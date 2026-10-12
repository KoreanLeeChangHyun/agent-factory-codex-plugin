"""Domain/child-area admission for one logical conductor's physical instances and workers.

The queue transaction owns reservations. ManagedBackend confirms membership before
external submission. Idle retirement releases a pool slot, never deletes a session.
"""
import json
import math

from storage.errors import ContractError
from storage.files import safe_read_json
from tasks import domains

SCHEMA = '''
CREATE TABLE IF NOT EXISTS pool_members(id TEXT PRIMARY KEY, role TEXT NOT NULL, area TEXT NOT NULL,
  signature TEXT NOT NULL, state TEXT NOT NULL, last_used REAL NOT NULL);
CREATE TABLE IF NOT EXISTS entity_areas(kind TEXT NOT NULL, id TEXT NOT NULL, area TEXT NOT NULL, PRIMARY KEY(kind,id));
CREATE TABLE IF NOT EXISTS attempt_workers(attempt_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS instance_waits(conductor_id TEXT PRIMARY KEY, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS request_waits(request_id TEXT PRIMARY KEY, message TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fixed_decisions(id TEXT PRIMARY KEY, request_id TEXT NOT NULL, kind TEXT NOT NULL,
  value TEXT NOT NULL, source TEXT NOT NULL, actor TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY, request_id TEXT, input_id TEXT, delegation_id TEXT,
  conductor_id TEXT, slot TEXT, epoch INTEGER, kind TEXT NOT NULL, state TEXT NOT NULL, text TEXT, source TEXT NOT NULL);
'''
DEFAULT = {'worker': {'domainLimit': 2, 'subdomainLimit': 1, 'reuse': 'oldest-idle', 'idleRetentionSeconds': None},
           'conductor': {'domainLimit': 2, 'subdomainLimit': 1, 'reuse': 'oldest-idle', 'idleRetentionSeconds': None},
           'domains': {}, 'subdomains': {}}


def enabled(policy):
    return policy.get('employment') is True or policy.get('conductor') == 'managed' or policy.get('executor') == 'managed'


def signature(policy, role, spec=None):
    from tasks.conductor_queue import digest
    settings = ((spec or {}).get('executionSettings') if role == 'worker' else None) or policy.get('work' if role == 'worker' else 'conductorSettings') or {}
    settings = {k: v for k, v in settings.items() if k not in ('sandbox', 'approvalPolicy') and not (k == 'workProfile' and v == 'work')}
    sandbox = policy.get('sandbox') if role == 'worker' else policy.get('conductorSandbox', 'read-only')
    if role == 'worker' and ((spec or {}).get('workspace') or {}).get('mode') == 'read-only':
        sandbox = 'read-only'
    return digest({'role': role, 'settings': settings, 'sandbox': sandbox, 'approvalPolicy': policy['approvalPolicy'],
                   'compaction': policy.get('compaction') if role == 'conductor' else None})


def session_busy(root, agent_id):
    if domains._worker_active(root, agent_id):
        return True
    latest = None
    for path in (root / 'agents' / agent_id / 'runs').glob('*/state.json'):
        try:
            run = safe_read_json(path)
        except (ContractError, OSError, ValueError):
            return True
        marker = run.get('createdAt') or run.get('acceptedAt') or path.parent.name
        if latest is None or str(marker) > latest[0]:
            latest = (str(marker), run)
    return bool(latest and (latest[1].get('status') == 'needs-human-decision' or latest[1].get('stopPending')))


class Pool:
    def __init__(self, store):
        self.store = store

    def catalog(self):
        document = domains.read(self.store.path.parent)
        return {'revision': document['revision'], 'domains': document['domains'], 'subdomains': document.get('subdomains', [])}

    def area(self, value):
        if not isinstance(value, dict):
            raise ContractError('area_required', 'Select an existing domain and explicit child area before hiring')
        document = domains.read(self.store.path.parent)
        domain = next((d for d in document['domains'] if d['id'] == value.get('domainId') and not d.get('provisional')), None)
        child = next((s for s in document.get('subdomains', []) if s['id'] == value.get('subdomainId') and s['domainId'] == value.get('domainId')), None)
        if not domain or not child:
            raise ContractError('area_required', 'Select an existing domain and child area; do not infer membership')
        return {'domainId': domain['id'], 'domain': domain['name'], 'subdomainId': child['id'], 'subdomain': child['name'],
                'writeScope': child.get('writeScope')}

    def set_area(self, c, kind, ident, area):
        c.execute('INSERT OR REPLACE INTO entity_areas VALUES(?,?,?)', (kind, ident, json.dumps(area)))

    def get_area(self, c, kind, ident):
        row = c.execute('SELECT area FROM entity_areas WHERE kind=? AND id=?', (kind, ident)).fetchone()
        return json.loads(row[0]) if row else None

    def configuration(self, c):
        row = c.execute("SELECT value FROM meta WHERE key='employment'").fetchone()
        return json.loads(row[0]) if row else json.loads(json.dumps(DEFAULT))

    def configure(self, value, reference):
        if not isinstance(value, dict) or not isinstance(reference, str) or not reference.strip():
            raise ContractError('pool_policy_invalid', 'Pool configuration needs a captured setting reference')
        if set(value) - {'worker', 'conductor', 'workLight', 'verification', 'explore', 'scribe', 'domains', 'subdomains'}:
            raise ContractError('pool_policy_invalid', 'Unknown employment setting')
        def validate(config, *, child=False):
            for role in ('worker', 'conductor', 'workLight', 'verification', 'explore', 'scribe'):
                if role not in config:
                    continue
                rule = config[role]
                allowed = {'domainLimit', 'subdomainLimit', 'reuse', 'idleRetentionSeconds'} - ({'domainLimit'} if child else set())
                if not isinstance(rule, dict) or set(rule) - allowed:
                    raise ContractError('pool_policy_invalid', 'Child overrides cannot change the parent domain limit')
                if any(k in rule and (type(rule[k]) is not int or rule[k] < 1) for k in ('domainLimit', 'subdomainLimit')):
                    raise ContractError('pool_policy_invalid', 'Positive domain/subdomain limits required')
                if 'reuse' in rule and rule['reuse'] not in ('oldest-idle', 'newest-idle'):
                    raise ContractError('pool_policy_invalid', 'Select oldest-idle or newest-idle reuse')
                age = rule.get('idleRetentionSeconds')
                if age is not None and (type(age) not in (int, float) or not math.isfinite(age) or age < 0):
                    raise ContractError('pool_policy_invalid', 'Idle retention is finite nonnegative seconds or null')
        validate(value)
        catalog = self.catalog()
        valid_ids = {'domains': {d['id'] for d in catalog['domains'] if not d.get('provisional')},
                     'subdomains': {s['id'] for s in catalog['subdomains']}}
        for group in ('domains', 'subdomains'):
            if not isinstance(value.get(group, {}), dict):
                raise ContractError('pool_policy_invalid', 'Area overrides are keyed by stable area ID')
            for key, rules in value.get(group, {}).items():
                if key not in valid_ids[group] or not isinstance(rules, dict) or set(rules) - {'worker', 'conductor', 'workLight', 'verification', 'explore', 'scribe'}:
                    raise ContractError('pool_policy_invalid', 'Area override needs an existing ID and role rules')
                validate(rules, child=group == 'subdomains')
        with self.store.tx() as c:
            current = self.configuration(c)
            for key, update in value.items():
                if key in ('domains', 'subdomains'):
                    for area_id, rules in update.items():
                        for role, values in rules.items():
                            current[key].setdefault(area_id, {}).setdefault(role, {}).update(values)
                else:
                    current.setdefault(key, dict(current['worker'])).update(update)
            c.execute("INSERT OR REPLACE INTO meta VALUES('employment',?)", (json.dumps(current),))
            self.store.op(c, 'pool-configured', reference=reference)
        return current

    def rule(self, c, role, area):
        config = self.configuration(c)
        return {**config.get(role, config['worker']), **config.get('domains', {}).get(area['domainId'], {}).get(role, {}),
                **{k: v for k, v in config.get('subdomains', {}).get(area['subdomainId'], {}).get(role, {}).items() if k != 'domainLimit'}}

    def room(self, c, role, area):
        rule = self.rule(c, role, area)
        members = []
        for row in c.execute("SELECT * FROM pool_members WHERE role=?", (role,)):
            agents = [row['id']] if role != 'conductor' else ['cq-' + row['id'].split('-', 1)[1] + '-' + slot for slot in ('a', 'b')]
            if row['state'] == 'busy' or any(session_busy(self.store.path.parent, agent) for agent in agents):
                members.append(json.loads(row['area']))
        pooled = {r['id'] for r in c.execute('SELECT id FROM pool_members')}
        for worker in self.store.roles.native():
            profile = self.store.roles.native_profile(worker)
            if worker['agentId'] not in pooled and self.store.roles.pool_role(profile) == role and not worker.get('removed') and worker.get('domain') and worker['availability'] in ('busy','queued','waiting-human','uncertain'):
                members.append({'domainId': worker['domain']['domainId'], 'subdomainId': None})
        if sum(a['domainId'] == area['domainId'] for a in members) >= rule['domainLimit']:
            return 'employment-limit:domain'
        if sum(a['subdomainId'] == area['subdomainId'] for a in members) >= rule['subdomainLimit']:
            return 'employment-limit:subdomain'
        return None

    def idle(self, c, role, area, signature, *, retired=False, chat_id=None):
        rule = self.rule(c, role, area)
        document = domains.read(self.store.path.parent)
        ordered = 'ASC' if rule['reuse'] == 'oldest-idle' else 'DESC'
        for row in c.execute("SELECT * FROM pool_members WHERE role=? AND signature=? AND state=? ORDER BY last_used " + ordered + ',id', (role, signature, "retired" if retired else "idle")):
            agents = [row['id']] if role != 'conductor' else ['cq-' + row['id'].split('-', 1)[1] + '-' + slot for slot in ('a', 'b')]
            if role == 'conductor' and chat_id is not None:
                instance = c.execute('SELECT chat_id FROM conductors WHERE id=?', (row['id'],)).fetchone()
                if instance and instance['chat_id'] != chat_id and c.execute("SELECT 1 FROM requests WHERE conductor_id=? AND status NOT IN ('completed','cancelled')", (row['id'],)).fetchone():
                    continue  # An unfinished parent/question retains its chat binding.
            parent = document['assignments'].get(row['id'])
            child = document.get('subdomainAssignments', {}).get(row['id'])
            if (parent and parent.get('domainId') != area['domainId']) or (child and child.get('subdomainId') != area['subdomainId']):
                continue  # A Human placement change supersedes reuse eligibility, never the recorded task area.
            if json.loads(row['area'])['subdomainId'] == area['subdomainId'] and not any(session_busy(self.store.path.parent, agent) for agent in agents):
                return dict(row)
        return None

    def member(self, c, ident, role, area, signature, state):
        c.execute('INSERT INTO pool_members VALUES(?,?,?,?,?,?)', (ident, role, json.dumps(area), signature, state, self.store.clock()))

    def retire_idle(self, c):
        count = 0
        for row in list(c.execute("SELECT * FROM pool_members WHERE state='idle'")):
            agents = [row['id']] if row['role'] != 'conductor' else ['cq-' + row['id'].split('-', 1)[1] + '-' + slot for slot in ('a', 'b')]
            if any(session_busy(self.store.path.parent, agent) for agent in agents):
                continue
            age = self.rule(c, row['role'], json.loads(row['area']))['idleRetentionSeconds']
            if age is not None and self.store.clock() - row['last_used'] >= age:
                c.execute("UPDATE pool_members SET state='retired' WHERE id=?", (row['id'],))
                count += 1
        return count

    def reserve_worker(self, c, delegation, signature):
        from tasks.conductor_queue import ident
        assigned = c.execute('SELECT worker_id FROM attempt_workers WHERE attempt_id=?', (delegation['attempt_id'],)).fetchone()
        if assigned:
            return assigned[0], None
        area = self.get_area(c, 'delegation', delegation['id'])
        if not area:
            return None, 'area-required'
        role = self.store.roles.pool_role(json.loads(delegation['spec']).get('workProfile', 'work'))
        reason = self.room(c, role, area)
        if reason:
            return None, reason
        member = self.idle(c, role, area, signature)
        if not member:
            spec = json.loads(delegation['spec'])
            settings = spec.get('executionSettings')
            if settings:
                settings = {**settings, 'sandbox': 'read-only' if (spec.get('workspace') or {}).get('mode') == 'read-only' else settings['sandbox']}
                member = self.store.roles.adopt_native(c, area, spec.get('workProfile', 'work'), signature, settings)
        if member:
            worker = member['id']
        else:
            reason = self.room(c, role, area)
            if reason:
                return None, reason
            retired = self.idle(c, role, area, signature, retired=True)
            worker = retired['id'] if retired else ident('work-cq')
            if not retired:
                self.member(c, worker, role, area, signature, 'idle')
        c.execute("UPDATE pool_members SET state='busy',last_used=? WHERE id=?", (self.store.clock(), worker))
        c.execute('INSERT INTO attempt_workers VALUES(?,?)', (delegation['attempt_id'], worker))
        return worker, None

    def release_worker(self, c, attempt_id):
        verifier = c.execute('SELECT agent_id FROM attempt_verifiers WHERE attempt_id=?', (attempt_id,)).fetchone()
        if verifier:
            c.execute("UPDATE pool_members SET state='idle',last_used=? WHERE id=?", (self.store.clock(), verifier[0]))
        row = c.execute('SELECT worker_id FROM attempt_workers WHERE attempt_id=?', (attempt_id,)).fetchone()
        if row:
            c.execute("UPDATE pool_members SET state='idle',last_used=? WHERE id=?", (self.store.clock(), row[0]))

    def decisions(self, c, request_id):
        return [{'id': r['id'], 'requestId': r['request_id'], 'kind': r['kind'], 'value': json.loads(r['value']),
                 'source': r['source'], 'actor': r['actor'], 'createdAt': r['created_at']}
                for r in c.execute('SELECT * FROM fixed_decisions WHERE request_id=? ORDER BY created_at,id', (request_id,))]

    def decide(self, c, request_id, kind, value, source, actor, key):
        from tasks.conductor_queue import digest
        ident = 'decision-' + digest([request_id, key])[:24]
        previous = c.execute('SELECT * FROM fixed_decisions WHERE id=?', (ident,)).fetchone()
        if previous and (json.loads(previous['value']) != value or previous['source'] != source):
            raise ContractError('decision_conflict', 'Confirmed decisions are immutable; append a superseding decision')
        c.execute('INSERT OR IGNORE INTO fixed_decisions VALUES(?,?,?,?,?,?,?)', (ident, request_id, kind, json.dumps(value), source, actor, self.store.clock()))
        return ident

    def enroll_worker(self, chat_id, agent_id, declared_area, reference):
        """Explicitly adopt a recorded idle Work session; never infer its child area or change its model/policy."""
        from storage.files import AGENT_ID
        if not isinstance(reference, str) or not reference.strip() or not isinstance(agent_id, str) or not AGENT_ID.fullmatch(agent_id):
            raise ContractError('pool_enrollment_invalid', 'Exact agent, area and Human assignment reference required')
        area = self.area(declared_area)
        session = safe_read_json(self.store.path.parent / 'agents' / agent_id / 'session.json')
        policy = self.store.policy(self.store.connection(), chat_id)
        settings = policy.get('work') or {}
        if session.get('role') != 'work' or session.get('workProfile', 'work') != settings.get('workProfile', 'work'):
            raise ContractError('pool_session_incompatible', 'Only a matching recorded Work profile can be reused')
        for field in ('provider', 'model', 'reasoningEffort', 'fast'):
            if field in settings and session.get(field) != settings[field]:
                raise ContractError('pool_session_incompatible', 'Recorded session setting differs: ' + field)
        if session.get('sandbox') != policy.get('sandbox') or session.get('humanApprovalPolicy') != policy.get('approvalPolicy'):
            raise ContractError('pool_session_incompatible', 'Recorded permissions must match the captured policy')
        if session_busy(self.store.path.parent, agent_id):
            raise ContractError('pool_session_busy', 'An active session cannot be adopted or relabelled')
        with self.store.tx() as c:
            old = self.store.row(c, 'SELECT * FROM pool_members WHERE id=?', agent_id)
            if old:
                if any(json.loads(old['area'])[key] != area[key] for key in ('domainId', 'subdomainId')) or old['signature'] != signature(policy, 'worker'):
                    raise ContractError('pool_session_incompatible', 'Existing pool membership remains unchanged')
                return {'workerId': agent_id, 'area': area, 'reused': True}
            reason = self.room(c, 'worker', area)
            if reason:
                raise ContractError('employment_limit', reason)
            domains.assign_subdomain(self.store.path.parent, agent_id, area['domainId'], area['subdomainId'], 'human', reference)
            self.member(c, agent_id, 'worker', area, signature(policy, 'worker'), 'idle')
            self.store.op(c, 'worker-enrolled', workerId=agent_id, reference=reference)
        return {'workerId': agent_id, 'area': area, 'reused': True}
