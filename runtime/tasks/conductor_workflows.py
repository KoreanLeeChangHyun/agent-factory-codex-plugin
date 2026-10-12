"""Adapter to loop.py; the existing loop owns Work/Verification/revision dispatch."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from storage import files
from storage.errors import ContractError


class Workflows:
    def __init__(self, backend):
        self.backend = backend
        self.root = backend.conductor.root
        self.path = backend.conductor.path

    def call(self, argv):
        completed = subprocess.run([sys.executable, str(files.PLUGIN_ROOT / 'scripts' / 'loop.py'), *argv,
                                    '--project-root', str(self.root), *files.runtime_paths.arguments(self.root)],
                                   capture_output=True, text=True, stdin=subprocess.DEVNULL)
        try:
            value = json.loads(completed.stdout)
        except ValueError as error:
            raise ContractError('workflow_response_invalid', 'Managed loop returned no JSON') from error
        if completed.returncode or value.get('kind') == 'error':
            detail = value.get('error') or {}
            raise ContractError(detail.get('code', 'workflow_failure'), detail.get('message', completed.stderr))
        return value

    def lookup(self, request):
        marker = self.path.with_name(request['run']['dispatchId'] + '.workflow.json')
        if marker.exists():
            return files.safe_read_json(marker)
        # Recover the canonical acceptance even if writing the local acknowledgement failed.
        accepted = []
        expected_hash = hashlib.sha256(json.dumps(request['task']['spec'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        for path in (self.path.parent / 'agents' / request['session']['agentId'] / 'loops').glob('*/state.json'):
            state = files.safe_read_json(path)
            if state.get('acceptanceId') != request['run']['dispatchId']:
                continue
            if state.get('acceptedRequestHash', state.get('originalRequestHash')) != expected_hash or state.get('verificationAgentId') != request['verification']['agentId']:
                raise ContractError('workflow_acceptance_conflict', 'This dispatch already has a different canonical acceptance')
            accepted.append({'agentId': request['session']['agentId'], 'runId': state['loopId'], 'loopId': state['loopId'], 'dispatchId': request['run']['dispatchId'], 'workflow': True})
        if len(accepted) > 1:
            raise ContractError('workflow_acceptance_conflict', 'Multiple canonical acceptances need reconciliation')
        return accepted[0] if accepted else None

    def start(self, request):
        session, task, policy = request['session'], request['task'], request['policy']
        spec = task['spec']
        verifier = request.get('verification')
        if not verifier or verifier['agentId'] == session['agentId']:
            raise ContractError('verification_independence', 'A distinct reserved verifier is required')
        for selected in (session, verifier):
            area = selected['area']
            from tasks import domains
            domains.assign_subdomain(self.path.parent, selected['agentId'], area['domainId'], area['subdomainId'], 'ai', 'queue-dispatch:' + request['run']['dispatchId'])
        document_id = 'conductor-' + hashlib.sha256(task['id'].encode()).hexdigest()[:32]
        body = self.path.with_name(request['run']['dispatchId'] + '.workflow-request.md')
        files.atomic_write(body, json.dumps(spec, ensure_ascii=False, sort_keys=True).encode())
        document = {'id': document_id, 'title': spec['goal'], 'tasks': [{'id': task['id'], 'title': spec['goal'],
                    'description': json.dumps(spec, ensure_ascii=False, sort_keys=True), 'completionCriteria': spec['completionCriteria'],
                    'requestFile': str(body), 'workAgentId': session['agentId'], 'verificationAgentId': verifier['agentId']}]}
        if spec.get('workspace'):
            document['tasks'][0]['workspace'] = spec['workspace']
        task_file = body.with_suffix('.tasks.json')
        files.atomic_write_json(task_file, document)
        import os
        if os.environ.get('AGENT_FACTORY_PARENT_STATE'):
            self.backend.call(['announce-tasks', '--task-list-file', str(task_file)])
        argv = ['start', '--work-agent', session['agentId'], '--verification-agent', verifier['agentId'],
                '--acceptance-id', request['run']['dispatchId'], '--task-list-file', str(task_file), '--task-id', task['id'],
                '--request-file', str(body), '--task-mode', 'work-verification', '--work-profile', spec.get('workProfile', 'work'),
                '--sandbox', policy['sandbox'], '--approval-policy', 'never']
        if spec.get('workIsolation'):
            argv.append('--work-isolation')
        for name, selected in (('work', session), ('verification', verifier)):
            settings = selected['settings']
            from execution.policy import normalize
            sandbox = {'type': settings.get('sandbox', policy['sandbox'])}
            if sandbox['type'] == 'workspace-write':
                sandbox['writable_roots'] = [str(self.root)]
            exact_policy = normalize({'schemaVersion': 1, 'sandboxPolicy': sandbox, 'approvalPolicy': 'never'})
            policy_file = body.with_name(body.stem + '.' + name + '.policy.json')
            files.atomic_write_json(policy_file, exact_policy)
            argv.extend(['--' + name + '-execution-policy-file', str(policy_file), '--' + name + '-human-approval-policy', settings.get('approvalPolicy', policy['approvalPolicy'])])
            argv.extend(['--' + name + '-model', settings['model']])
            if settings.get('provider') is not None:
                argv.extend(['--' + name + '-provider', settings['provider']])
            if settings.get('reasoningEffort') is not None:
                argv.extend(['--' + name + '-reasoning-effort', settings['reasoningEffort']])
            if settings.get('fast') is not None:
                argv.append('--' + name + '-fast' if settings['fast'] else '--no-' + name + '-fast')
        # Explicit captured provider/model are passed through the canonical loop unchanged.
        state = self.call(argv)
        value = {'agentId': session['agentId'], 'runId': state['loopId'], 'loopId': state['loopId'],
                 'dispatchId': request['run']['dispatchId'], 'workflow': True}
        files.atomic_write_json(self.path.with_name(request['run']['dispatchId'] + '.workflow.json'), value)
        return value

    def observe(self, external):
        state = self.call(['status', '--work-agent', external['agentId'], '--loop-id', external['loopId']])
        child = state.get('currentChild') or {}
        stage = 'waiting-result'
        if child.get('role') == 'verification':
            stage = 'verifying'
        elif state.get('revisionCount', 0):
            stage = 'revision-waiting'
        if (state.get('controlCenter') or {}).get('lastVerificationDecision') == 'pass' and state['status'] == 'completed':
            stage = 'verifying'  # Pass is published only after exact receipts validate.
        elif state.get('humanSkip'):
            stage = 'skipped-by-human'
        elif (state.get('controlCenter') or {}).get('lastVerificationDecision') == 'fail':
            stage = 'revision-waiting'
        status = {'active': 'running'}.get(state['status'], state['status'])
        if state.get('integrationWait'):
            status = 'running'
        stages = ((state.get('controlCenter') or {}).get('tasks') or [{}])[0].get('stages') or {}
        implementation = (stages.get('work') or {}).get('runStatus') or (stages.get('work') or {}).get('processedStatus')
        return {'activeRole': child.get('role'), 'activeStatus': child.get('status'), 'implementationState': implementation,
                'runId': external['runId'], 'status': status, 'workflowState': state,
                'verificationState': stage, 'binding': {'taskId': (state.get('workflow') or {}).get('tasks', [{}])[0].get('id'),
                'workAgentId': state['workAgentId'], 'workRunId': state.get('latestWorkRunId'),
                'verificationAgentId': state['verificationAgentId'], 'verificationRunId': state.get('latestVerificationRunId')}}

    def completion(self, external):
        import exec as runtime
        observed = self.observe(external)
        state = observed['workflowState']
        if state['status'] != 'completed':
            raise ContractError('workflow_incomplete', 'The canonical loop has not completed')
        work = runtime.find_run(self.root, state['workAgentId'], state['latestWorkRunId'])
        receipt = runtime.validate_receipt(self.root, work, agent_id=state['workAgentId'], run_id=state['latestWorkRunId'])
        result = Path(work['resultPath'])
        binding = {**observed['binding'], 'humanSkip': state.get('humanSkip'), 'resultRevision': hashlib.sha256(result.read_bytes()).hexdigest(), 'workReceiptPath': work['receiptPath'], 'resultPath': work['resultPath']}
        if not state.get('humanSkip'):
            verification = runtime.find_run(self.root, state['verificationAgentId'], state['latestVerificationRunId'])
            verified = runtime.validate_receipt(self.root, verification, agent_id=state['verificationAgentId'], run_id=state['latestVerificationRunId'])
            if verified['decision'] != 'pass' or verification.get('verifiedWorkRunId') != work['runId']:
                raise ContractError('verification_binding_invalid', 'Pass must verify this exact Work run')
            binding['verificationReceiptPath'] = verification['receiptPath']
        return {'resultPath': work['resultPath'], 'receiptPath': work['receiptPath'], 'checks': receipt['tests'],
                'verificationState': 'skipped-by-human' if state.get('humanSkip') else 'pass', 'binding': binding}

    def answer(self, external, text, reference, expected_decision=None):
        state = self.observe(external)['workflowState']
        decision = state.get('pendingDecision')
        if not decision:
            raise ContractError('workflow_decision_invalid', 'No exact managed decision is pending; use the recorded loop control for revision-limit or environment faults')
        if expected_decision and any(decision.get(k) != expected_decision.get(k) for k in ('id','questionHash','runId')):
            raise ContractError('workflow_decision_stale', 'This answer names a superseded managed question')
        if not decision:
            raise ContractError('workflow_decision_invalid', 'No exact managed decision is pending')
        response = {'decisionId': decision['id'], 'questionHash': decision['questionHash'], 'taskId': decision['taskBinding']['taskId'], 'runId': decision['runId'], 'loopId': state['loopId'], 'projectRoot': state['projectRoot'], 'answer': text, 'authorizationReference': reference, 'evidence': 'Exact Human answer received through queue'}
        return self.call(['answer', '--work-agent', external['agentId'], '--loop-id', external['loopId'], '--actor', 'human',
                          '--authorization-reference', reference, '--decision-evidence', response['evidence'], '--response-json', json.dumps(response)])

    def cancel(self, external, reference):
        return self.call(['close', '--work-agent', external['agentId'], '--loop-id', external['loopId'], '--actor', 'human',
                          '--authorization-reference', reference, '--decision-evidence', 'Human cancelled this exact queue request'])
