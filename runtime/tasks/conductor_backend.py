"""Bridge to the existing exec lifecycle and provider adapters, not a provider launcher."""
from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from storage import files
from storage.errors import ContractError


class ManagedBackend:
    def __init__(self, conductor):
        self.conductor = conductor
        self.exec_path = files.PLUGIN_ROOT / 'scripts' / 'exec.py'
        from tasks.conductor_workspaces import WorkUnits
        self.work_units = WorkUnits(conductor.root, conductor.path)
        from tasks.conductor_workflows import Workflows
        self.workflows = Workflows(self)

    def call(self, arguments):
        binding = files.runtime_paths.arguments(self.conductor.root)
        result = subprocess.run([sys.executable,str(self.exec_path),*arguments,
                                 '--project-root',str(self.conductor.root),*binding],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        try:
            value=json.loads(result.stdout)
        except ValueError as error:
            raise ContractError('managed_response_invalid','Managed runtime returned no JSON acceptance') from error
        if result.returncode or value.get('kind')=='error':
            detail=value.get('error') or {}
            raise ContractError(detail.get('code','managed_failure'),detail.get('message',result.stderr))
        return value

    def submit(self, request):
        if request.get('verification'):
            return self.workflows.start(request)
        run,session,message=request['run'],request['session'],request['message']
        config=session['settings']
        if session.get('area'):
            from tasks import domains
            area = session['area']
            # Membership precedes external session creation, respecting Human placements.
            domains.assign_subdomain(self.conductor.path.parent, session['agentId'], area['domainId'], area['subdomainId'],
                                     'ai', 'queue-dispatch:' + run['dispatchId'])
        # This native session belongs solely to the conductor. A provider handoff
        # creates a fresh agent, preserving the previous managed session untouched.
        command='send' if session['managedCreated'] else 'submit'
        arguments=[command,'--agent',session['agentId'],'--actor','main','--dispatch-id',run['dispatchId']]
        if command=='submit' and self.conductor.chat_id == 'conductor-queue' and not session.get('area'):
            raise ContractError('area_required', 'Queue hires require domain and child-area membership before session creation')
        if command=='submit':
            arguments.extend(['--role','work' if session['role']=='work' else 'main'])
        policy=request['policy']
        sandbox=policy['sandbox']
        arguments.extend(['--sandbox',sandbox,'--approval-policy','never',
                          '--human-approval-policy',policy['approvalPolicy'],
                          '--task-mode','work' if session['role']=='work' else 'direct'])
        for key in ('model','provider','reasoningEffort'):
            if config.get(key) is not None:
                flag={'reasoningEffort':'reasoning-effort'}.get(key,key)
                arguments.extend(['--'+flag,str(config[key])])
        if config.get('executable') and command=='submit':
            flag={'codex':'codex','claude':'claude','antigravity':'agy'}[config.get('provider','codex')]
            arguments.extend(['--'+flag,config['executable']])
        if config.get('fast') is not None and config.get('provider','codex')=='codex':
            arguments.append('--fast' if config['fast'] else '--no-fast')
        # Runtime-owned exact input file keeps arbitrary text out of command parsing.
        path=self.conductor.path.with_name(run['dispatchId']+'.request.md')
        context={'message':message,'task':request['task'],'policy':policy,'handoff':session['handoff']}
        files.atomic_write(path,json.dumps(context,ensure_ascii=False,indent=2).encode('utf-8'))
        if session['role']=='work':
            if request['task']['spec'].get('workProfile'):
                arguments.extend(['--work-profile', request['task']['spec']['workProfile']])
            task=request['task']
            flow_id='conductor-'+hashlib.sha256((self.conductor.chat_id+':'+task['id']).encode()).hexdigest()[:32]
            announcement_request=self.conductor.path.with_name(flow_id+'.request.md')
            files.atomic_write(announcement_request,json.dumps(task['spec'],ensure_ascii=False,sort_keys=True).encode())
            document={'id':flow_id,'title':task['spec']['goal'],
                      'tasks':[{'id':task['id'],'title':task['spec']['goal'],
                                'description':json.dumps(task['spec'],ensure_ascii=False,sort_keys=True),
                                'completionCriteria':task['spec']['completionCriteria'],
                                'requestFile':str(announcement_request)}]}
            task_path=path.with_suffix('.tasks.json')
            files.atomic_write_json(task_path,document)
            if os.environ.get('AGENT_FACTORY_PARENT_STATE'):
                # Preserve the existing Main announcement gate; do not mark this
                # explicit task list as a brief to evade the accepted contract.
                self.call(['announce-tasks','--task-list-file',str(task_path)])
            arguments.extend(['--task-list-file',str(task_path),'--task-id',task['id']])
        if message['kind']=='question':
            binding={'schemaVersion':'0.1.0','bindings':[{'capabilityId':'conductor-question',
                     'authority':{'kind':'host-capability','reference':policy['reference']},
                     'invocationRoute':'conductor question response',
                     'exactTarget':message['taskId'] or self.conductor.chat_id,
                     'allowedEffects':['read','respond'],'allowedScopes':['task-execution'],
                     'approvalReference':policy['reference']}]}
            binding_path=path.with_suffix('.capabilities.json')
            files.atomic_write_json(binding_path,binding)
            arguments.extend(['--capability-binding-file',str(binding_path)])
        if session['role'] == 'work':
            workspace_file = self.work_units.prepare(request)
            if workspace_file:
                arguments.extend(['--task-workspace-file', str(workspace_file)])
        arguments.extend(['--request-file',str(path)])
        result=self.call(arguments)
        return result.get('run',result)

    def workspace_action(self, ctx, action, authorization):
        import exec as runtime
        external = ctx['external']
        work = runtime.find_run(self.conductor.root, external['agentId'], external['runId'])
        receipt = runtime.validate_receipt(self.conductor.root, work, agent_id=external['agentId'], run_id=external['runId']) if action == 'integrate' else None
        return self.work_units.action(ctx['delegationId'], action, work=work, receipt=receipt, authorization=authorization)

    def workspace(self, task_id):
        return self.work_units.snapshot(task_id)

    def question(self, external):
        if external.get('workflow'):
            state = self.workflows.observe(external)['workflowState']
            decision = state.get('pendingDecision') or {}
            return {'text': decision.get('question') or decision.get('reason') or str(state.get('controlPlaneError')), 'decisionKind': decision.get('kind', 'clarification'), 'decisionScope': decision.get('scope'), 'decision': decision}
        import exec as runtime
        raw = runtime.find_run(self.conductor.root, external['agentId'], external['runId'])
        text = runtime.safe_read_bytes(Path(raw['resultPath']), None).decode('utf-8') if raw.get('resultPath') else raw.get('response')
        return {'text': text, 'resultPath': raw.get('resultPath'), 'decisionKind': raw.get('decisionKind'), 'decisionScope': raw.get('decisionScope')}

    def completion(self, external):
        if external.get('workflow'):
            return self.workflows.completion(external)
        import exec as runtime
        raw = runtime.find_run(self.conductor.root, external['agentId'], external['runId'])
        receipt = runtime.validate_receipt(self.conductor.root, raw, agent_id=external['agentId'], run_id=external['runId'])
        return {'resultPath': raw.get('resultPath'), 'receiptPath': raw.get('receiptPath'), 'checks': receipt['tests']}

    def health(self, external):
        if external.get('workflow'):
            state = self.workflows.observe(external)['workflowState']
            stopped = not state.get('currentChild') and not state.get('stopPending')
            if state.get('currentChild') and state['status'] in ('needs-human-decision','runtime-error','failed','cancelled'):
                import exec as runtime
                from runs.deletion import require_ended
                child = state['currentChild']
                raw = runtime.find_run(self.conductor.root, child['agentId'], child['runId'])
                require_ended(runtime, raw)
                stopped = True
            return {'stopped': stopped, 'zombie': False}
        import exec as runtime
        from runs.deletion import require_ended
        raw = runtime.find_run(self.conductor.root, external['agentId'], external['runId'])
        stopped = False
        try:
            require_ended(runtime, raw)
            stopped = True
        except ContractError:
            pass
        from tasks.workspaces import run_owner_evidence
        session = runtime.load_session(self.conductor.root, external['agentId'])
        return {'stopped': stopped, 'zombie': raw.get('status') in ('running', 'starting') and run_owner_evidence(runtime, raw, self.conductor.root) == 'inactive',
                'heartbeatStale': runtime.heartbeat_stale(raw, session), 'progress': raw.get('progressEvidence')}

    def status(self, external):
        if external.get('workflow'):
            return self.workflows.observe(external)
        return self.call(['status', '--agent', external['agentId'], '--run-id', external['runId']]).get('run') or {}

    def classify_error(self,error):
        from loop import failure_class
        return failure_class({'code':getattr(error,'code','start_ack_unknown')})

    def lookup(self, request):
        if request.get('verification'):
            return self.workflows.lookup(request)
        try:
            value=self.call(['status','--agent',request['session']['agentId'],
                             '--dispatch-id',request['run']['dispatchId']])
        except ContractError as error:
            if error.code=='dispatch_not_found':
                return None
            raise
        return value.get('run',value)

    def observe(self, run_id, evidence=None):
        state=self.conductor.read()
        run=state['runs'][run_id]
        session=state['sessions'][run['sessionId']]
        value=self.call(['status','--agent',session['agentId'],'--run-id',run['managedRunId']])['run']
        # The same process/containment evidence used by existing lifecycle guards.
        import exec as runtime
        from runs.deletion import require_ended
        from loop import failure_class
        raw=runtime.find_run(self.conductor.root,session['agentId'],run['managedRunId'])
        stopped=False
        if value['status'] in {'completed','failed','cancelled','runtime-error','needs-human-decision'}:
            try:
                require_ended(runtime,raw)
                stopped=True
            except ContractError:
                pass
        evidence=evidence or raw.get('progressEvidence') or {}
        if evidence:
            if evidence.get('runId') != run['managedRunId'] or evidence.get('taskRevision') != run['taskRevision'] or not evidence.get('source'):
                raise ContractError('evidence_binding','Progress evidence requires managed run, task revision and source reference')
        if raw['status']=='completed' and raw.get('role')=='work':
            try:
                receipt=runtime.validate_receipt(self.conductor.root,raw,agent_id=session['agentId'],run_id=raw['runId'])
            except ContractError:
                receipt=None
            if not receipt:
                evidence={**evidence,'taskCompleted':False}
            if receipt:
                tests=receipt.get('tests') or {}
                evidence={**evidence,'source':raw['receiptPath'],'artifacts':[raw['resultPath']], 'changes':receipt.get('changedPaths',[]),
                          'checks':evidence.get('checks','reported' if tests.get('run') is True else 'not-run'),
                          'goalEvidence':request_goal(state,run), 'taskCompleted':True}
        observation={'id': 'managed-'+hashlib.sha256(json.dumps([raw.get('updatedAt'),raw['status'],stopped,evidence],sort_keys=True).encode()).hexdigest(),
                     'runId':value['runId'],'status':value['status'],
                     'resultPath':value.get('resultPath'),'receiptPath':value.get('receiptPath'),
                     'error':value.get('error'), 'failureClass':failure_class(value.get('error')),
                     **{k:evidence[k] for k in ('source','artifacts','changes','checks','goalEvidence','blocker','action','offGoal','milestoneExceeded','taskCompleted') if k in evidence}}
        return self.conductor.observe(run_id,observation,termination_confirmed=stopped)


def request_goal(state,run):
    task=state['tasks'].get(run['taskId'])
    return task['spec']['completionCriteria'] if task else 'Conversation result'
