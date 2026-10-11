"""Durable chat routing and event-driven supervision over managed executions.

A single atomic ledger owns messages, reservations and the report outbox. Provider
execution remains in exec.py; uncertain starts are observed, never replayed blindly.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path

from adapters import provider_for
from storage import files, paths
from storage.errors import ContractError

TERMINAL = {'completed', 'failed', 'cancelled', 'runtime-error', 'needs-human-decision'}


def require(condition, code, message):
    if not condition:
        raise ContractError(code, message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def identity(prefix):
    return prefix + '-' + uuid.uuid4().hex


def event(state, key, kind, **data):
    existing = next((e for e in state['events'] if e['key'] == key), None)
    if existing:
        return existing
    value = {'id': identity('event'), 'sequence': len(state['events']) + 1,
             'key': key, 'kind': kind, 'chatId': state['chatId'], **copy.deepcopy(data)}
    state['events'].append(value)
    return value


class Conductor:
    def __init__(self, project_root, chat_id, *, runtime_home=None, project_id=None):
        files.validate_id(chat_id, files.AGENT_ID, 'chat_id')
        binding = paths.resolve(project_root, home=runtime_home, project_id=project_id)
        paths.require_ready(binding)
        require(binding['registered'], 'project_uninitialized', 'Initialize the managed project first')
        self.root = Path(binding['projectRoot'])
        self.path = Path(binding['runtimeRoot']) / ('conductor-' + chat_id + '.json')
        self.chat_id = chat_id

    def read(self):
        return files.safe_read_json(self.path)

    def update(self, operation):
        with files.file_lock(self.path.with_suffix('.lock')):
            state = self.read()
            result = operation(state)
            state['revision'] += 1
            files.atomic_write_json(self.path, state)
            return copy.deepcopy(result)

    def initialize(self, settings, policy):
        """Captured role settings and authority, not authority inferred from messages."""
        require(policy.get('sandbox') in {'read-only','workspace-write','danger-full-access'},
                'authority_missing', 'Captured sandbox required')
        require(policy.get('approvalPolicy') in {'bypass', 'required'} and policy.get('reference'),
                'authority_missing', 'Captured approval policy and authorization reference required')
        require(settings.get('conversation') and settings.get('work'), 'settings_missing', 'Both role settings required')
        supervision=policy.get('supervision')
        if supervision:
            require(supervision.get('basis') and supervision.get('noProgressObservations',0)>=2 and
                    supervision.get('repeatObservations',0)>=2, 'inspection_policy', 'Evidence-based supervision policy required')
        for config in settings.values():
            provider_for(config.get('model'), config.get('provider'))
        with files.file_lock(self.path.with_suffix('.lock')):
            if self.path.exists():
                state = self.read()
                require(state['settings'] == settings and state['policy'] == policy,
                        'chat_conflict', 'Existing chat retains its settings and authority')
                return self.snapshot()
            state = {'schemaVersion': 1, 'chatId': self.chat_id, 'revision': 0,
                     'settings': copy.deepcopy(settings), 'policy': copy.deepcopy(policy),
                     'messages': [], 'tasks': {}, 'sessions': {}, 'runs': {},
                     'decisions': {}, 'events': [], 'consumers': {}}
            files.atomic_write_json(self.path, state)
        return self.snapshot()

    def _session(self, state, role, config=None, handoff=None):
        config = copy.deepcopy(config or state['settings'][role])
        sid = identity('session')
        value = {'id': sid, 'role': role, 'settings': config, 'agentId': identity('conductor'),
                 'nativeSessionId': None, 'managedCreated': False, 'activeRunId': None, 'handoff': handoff}
        state['sessions'][sid] = value
        return sid

    def receive(self, message):
        def accept(s):
            require(not message.get('sensitive') and not message.get('credentials'),
                    'credential_unsafe', 'Use existing protected input for credentials')
            mid = message.get('id')
            files.validate_id(mid or '', files.AGENT_ID, 'message_id')
            require(isinstance(message.get('text'), str) and message['text'].strip(), 'message_empty', 'Text required')
            kind = message.get('kind')
            require(kind in {'question', 'task', 'rework'}, 'message_kind', 'Explicit routing kind required')
            old = next((m for m in s['messages'] if m['id'] == mid), None)
            if old:
                require(old['inputHash'] == digest(message), 'message_conflict', 'Duplicate message has different content')
                return old
            task_id = message.get('taskId')
            if kind == 'task':
                spec = copy.deepcopy(message.get('task') or {})
                for field in ('goal', 'inputs', 'completionCriteria', 'writeScope', 'dependencies'):
                    require(field in spec, 'task_incomplete', 'Missing task field: ' + field)
                require(all(isinstance(spec[f],str) and spec[f].strip() for f in ('goal','completionCriteria')),
                        'task_invalid', 'Goal and completion criteria must be nonempty text')
                files.validate_id(task_id or 'generated', files.AGENT_ID, 'task_id')
                require(isinstance(spec['dependencies'], list) and isinstance(spec['writeScope'], list),
                        'task_invalid', 'Dependencies and write scope must be lists')
                task_id = task_id or identity('task')
                require(task_id not in s['tasks'], 'task_exists', 'Use rework for an existing task')
                require(all(d in s['tasks'] for d in spec['dependencies']), 'dependency_unknown', 'Unknown dependency')
                sid = self._session(s, 'work')
                s['tasks'][task_id] = {'id': task_id, 'spec': spec, 'revision': 1, 'ownerSessionId': sid,
                                      'status': 'pending', 'results': [], 'checks': None, 'blockers': []}
            elif task_id:
                require(task_id in s['tasks'], 'task_unknown', 'Unknown task')
                task = s['tasks'][task_id]
                require(message.get('taskRevision') == task['revision'], 'stale_revision', 'Reload the current task revision')
                sid = task['ownerSessionId']
                if kind == 'rework':
                    require(not task.get('pendingDecisionId'), 'decision_pending', 'Answer or supersede the pending decision first')
                    active=s['sessions'][sid]['activeRunId']
                    if active and s['runs'][active]['status']=='reserved':
                        s['runs'][active].update(status='cancelled',terminationConfirmed=True)
                        s['sessions'][sid]['activeRunId']=None
                        for prior in s['messages']:
                            if prior.get('runId')==active:
                                prior['status']='superseded'
                        event(s,'superseded:'+active,'execution-superseded',runId=active,taskId=task_id)
                    task['revision'] += 1
                    task['status'] = 'pending'
                    task['checks'] = None
                    task.setdefault('requirements', []).append(message['text'])
            else:
                require(kind == 'question', 'task_required', 'Rework requires an existing task')
                sid = next((v['id'] for v in s['sessions'].values() if v['role'] == 'conversation'), None)
                sid = sid or self._session(s, 'conversation')
            m = {'id': mid, 'inputHash': digest(message), 'text': message['text'], 'kind': kind,
                 'sequence': len(s['messages']) + 1, 'taskId': task_id, 'sessionId': sid,
                 'taskRevision': s['tasks'][task_id]['revision'] if task_id else None,
                 'status': 'queued', 'speaker': message.get('speaker', 'human'),
                 'authority': 'read-only' if kind == 'question' else 'bounded-task'}
            s['messages'].append(m)
            event(s, 'message:' + mid, 'message-received', message= m)
            return m
        return self.update(accept)

    def reserve(self, session_id):
        def claim(s):
            session = s['sessions'][session_id]
            if session['activeRunId']:
                return {'disposition': 'busy', 'run': s['runs'][session['activeRunId']]}
            m = next((m for m in s['messages'] if m['sessionId'] == session_id and m['status'] == 'queued'), None)
            if not m:
                return {'disposition': 'empty'}
            task = s['tasks'].get(m['taskId'])
            if task and m['kind'] != 'question':
                if m['taskRevision'] != task['revision']:
                    m['status'] = 'superseded'
                    return {'disposition': 'superseded', 'messageId': m['id']}
                blockers = [d for d in task['spec']['dependencies'] if s['tasks'][d]['status'] != 'completed']
                if blockers:
                    task.update(status='blocked', blockers=blockers)
                    return {'disposition': 'blocked', 'dependencies': blockers}
                if task.get('pendingDecisionId'):
                    return {'disposition': 'decision', 'decisionId': task['pendingDecisionId']}
            rid = identity('run')
            run = {'id': rid, 'sessionId': session_id, 'messageId': m['id'], 'taskId': m['taskId'],
                   'taskRevision': m['taskRevision'], 'status': 'reserved', 'dispatchId': identity('dispatch'),
                   'managedRunId': None, 'terminationConfirmed': False, 'observations': [], 'result': None}
            s['runs'][rid] = run
            session['activeRunId'] = rid
            m.update(status='reserved', runId=rid)
            if task and m['kind'] != 'question':
                task.update(status='running', blockers=[])
            return {'disposition': 'reserved', 'run': run}
        return self.update(claim)

    def dispatch(self, run_id, backend):
        """backend uses existing submit/send/status and adapter boundary. Never retry an unknown start."""
        def prepare(s):
            run = s['runs'][run_id]
            session = s['sessions'][run['sessionId']]
            require(session['activeRunId'] == run_id, 'run_stale', 'Run no longer owns this session')
            task = s['tasks'].get(run['taskId'])
            m = next(m for m in s['messages'] if m['id'] == run['messageId'])
            if m['kind'] != 'question' and task and s['policy']['approvalPolicy'] == 'required':
                require(task.get('approvedRevision') == run['taskRevision'], 'approval_required', 'Answer the exact task execution decision first')
            require(not task or m['kind'] == 'question' or task['revision'] == run['taskRevision'],
                    'stale_revision', 'Reserved request was superseded')
            first = run['status'] == 'reserved'
            if first:
                run['status'] = 'starting'
            return first, copy.deepcopy({'run': run, 'session': session, 'message': m,
                                         'task': task, 'policy': s['policy']})
        first, request = self.update(prepare)
        # Reservation precedes provider acceptance; lost acceptance is found by the
        # managed dispatch key on recovery. No elapsed-time lease permits a second writer.
        try:
            accepted = backend.submit(request) if first else backend.lookup(request)
        except (OSError, ContractError) as error:
            def failed(s):
                run=s['runs'][run_id]
                detail={'code':getattr(error,'code','start_ack_unknown'),'message':str(error)}
                run['startError']=detail
                run['failureClass']=backend.classify_error(error) if hasattr(backend,'classify_error') else None
                run['failureKind']=('allocation' if detail['code'].startswith(('task_target','task_preparation','task_workspace'))
                                    else 'implementation' if run['failureClass']=='contract' else run['failureClass'] or 'unknown')
                task=s['tasks'].get(run['taskId'])
                if task and task['revision']==run['taskRevision']:
                    task.update(status='blocked',blockers=[detail])
                event(s,'start-error:'+run_id+':'+digest(detail),'execution-start-uncertain',
                      runId=run_id,taskId=run['taskId'],error=detail,nextStep='observe-existing-dispatch')
            self.update(failed)
            raise
        if not accepted:
            return {'disposition': 'waiting', 'reason': 'start-or-termination-unknown', 'runId': run_id}
        def bind(s):
            run = s['runs'][run_id]
            require(not run['managedRunId'] or run['managedRunId'] == accepted['runId'],
                    'run_binding', 'Managed dispatch identity changed')
            run['managedRunId']=accepted['runId']
            if run['status'] not in TERMINAL:
                run['status']=accepted['status']
            s['sessions'][run['sessionId']]['managedCreated'] = True
            if accepted.get('sessionId'):
                s['sessions'][run['sessionId']]['nativeSessionId'] = accepted['sessionId']
            event(s, 'accepted:' + run_id, 'execution-accepted', run=run)
            return run
        return self.update(bind)

    def observe(self, run_id, observation, *, termination_confirmed=False):
        def record(s):
            run = s['runs'][run_id]
            require(observation.get('runId') == run['managedRunId'] and run['managedRunId'],
                    'observation_binding', 'Observation must identify the accepted managed run')
            key = observation.get('id')
            require(isinstance(key, str) and key, 'observation_id', 'Stable observation ID required')
            old = next((o for o in run['observations'] if o['id'] == key), None)
            if old:
                require(old == observation, 'observation_conflict', 'Observation ID changed content')
            else:
                run['observations'].append(copy.deepcopy(observation))
            status = observation.get('status')
            require(status in TERMINAL | {'accepted','queued','starting','running','cancelling'}, 'run_status', 'Invalid execution state')
            require(run['status'] not in TERMINAL or run['status'] == status, 'terminal_conflict', 'Terminal state cannot regress')
            run['status'] = status
            run['failureClass'] = observation.get('failureClass')
            error_code = (observation.get('error') or {}).get('code', '')
            run['failureKind'] = ('allocation' if error_code.startswith(('task_target','task_preparation','task_workspace')) else
                                  'implementation' if run['failureClass']=='contract' else run['failureClass'] or 'unknown')
            if status in TERMINAL:
                run['terminationConfirmed'] = run['terminationConfirmed'] or bool(termination_confirmed)
                termination = run['terminationConfirmed']
                task = s['tasks'].get(run['taskId'])
                m = next(m for m in s['messages'] if m['id'] == run['messageId'])
                if not run['result']:
                    run['result'] = {k: copy.deepcopy(observation.get(k)) for k in ('resultPath','receiptPath','checks','error','taskCompleted')}
                    if task:
                        task['results'].append({'runId': run_id, 'revision': run['taskRevision'], 'kind':m['kind'], **run['result']})
                    event(s, 'terminal:' + run_id, 'execution-ended', runId=run_id, taskId=run['taskId'],
                          taskRevision=run['taskRevision'], speaker=run['sessionId'], result=run['result'])
                if task and task['revision'] == run['taskRevision'] and m['kind'] != 'question':
                    if observation.get('checks') is not None:
                        task['checks'] = observation['checks']
                    task['status'] = ('completed' if task['status']=='completed' or
                                      (status == 'completed' and observation.get('taskCompleted') is True
                                       and task['checks'] == 'passed' and not task.get('pendingDecisionId')) else
                                      'awaiting-acceptance' if status == 'completed' else 'blocked')
                    task['blockers'] = [] if task['status'] == 'completed' else [observation.get('error') or status]
                if termination:
                    session = s['sessions'][run['sessionId']]
                    if session['activeRunId'] == run_id:
                        session['activeRunId'] = None
                    m['status'] = 'ended'
            policy=s['policy'].get('supervision')
            if policy:
                self._inspection_event(s,run_id,policy)
            return run
        return self.update(record)

    def decision(self, run_id, proposal):
        def create(s):
            run = s['runs'][run_id]
            task = s['tasks'][run['taskId']]
            require(task['revision'] == run['taskRevision'], 'decision_stale', 'Task changed')
            for field in ('kind','scope','target','reason','effect','alternatives'):
                require(proposal.get(field), 'decision_incomplete', 'Missing decision field: ' + field)
            require(proposal['kind'] in {'approval','clarification'} and proposal['scope'] in
                    {'task-execution','scope-expansion','external-prerequisite'}, 'decision_invalid', 'Invalid decision')
            if proposal['scope'] == 'task-execution' and s['policy']['approvalPolicy'] == 'bypass':
                return {'disposition': 'already-authorized'}
            require(not proposal.get('credentials'), 'credential_unsafe', 'Use the protected provider input, never chat credentials')
            if proposal.get('requiresCredential'):
                require(proposal.get('protectedInputReference'), 'protected_input_required', 'Reference existing protected input')
            binding = {'taskId': task['id'], 'runId': run_id, 'managedRunId':run['managedRunId'],
                       'sessionId':run['sessionId'], 'taskRevision': task['revision'], 'proposal': proposal}
            did = 'decision-' + digest(binding)[:32]
            d = s['decisions'].setdefault(did, {'id':did, 'questionHash':digest(binding), **binding, 'status':'pending'})
            require(not task.get('pendingDecisionId') or task['pendingDecisionId'] == did,
                    'decision_pending', 'A different decision is already pending')
            task.update(status='blocked', pendingDecisionId=did)
            event(s, did, 'human-decision', decision=d)
            return d
        return self.update(create)

    def answer(self, response):
        def accept(s):
            d = s['decisions'][response['decisionId']]
            for field in ('taskId','runId','taskRevision','questionHash'):
                require(response.get(field) == d[field], 'decision_binding', 'Decision response binding changed')
            require(response.get('actor') == 'human' and response.get('reference') and response.get('answer'),
                    'decision_unauthorized', 'Exact Human response and reference required')
            require(not d['proposal'].get('requiresCredential') or response.get('protectedInputReady') is True,
                    'credential_required', 'Complete existing protected input first; do not include a secret')
            require(not d['proposal'].get('requiresCredential') or response['answer'] in {'ready','declined'},
                    'credential_unsafe', 'Credential response must be ready or declined')
            if d.get('response'):
                require(d['response'] == response, 'decision_conflict', 'Decision already answered differently')
                return d
            task = s['tasks'][d['taskId']]
            require(task['revision'] == d['taskRevision'] and task.get('pendingDecisionId') == d['id'],
                    'decision_stale', 'Decision no longer current')
            require(response.get('answer') in {'approved','ready','declined'} or d['proposal']['kind'] == 'clarification',
                    'decision_answer', 'Approval needs approved or declined')
            d.update(status='answered', response=copy.deepcopy(response))
            task['pendingDecisionId'] = None
            if response['answer'] == 'declined':
                task.update(status='blocked', blockers=['human-declined'])
                run=s['runs'][d['runId']]
                if run['status']=='reserved':
                    run.update(status='cancelled',terminationConfirmed=True)
                    session=s['sessions'][run['sessionId']]
                    if session['activeRunId']==run['id']:
                        session['activeRunId']=None
                    for m in s['messages']:
                        if m.get('runId')==run['id']:
                            m['status']='declined'
            else:
                task['approvedRevision'] = task['revision']
                # No authority inferred from prose: the exact answered proposal is handed to the owner.
                if s['runs'][d['runId']]['status'] != 'reserved':
                    self._queue_continuation(s, task, 'answer-' + d['id'], json.dumps(d, ensure_ascii=False))
                else:
                    task['status'] = 'pending'
            event(s, 'answered:' + d['id'], 'decision-answered', decision=d)
            return d
        return self.update(accept)

    def _queue_continuation(self, s, task, mid, text):
        s['messages'].append({'id':mid, 'text':text, 'kind':'rework', 'sequence':len(s['messages'])+1,
                              'taskId':task['id'], 'sessionId':task['ownerSessionId'], 'taskRevision':task['revision'],
                              'status':'queued','speaker':'human','authority':'bounded-task'})
        task['status'] = 'pending'

    def switch_provider(self, task_id, revision, settings):
        provider_for(settings.get('model'), settings.get('provider'))
        def switch(s):
            task = s['tasks'][task_id]
            require(task['revision'] == revision, 'stale_revision', 'Reload current task')
            old = s['sessions'][task['ownerSessionId']]
            require(not old['activeRunId'], 'writer_uncertain', 'Confirm prior writer termination before handoff')
            require(not task.get('pendingDecisionId'), 'decision_pending', 'Resolve current decision before switching')
            require(old['settings'].get('provider','codex') != settings.get('provider','codex'), 'provider_same', 'Provider must change')
            handoff = {'fromSessionId':old['id'], 'task':copy.deepcopy(task), 'policy':s['policy'],
                       'decisions':[d for d in s['decisions'].values() if d['taskId']==task_id],
                       'requirements':task.get('requirements',[]), 'results':task['results']}
            sid = self._session(s, 'work', settings, copy.deepcopy(handoff))
            task['ownerSessionId'] = sid
            for m in s['messages']:
                if m['taskId'] == task_id and m['status'] == 'queued':
                    m['sessionId'] = sid
            event(s, 'handoff:' + sid, 'provider-handoff', taskId=task_id, sessionId=sid, handoff=handoff)
            return s['sessions'][sid]
        return self.update(switch)

    def retry(self, task_id, revision, *, reference, failure_class, max_attempts=1):
        def retry(s):
            task = s['tasks'][task_id]
            require(task['revision'] == revision, 'stale_revision', 'Reload task')
            require(not s['sessions'][task['ownerSessionId']]['activeRunId'], 'writer_uncertain', 'Previous writer not confirmed ended')
            last = next((r for r in reversed(list(s['runs'].values())) if r['taskId']==task_id), None)
            require(last and last['status'] in TERMINAL and last['terminationConfirmed'], 'retry_invalid', 'No ended execution')
            require(last.get('failureClass') == failure_class, 'retry_class_conflict', 'Retry must use the recorded runtime failureClass')
            require(last['status'] in {'failed','runtime-error'}, 'retry_invalid', 'Only failed executions may retry')
            authority=s['policy'].get('retryAuthority') or {}
            require(reference == authority.get('reference') and failure_class in authority.get('classes',[])
                    and max_attempts <= authority.get('maxAttempts',0),
                    'retry_unauthorized', 'Retry exceeds captured Human retry authority')
            require(reference and failure_class in {'contract','transient'} and max_attempts > 0,
                    'retry_unauthorized', 'Only a bounded authorized contract/transient retry is allowed')
            require(task.get('retryCount',0) < max_attempts, 'retry_limit', 'Retry budget exhausted')
            task['retryCount'] = task.get('retryCount',0)+1
            self._queue_continuation(s,task,identity('retry'),'Authorized repair/retry: '+reference)
            return task
        return self.update(retry)

    def inspect(self, run_id, policy):
        """One event/observation trigger, no polling loop or automatic stop."""
        require(policy.get('basis') and policy.get('noProgressObservations',0) >= 2 and
                policy.get('repeatObservations',0) >= 2, 'inspection_policy', 'Evidence-based observation thresholds required')
        return self.update(lambda s: self._inspection_event(s,run_id,policy))

    def _inspection_event(self,s,run_id,policy):
        run = s['runs'][run_id]
        task = s['tasks'].get(run['taskId'])
        obs = run['observations']
        # Heartbeats/tokens are intentionally not progress evidence.
        evidence = [{k:o[k] for k in ('id','source','artifacts','changes','checks','blocker','goalEvidence','action','error','milestoneExceeded','offGoal') if k in o} for o in obs]
        meaningful = [e for e in evidence if e.get('goalEvidence') and (e.get('artifacts') or e.get('changes') or e.get('checks')=='passed')]
        latest = evidence[-1] if evidence else {}
        reason = ('milestone-exceeded' if latest.get('milestoneExceeded') else
                  'repeated-observation' if len(obs)>=policy['noProgressObservations'] else 'observation')
        progress_hashes = [digest({k:e.get(k) for k in ('artifacts','changes','checks','goalEvidence')}) for e in meaningful]
        tail = evidence[-policy['noProgressObservations']:]
        repeats = evidence[-policy['repeatObservations']:]
        stagnant = (len(tail)>=policy['noProgressObservations'] and
                    len({digest({k:e.get(k) for k in ('artifacts','changes','checks','goalEvidence')}) for e in tail})==1)
        repeated = (len(repeats)>=policy['repeatObservations'] and all(e.get('action') or e.get('error') for e in repeats)
                    and len({digest((e.get('action'),e.get('error'))) for e in repeats})==1)
        if latest.get('offGoal') and latest.get('goalEvidence'):
            assessment='direction-deviation'
        elif latest.get('blocker') or (run['status'] in TERMINAL and not run['terminationConfirmed']):
            assessment='waiting'
        elif (stagnant or repeated) and (meaningful or repeated):
            assessment='suspected-stall'
        elif latest in meaningful and (len(progress_hashes)==1 or len(set(progress_hashes))>1):
            assessment='progressing'
        else:
            assessment='indeterminate'
        uncertainty=[] if meaningful else ['No goal-linked output/change/check evidence']
        if run['status'] in TERMINAL and not run['terminationConfirmed']:
            uncertainty.append('Previous writer termination is unconfirmed')
        if task and task['revision']!=run['taskRevision']:
            uncertainty.append('Observation belongs to a superseded task revision')
        report = {'taskId':run['taskId'],'runId':run_id,'taskRevision':run['taskRevision'],
                  'originalGoal':task['spec']['goal'] if task else 'Conversation',
                  'completionCriteria':task['spec']['completionCriteria'] if task else None,
                  'evidenceBasis':'reported goal-linked evidence; not independent verification',
                  'reason':reason, 'assessment':assessment, 'actualProgress':meaningful,
                  'uncertainty':uncertainty,
                  'problems':[e.get('blocker') or e.get('error') for e in evidence if e.get('blocker') or e.get('error')],
                  'action':'recorded-and-reported', 'nextStep':'continue' if assessment=='progressing' else 'request-owner-evidence',
                  'humanDecisionRequired': bool(task and task.get('pendingDecisionId')),
                  'policy':policy,'evidence':evidence}
        signature={'assessment':assessment,'reason':reason,'taskRevision':run['taskRevision'],
                   'latest':{k:v for k,v in latest.items() if k!='id'},
                   'progress':sorted(set(progress_hashes)), 'uncertainty':uncertainty,
                   'decisionRequired':report['humanDecisionRequired'],'policy':policy}
        key='inspection:'+run_id+':'+digest(signature)
        return event(s,key,'inspection-report',report=report,speaker='conductor',taskId=run['taskId'])

    def reports(self, consumer, ack=None):
        def read(s):
            cursor=s['consumers'].get(consumer,0)
            if ack is not None:
                require(isinstance(ack,int) and cursor <= ack <= len(s['events']), 'ack_invalid', 'Invalid durable cursor')
                s['consumers'][consumer]=ack
                cursor=ack
            return {'schemaVersion':1,'chatId':self.chat_id,'cursor':cursor,
                    'events':[e for e in s['events'] if e['sequence']>cursor]}
        return self.update(read) if ack is not None else read(self.read())

    def snapshot(self):
        s=self.read()
        rows=[]
        for task in s['tasks'].values():
            session=s['sessions'][task['ownerSessionId']]
            rows.append({**task,'worker':session,'kanban': 'done' if task['status']=='completed' else
                         'blocked' if task['status']=='blocked' else 'remaining'})
        return {'schemaVersion':1,'kind':'conductor','chatId':self.chat_id,'revision':s['revision'],
                'tasks':rows,'sessions':list(s['sessions'].values()),'messages':s['messages'],
                'runs':list(s['runs'].values()),'decisions':list(s['decisions'].values()),
                'lastEventSequence':len(s['events'])}
