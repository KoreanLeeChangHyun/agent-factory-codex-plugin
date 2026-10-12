"""Area role settings, captured new-task routes and exact managed workflow bindings."""
from __future__ import annotations

import json

from storage.errors import ContractError
from tasks import conductor_pool, domains

SCHEMA = '''
CREATE TABLE IF NOT EXISTS area_role_settings(area_id TEXT NOT NULL, role TEXT NOT NULL, settings TEXT NOT NULL,
 source TEXT NOT NULL, PRIMARY KEY(area_id,role));
CREATE TABLE IF NOT EXISTS area_processing(area_id TEXT PRIMARY KEY, route TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS request_processing(request_id TEXT PRIMARY KEY, route TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS role_member_settings(agent_id TEXT PRIMARY KEY, profile TEXT NOT NULL, settings TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempt_verifiers(attempt_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workflow_observations(attempt_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
'''
PROFILES = ('workLight', 'work', 'verification')
ROUTES = ('work', 'work-verification')


class Roles:
    def __init__(self, store):
        self.store = store
        self.native_cache = None

    def native(self):
        """Reuse the existing roster, with an explicit observation time; never migrate its records."""
        root = getattr(self.store, 'project_root', None)
        if root is None:
            return []
        if self.native_cache is None or self.store.clock() - self.native_cache[0] >= 30:
            import exec as runtime
            from tasks import team
            roster = team.roster(runtime, root)
            for worker in roster['workers']:
                if worker.get('role') == 'work' and not worker.get('workProfile'):
                    from storage.files import safe_read_json
                    try:
                        session = safe_read_json(self.store.path.parent / 'agents' / worker['agentId'] / 'session.json')
                        worker['workProfile'] = session.get('workProfile')
                    except (ContractError, OSError, ValueError):
                        worker['role'] = None  # An unreadable profile is unknown, never an assumed Expert.
            self.native_cache = (self.store.clock(), roster)
        return self.native_cache[1]['workers']

    @staticmethod
    def native_profile(worker):
        return 'verification' if worker.get('role') == 'verification' else (worker.get('workProfile') or 'work') if worker.get('role') == 'work' else None

    def adopt_native(self, c, area, profile, signature, settings):
        from storage.files import safe_read_json
        placements = domains.read(self.store.path.parent)
        for worker in self.native():
            agent = worker['agentId']
            if worker.get('removed') or worker.get('availability') != 'idle' or self.native_profile(worker) != profile:
                continue
            child = placements.get('subdomainAssignments', {}).get(agent) or {}
            if (worker.get('domain') or {}).get('domainId') != area['domainId'] or child.get('subdomainId') != area['subdomainId']:
                continue
            if self.store.row(c, 'SELECT id FROM pool_members WHERE id=?', agent) or conductor_pool.session_busy(self.store.path.parent, agent):
                continue
            session = safe_read_json(self.store.path.parent / 'agents' / agent / 'session.json')
            if any(session.get(key) != settings.get(key) for key in ('model','provider','reasoningEffort','fast')):
                continue
            if session.get('sandbox') != settings['sandbox'] or session.get('humanApprovalPolicy') != settings['approvalPolicy']:
                continue
            self.store.pool.member(c, agent, self.pool_role(profile), area, signature, 'idle')
            c.execute('INSERT INTO role_member_settings VALUES(?,?,?,?)', (agent, profile, json.dumps(settings), 'existing-explicit-placement'))
            return self.store.row(c, 'SELECT * FROM pool_members WHERE id=?', agent)
        return None

    def area_id(self, value):
        catalog = self.store.pool.catalog()
        if value not in {a['id'] for a in catalog['domains'] + catalog['subdomains']}:
            raise ContractError('area_required', 'Select a registered domain or subdomain')
        return value

    def configure(self, c, area_id, reference, *, route=None, profile=None, settings=None):
        self.area_id(area_id)
        if not isinstance(reference, str) or not reference.strip():
            raise ContractError('role_setting_invalid', 'Captured Human setting reference required')
        if route is not None:
            if route not in ROUTES:
                raise ContractError('route_invalid', 'Select work or work-verification for new requests')
            c.execute('INSERT OR REPLACE INTO area_processing VALUES(?,?,?)', (area_id, route, reference))
        if profile is not None:
            if profile not in (*PROFILES, 'explore', 'scribe') or not isinstance(settings, dict) or not settings.get('model') or settings.get('provider') not in ('codex', 'claude', 'antigravity'):
                raise ContractError('role_setting_invalid', 'Use an explicit existing role model/provider setting')
            if settings.get('sandbox') not in ('read-only', 'workspace-write', 'danger-full-access') or settings.get('approvalPolicy') not in ('bypass', 'required'):
                raise ContractError('role_setting_invalid', 'Capture the role permissions without substituting a model')
            c.execute('INSERT OR REPLACE INTO area_role_settings VALUES(?,?,?,?)', (area_id, profile, json.dumps(settings), reference))

    def processing(self, c, area):
        for aid in (area.get('subdomainId'), area.get('domainId')):
            row = c.execute('SELECT * FROM area_processing WHERE area_id=?', (aid,)).fetchone()
            if row:
                return {'route': row['route'], 'source': row['source'], 'inheritedFrom': aid}
        return {'route': 'work', 'source': 'existing-work-default', 'inheritedFrom': None}

    def capture(self, c, request_id, area, choice=None, source=None, *, profile="work"):
        route = self.processing(c, area or {})
        if choice is not None:
            if choice not in ROUTES or not source:
                raise ContractError('route_invalid', 'New-request route choice needs its exact Human input')
            route = {'route': choice, 'source': source, 'inheritedFrom': None}
        if profile not in ('work', 'workLight', 'explore', 'scribe'):
            raise ContractError('role_profile_invalid', 'Select an existing Work profile')
        route['workProfile'] = profile
        req = self.store.row(c, 'SELECT chat_id FROM requests WHERE id=?', request_id)
        policy = self.store.policy(c, req['chat_id'])
        for role, key in ((profile, 'initialExecutionSettings'), ('verification', 'initialVerificationSettings')):
            try:
                route[key] = self.settings(c, area or {}, role, policy)
            except ContractError as error:
                if error.code != 'role_settings_required':
                    raise
                route[key] = None
        c.execute('INSERT INTO request_processing VALUES(?,?,?)', (request_id, route['route'], json.dumps(route)))
        return route

    def settings(self, c, area, profile, policy):
        for aid in (area.get('subdomainId'), area.get('domainId')):
            row = c.execute('SELECT settings FROM area_role_settings WHERE area_id=? AND role=?', (aid, profile)).fetchone()
            if row:
                return json.loads(row['settings'])
        raw = (policy.get('roleSettings') or {}).get(profile) or (policy.get('work') if profile == (policy.get('work') or {}).get('workProfile', 'work') else None)
        if not raw or not raw.get('model'):
            raise ContractError('role_settings_required', 'Configure the selected role using its existing captured settings')
        return {**raw, 'sandbox': raw.get('sandbox', policy.get('sandbox')), 'approvalPolicy': raw.get('approvalPolicy', policy['approvalPolicy'])}

    def freeze(self, c, req, spec, area, policy):
        captured = c.execute('SELECT * FROM request_processing WHERE request_id=?', (req['id'],)).fetchone()
        route = captured['route'] if captured else 'work'
        profile = spec.get('workProfile', json.loads(captured['source']).get('workProfile', 'work') if captured else (policy.get('work') or {}).get('workProfile', 'work'))
        if profile not in ('work', 'workLight', 'explore', 'scribe'):
            raise ContractError('role_profile_invalid', 'Preserve the selected Work profile')
        if 'taskMode' in spec and spec['taskMode'] != route:
            raise ContractError('route_immutable', 'The request processing choice is fixed at acceptance')
        if route == 'work' and profile == 'work' and not policy.get('work') and policy['executor'] == 'fake':
            return spec  # Historical fake development requests have no role/model selection.
        initial = json.loads(captured['source']) if captured else {}
        settings = initial.get('initialExecutionSettings') if initial.get('workProfile') == profile else None
        settings = settings or self.settings(c, area or {}, profile, policy)
        if settings['sandbox'] != policy.get('sandbox') or settings['approvalPolicy'] != policy['approvalPolicy']:
            raise ContractError('role_permission_invalid', 'Selected role permissions must match the captured request authority')
        result = {**spec, 'taskMode': route, 'workProfile': profile, 'executionSettings': {**settings, 'workProfile': profile}, 'workIsolation': policy.get('workIsolation', False)}
        if route == 'work-verification':
            result['verificationSettings'] = initial.get('initialVerificationSettings') or self.settings(c, area or {}, 'verification', policy)
            if result['verificationSettings']['approvalPolicy'] != policy['approvalPolicy']:
                raise ContractError('role_permission_invalid', 'Verification cannot change captured approval authority')
        return result

    def pool_role(self, profile):
        return 'worker' if profile == 'work' else profile

    def signature(self, settings, profile):
        return conductor_pool.signature({'work': {**settings, 'workProfile': profile}, 'sandbox': settings['sandbox'], 'approvalPolicy': settings['approvalPolicy']}, 'worker')

    def hire(self, c, area_value, profile, settings, reference, *, actor="human"):
        from tasks.conductor_queue import ident
        area = self.store.pool.area(area_value)
        if profile not in PROFILES:
            raise ContractError('role_profile_invalid', 'Select Worker, Expert or Verifier')
        if actor == 'human':
            self.configure(c, area['subdomainId'], reference, profile=profile, settings=settings)
        role, signature = self.pool_role(profile), self.signature(settings, profile)
        existing = self.store.pool.idle(c, role, area, signature) or self.adopt_native(c, area, profile, signature, settings)
        if existing:
            return {'agentId': existing['id'], 'profile': profile, 'reused': True}
        reason = self.store.pool.room(c, role, area)
        if reason:
            raise ContractError('employment_limit', reason)
        agent = ident('verify-cq' if profile == 'verification' else 'work-cq')
        domains.assign_subdomain(self.store.path.parent, agent, area['domainId'], area['subdomainId'], actor, reference)
        self.store.pool.member(c, agent, role, area, signature, 'idle')
        c.execute('INSERT INTO role_member_settings VALUES(?,?,?,?)', (agent, profile, json.dumps(settings), reference))
        return {'agentId': agent, 'profile': profile, 'reused': False, 'nativeSession': 'created-on-first-assignment'}

    def reserve_verifier(self, c, d, spec, implementation_agent):
        previous = c.execute('SELECT agent_id FROM attempt_verifiers WHERE attempt_id=?', (d['attempt_id'],)).fetchone()
        if previous:
            return previous[0], None
        area = self.store.pool.get_area(c, 'delegation', d['id'])
        settings = spec['verificationSettings']
        sig = self.signature(settings, 'verification')
        member = self.store.pool.idle(c, 'verification', area, sig) or self.adopt_native(c, area, 'verification', sig, settings)
        reason = self.store.pool.room(c, 'verification', area)
        if reason:
            return None, reason
        if not member:
            hired = self.hire(c, area, 'verification', settings, 'captured-task:' + d['id'], actor='ai')
            member = self.store.row(c, 'SELECT * FROM pool_members WHERE id=?', hired['agentId'])
        if member['id'] == implementation_agent:
            raise ContractError('verification_independence', 'Implementation owner cannot independently verify its result')
        c.execute("UPDATE pool_members SET state='busy',last_used=? WHERE id=?", (self.store.clock(), member['id']))
        c.execute('INSERT INTO attempt_verifiers VALUES(?,?)', (d['attempt_id'], member['id']))
        return member['id'], None

    def projection(self, c):
        catalog = self.store.pool.catalog()
        members = []
        for row in c.execute("SELECT * FROM pool_members WHERE role!='conductor'"):
            settings = c.execute('SELECT * FROM role_member_settings WHERE agent_id=?', (row['id'],)).fetchone()
            tasks = [r['delegation_id'] for r in c.execute('SELECT a.delegation_id FROM attempts a JOIN attempt_workers w ON w.attempt_id=a.id WHERE w.worker_id=? AND a.status NOT IN (\'completed\',\'failed\',\'cancelled\',\'lost\')', (row['id'],))]
            tasks += [r['delegation_id'] for r in c.execute('SELECT a.delegation_id FROM attempts a JOIN attempt_verifiers v ON v.attempt_id=a.id WHERE v.agent_id=? AND a.status NOT IN (\'completed\',\'failed\',\'cancelled\',\'lost\')', (row['id'],))]
            availability = row['state']
            if availability == 'busy':
                availability = 'reserved'
                for tid in tasks:
                    d = self.store.row(c, 'SELECT * FROM delegations WHERE id=?', tid)
                    observed = self.store.row(c, 'SELECT payload FROM workflow_observations WHERE attempt_id=?', d['attempt_id'])
                    observation = json.loads(observed['payload']) if observed else {}
                    is_verifier = row['role'] == 'verification'
                    if observation:
                        expected = 'verification' if is_verifier else 'work'
                        if observation.get('activeRole') == expected and observation.get('activeStatus') in ('running', 'starting'):
                            availability = 'verifying' if is_verifier else 'running'
                    elif not is_verifier and self.store.row(c, 'SELECT status FROM attempts WHERE id=?', d['attempt_id'])['status'] == 'running':
                        availability = 'running'
                    elif is_verifier:
                        availability = 'waiting-result'
            elif availability == 'idle' and conductor_pool.session_busy(self.store.path.parent, row['id']):
                availability = 'occupied-externally'
            members.append({'poolState': row['state'], 'id': row['id'], 'profile': settings['profile'] if settings else ('work' if row['role']=='worker' else row['role']),
                            'area': json.loads(row['area']), 'state': availability, 'taskIds': tasks,
                            'settings': json.loads(settings['settings']) if settings else None})
        placements = domains.read(self.store.path.parent)
        pooled = {m['id'] for m in members}
        for worker in self.native():
            if worker['agentId'] in pooled or worker.get('removed') or not worker.get('domain'):
                continue
            profile = self.native_profile(worker)
            if profile is None:
                continue
            child = placements.get('subdomainAssignments', {}).get(worker['agentId']) or {}
            availability = worker['availability']
            latest = worker.get('latestRun') or {}
            state = 'running' if latest.get('status') in ('running','starting') else 'idle' if availability == 'idle' else 'occupied-externally'
            members.append({'id': worker['agentId'], 'profile': profile, 'source': 'team-roster', 'observedAt': self.native_cache[0],
                            'area': {'domainId': worker['domain']['domainId'], 'subdomainId': child.get('subdomainId')}, 'state': state,
                            'taskIds': [t['taskId'] for t in worker.get('currentTasks', [])],
                            'settings': {k: worker.get(k) for k in ('model','provider','reasoningEffort','fast','sandbox','humanApprovalPolicy')},
                            'reuseRequiresArea': not bool(child.get('subdomainId'))})
        areas = []
        for d in catalog['domains']:
            children = [s for s in catalog['subdomains'] if s['domainId']==d['id']]
            for a in [d, *children]:
                selected = [m for m in members if m['area']['domainId']==a['id'] or m['area']['subdomainId']==a['id']]
                area = {'domainId': a.get('domainId',a['id']), 'subdomainId': a['id'] if 'domainId' in a else None}
                areas.append({**a, 'processing': self.processing(c, area), 'members': selected,
                              'counts': {p: {'hired': sum(m['profile']==p and m['state']!='retired' for m in selected), 'active': sum(m['profile']==p and m['state'] in ('running','verifying') for m in selected), 'idle': sum(m['profile']==p and m['state']=='idle' for m in selected), 'waiting': sum(m['profile']==p and m['state'] in ('reserved','waiting-result','occupied-externally') for m in selected)} for p in PROFILES}})
        return {'nativeProblems': self.native_cache[1].get('problems', []) if self.native_cache else [], 'nativeObservation': {'at': self.native_cache[0], 'consistency': 'sequential-observations'} if self.native_cache else None,
                'responsibilities': [self.store.responsibility.view(c, r['id']) for r in c.execute('SELECT id FROM requests')], 'chats': [{'id': r['id'], 'policy': json.loads(r['policy'])} for r in c.execute('SELECT * FROM chats ORDER BY created_at')], 'catalog': catalog, 'areas': areas, 'tasks': [self.task(c, dict(d)) for d in c.execute('SELECT * FROM delegations ORDER BY created_at')]}

    def task(self, c, d):
        spec = json.loads(d['spec'])
        work = c.execute('SELECT worker_id FROM attempt_workers WHERE attempt_id=?', (d['attempt_id'],)).fetchone()
        verifier = c.execute('SELECT agent_id FROM attempt_verifiers WHERE attempt_id=?', (d['attempt_id'],)).fetchone()
        observation = c.execute('SELECT payload FROM workflow_observations WHERE attempt_id=?', (d['attempt_id'],)).fetchone()
        value = json.loads(observation[0]) if observation else {}
        stage = 'not-requested' if spec.get('taskMode','work') == 'work' else ('waiting-result' if verifier else 'waiting-assignment')
        if value:
            stage = value.get('verificationState', stage)
        binding = value.get('binding') or {}
        if stage == 'pass' and binding.get('resultPath') and binding.get('resultRevision'):
            from pathlib import Path
            import hashlib
            path = Path(binding['resultPath'])
            try:
                if not path.resolve().is_relative_to(self.store.path.parent / 'agents') or hashlib.sha256(path.read_bytes()).hexdigest() != binding['resultRevision']:
                    stage = 'revision-waiting'
            except OSError:
                stage = 'revision-waiting'
        return {'chatId': d['chat_id'], 'questions': [self.store.question_view(dict(q)) for q in c.execute("SELECT * FROM questions WHERE delegation_id=? AND state='pending'", (d['id'],))], 'id': d['id'], 'requestId': d['request_id'], 'title': d['title'], 'implementationState': value.get('implementationState') or d['status'], 'workProfile': spec.get('workProfile','work'),
                'workAgentId': work[0] if work else None, 'verificationAgentId': verifier[0] if verifier else None, 'verificationState': stage,
                'binding': value.get('binding'), 'route': spec.get('taskMode','work'), 'version': d['version'], 'waitReason': self.store.admission(c, d) if d['status'] not in ('completed','failed','cancelled') else None}
