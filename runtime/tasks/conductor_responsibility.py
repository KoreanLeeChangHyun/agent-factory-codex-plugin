"""Required deliverables live in the queue transaction, beyond any model turn."""
from __future__ import annotations

import json

from storage.errors import ContractError

SCHEMA = '''
CREATE TABLE IF NOT EXISTS obligations(id TEXT PRIMARY KEY, request_id TEXT NOT NULL, logical_owner TEXT NOT NULL,
 title TEXT NOT NULL, spec TEXT NOT NULL, prerequisites TEXT NOT NULL, state TEXT NOT NULL,
 wait_kind TEXT, reason TEXT, delegation_id TEXT, evidence TEXT, source TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS responsibility_instructions(id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
 text TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_details(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS responsibility_retries(id TEXT PRIMARY KEY, count INTEGER NOT NULL);
'''


class Responsibility:
    def __init__(self, store):
        self.store = store

    def register(self, c, request_id, tasks, source):
        """Atomic scope manifest: callers must explicitly name the authorized effects."""
        from tasks.conductor_queue import digest
        if not isinstance(tasks, list) or not tasks or not source:
            raise ContractError('obligations_invalid', 'An explicit authorized task manifest and source are required')
        req = self.store.row(c, 'SELECT * FROM requests WHERE id=?', request_id)
        if not req or req['status'] == 'cancelled':
            raise ContractError('obligations_invalid', 'Select a non-cancelled request')
        ids = {t.get('key'): 'required-' + digest([request_id, t.get('key')])[:24] for t in tasks if isinstance(t, dict)}
        if len(ids) != len(tasks) or any(not isinstance(k, str) or not k for k in ids):
            raise ContractError('obligations_invalid', 'Every required task needs a unique stable key')
        existing = {r['id'] for r in c.execute('SELECT id FROM obligations WHERE request_id=?', (request_id,))}
        graph = {}
        normalized = []
        for t in tasks:
            oid = ids[t['key']]
            deps = [ids.get(k, k) for k in t.get('prerequisites', [])]
            if any(k not in set(ids.values()) | existing or k == oid for k in deps):
                raise ContractError('obligations_invalid', 'Prerequisites must name this request required tasks')
            if not isinstance(t.get('title'), str) or not t['title'].strip() or not isinstance(t.get('spec'), dict):
                raise ContractError('obligations_invalid', 'Title and bounded execution spec required')
            graph[oid] = deps
            normalized.append((oid, t['title'], t['spec'], deps))
        def visit(key, trail):
            if key in trail:
                raise ContractError('obligations_cycle', 'Required task dependencies cannot cycle')
            for dep in graph.get(key, []):
                visit(dep, trail | {key})
        for oid in graph:
            visit(oid, set())
        for oid, title, spec, deps in normalized:
            old = self.store.row(c, 'SELECT * FROM obligations WHERE id=?', oid)
            if old:
                if (old['title'], json.loads(old['spec']), json.loads(old['prerequisites'])) != (title, spec, deps):
                    raise ContractError('obligations_conflict', 'An accepted required task is immutable; register an authorized successor')
                continue
            c.execute('INSERT INTO obligations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (oid, request_id, 'logical-conductor', title, json.dumps(spec), json.dumps(deps),
                       'registered', 'internal', 'planning', None, None, source, 1))
        if req['status'] == 'completed':
            conductor = self.store.row(c, 'SELECT chat_id FROM conductors WHERE id=?', req['conductor_id'])
            if conductor and conductor['chat_id'] != req['chat_id']:
                c.execute("UPDATE requests SET conductor_id='',owner_epoch=owner_epoch+1 WHERE id=?", (req['id'],))
                c.execute('INSERT OR IGNORE INTO request_waits VALUES(?,?)', (req['id'], '[]'))
                req = self.store.row(c, 'SELECT * FROM requests WHERE id=?', req['id'])
            self.store.set_request(c, req, 'accepted' if req['conductor_id'] else 'queued-for-instance', final_at=None)
        self.emit(c, request_id)
        return self.view(c, request_id)

    def instruction(self, c, request_id, text, source):
        from tasks.conductor_queue import digest
        iid = 'instruction-' + digest([request_id, source])[:24]
        c.execute('INSERT OR IGNORE INTO responsibility_instructions VALUES(?,?,?,?,?)', (iid, request_id, text, source, 'pending'))
        self.emit(c, request_id)
        return iid

    def acknowledge(self, c, request_id, instruction_id, task_ids, evidence):
        row = self.store.row(c, 'SELECT * FROM responsibility_instructions WHERE id=? AND request_id=?', instruction_id, request_id)
        if not row or not evidence or not isinstance(task_ids, list):
            raise ContractError('instruction_invalid', 'Acknowledge the exact instruction with coverage evidence')
        for oid in task_ids:
            if not self.store.row(c, 'SELECT id FROM obligations WHERE id=? AND request_id=?', oid, request_id):
                raise ContractError('instruction_invalid', 'Instruction coverage must bind registered required tasks')
        c.execute("UPDATE responsibility_instructions SET state='processed' WHERE id=?", (instruction_id,))
        self.store.pool.decide(c, request_id, 'instruction-coverage', {'instructionId': instruction_id, 'taskIds': task_ids, 'evidence': evidence}, row['source'], 'declared', instruction_id)
        self.emit(c, request_id)

    def bind(self, c, request_id, oid, delegation_id):
        row = self.store.row(c, 'SELECT * FROM obligations WHERE id=? AND request_id=?', oid, request_id)
        if not row or row['delegation_id']:
            raise ContractError('obligation_binding', 'Required task must be registered and not already assigned')
        if any(self.store.row(c, 'SELECT state FROM obligations WHERE id=?', dep)['state'] != 'completed' for dep in json.loads(row['prerequisites'])):
            raise ContractError('obligation_dependency', 'Required predecessor completion evidence is pending')
        c.execute("UPDATE obligations SET delegation_id=?,state='assigned',wait_kind=NULL,reason=NULL,version=version+1 WHERE id=?", (delegation_id, oid))
        self.emit(c, request_id)

    def exclude(self, c, request_id, oid, expected_version, reason, reference):
        row = self.store.row(c, 'SELECT * FROM obligations WHERE id=? AND request_id=?', oid, request_id)
        if not row or row['version'] != expected_version or not isinstance(reason, str) or not reason.strip():
            raise ContractError('scope_reduction_invalid', 'Select the observed required task and record the Human scope reduction reason')
        if row['delegation_id']:
            delegation = self.store.row(c, 'SELECT status FROM delegations WHERE id=?', row['delegation_id'])
            if delegation['status'] not in ('completed', 'failed', 'cancelled'):
                raise ContractError('scope_change_active', 'Cancel this exact delegation and observe termination before excluding it')
        evidence = {'reason': reason, 'authorizationReference': reference, 'actor': 'human', 'previousState': row['state'],
                    'previousEvidence': json.loads(row['evidence'] or 'null')}
        c.execute("UPDATE obligations SET state='excluded',wait_kind=NULL,reason='human-scope-reduction',evidence=?,version=version+1 WHERE id=?", (json.dumps(evidence), oid))
        self.store.pool.decide(c, request_id, 'scope-reduction', {'obligationId': oid, **evidence}, reference, 'human', reference)
        self.emit(c, request_id)

    def reconcile(self, c):
        count = 0
        for row in list(c.execute("SELECT * FROM obligations WHERE state NOT IN ('completed','cancelled','excluded')")):
            req = self.store.row(c, 'SELECT * FROM requests WHERE id=?', row['request_id'])
            if not req:
                continue
            if req['status'] == 'cancelled':
                c.execute("UPDATE obligations SET state='cancelled',wait_kind=NULL,reason='human-request-cancelled',version=version+1 WHERE id=?", (row['id'],))
                self.emit(c, row['request_id'])
                count += 1
                continue
            state, kind, reason, evidence = row['state'], row['wait_kind'], row['reason'], row['evidence']
            if row['delegation_id']:
                d = self.store.row(c, 'SELECT * FROM delegations WHERE id=?', row['delegation_id'])
                state = d['status']
                result = json.loads(d['result'] or 'null')
                if state == 'completed':
                    # A fake receipt is explicit test evidence. Managed receipts are validated by the backend.
                    if not result or not result.get('receiptPath') or not result.get('resultPath'):
                        state, kind, reason = 'receipt-missing', 'fault', 'completion-evidence-missing'
                    else:
                        evidence, kind, reason = json.dumps(result), None, None
                elif state in ('waiting', 'ready', 'dispatched', 'running'):
                    kind, reason = 'internal', self.store.admission(c, d) or state
                elif state in ('awaiting-answer', 'awaiting-approval'):
                    kind, reason = 'human', state
                elif state in ('failed', 'cancelled'):
                    kind, reason = 'fault', (json.loads(d['error'] or '{}')).get('code', state)
            else:
                blocked = [dep for dep in json.loads(row['prerequisites']) if self.store.row(c, 'SELECT state FROM obligations WHERE id=?', dep)['state'] != 'completed']
                state, kind, reason = ('waiting', 'internal', 'dependency:' + ','.join(blocked)) if blocked else ('registered', 'internal', 'planning')
                if not blocked and req['conductor_id']:
                    dispatched = self.store.row(c, 'SELECT status FROM mailbox WHERE id=?', 'mailbox-' + row['id'])
                    retry = self.store.row(c, 'SELECT count FROM responsibility_retries WHERE id=?', row['id'])
                    number = retry['count'] if retry else 0
                    if dispatched and dispatched['status'] == 'processed':
                        state, kind, reason = 'unassigned', 'fault', 'execution-unassigned'
                        if number < 3:
                            c.execute('INSERT OR REPLACE INTO responsibility_retries VALUES(?,?)', (row['id'], number + 1))
                            self.store.enqueue(c, req['conductor_id'], req['id'], 'required-task',
                                               {'obligationId': row['id'], 'title': row['title'], 'spec': json.loads(row['spec']), 'recovery': 'Previously consumed without assignment'},
                                               'required-recovery:' + row['id'] + ':' + str(number), mid='recovery-' + row['id'] + '-' + str(number))
                    else:
                        self.store.enqueue(c, req['conductor_id'], req['id'], 'required-task',
                                       {'obligationId': row['id'], 'title': row['title'], 'spec': json.loads(row['spec'])},
                                       'required:' + row['id'], mid='mailbox-' + row['id'])
            if (state, kind, reason, evidence) != (row['state'], row['wait_kind'], row['reason'], row['evidence']):
                c.execute('UPDATE obligations SET state=?,wait_kind=?,reason=?,evidence=?,version=version+1 WHERE id=?', (state, kind, reason, evidence, row['id']))
                self.emit(c, row['request_id'])
                count += 1
        return count

    def blockers(self, c, request_id):
        return [r['id'] for r in c.execute("SELECT id FROM obligations WHERE request_id=? AND state NOT IN ('completed','excluded')", (request_id,))] + [r['id'] for r in c.execute("SELECT id FROM responsibility_instructions WHERE request_id=? AND state='pending'", (request_id,))]

    def view(self, c, request_id):
        tasks = [{'id': r['id'], 'requestId': r['request_id'], 'logicalOwner': r['logical_owner'], 'title': r['title'],
                  'spec': json.loads(r['spec']), 'prerequisites': json.loads(r['prerequisites']), 'state': r['state'],
                  'waitKind': r['wait_kind'], 'waitReason': r['reason'], 'delegationId': r['delegation_id'],
                  'completionEvidence': json.loads(r['evidence'] or 'null'), 'source': r['source'], 'version': r['version']}
                 for r in c.execute('SELECT * FROM obligations WHERE request_id=? ORDER BY rowid', (request_id,))]
        return {'requestId': request_id, 'logicalOwner': 'logical-conductor', 'tasks': tasks,
                'pendingInstructions': [dict(r) for r in c.execute("SELECT * FROM responsibility_instructions WHERE request_id=? AND state='pending'", (request_id,))],
                'completionBlockedBy': self.blockers(c, request_id)}

    def emit(self, c, request_id):
        req = self.store.row(c, 'SELECT * FROM requests WHERE id=?', request_id)
        self.store.event(c, req['chat_id'], 'responsibility-state', self.view(c, request_id))
