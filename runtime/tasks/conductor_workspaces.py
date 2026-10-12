"""Queue adapter for the existing task-owned Work Unit lifecycle.

No automatic commit, integration or cleanup. Those effects require an explicit
operator action and exact delegation; failures preserve the state and workspace.
"""
import hashlib
from pathlib import Path

from storage import files
from storage.errors import ContractError
from tasks import workspaces
from tasks.conductor_queue import digest
from tasks.conductor_intents import scope_paths


class WorkUnits:
    def __init__(self, root, queue_path):
        self.root, self.queue_path = Path(root), Path(queue_path)

    def state_path(self, task_id):
        return self.queue_path.parent / 'worktrees' / ('cq-' + task_id) / 'state.json'

    def prepare(self, request):
        import exec as runtime
        task = request['task']
        plan = task['spec'].get('workspace')
        if plan is None:
            return None  # Existing sequential shared-checkout submission.
        path = self.state_path(task['id'])
        path.parent.mkdir(parents=True, exist_ok=True)
        with files.file_lock(path.with_suffix('.lock')):
            if path.exists():
                state = files.safe_read_json(path)
                if state['requestHash'] != digest(task):
                    raise ContractError('task_workspace_binding', 'Recovered workspace belongs to a different task spec')
            else:
                normalized = workspaces.plan(self.root, plan, isolation=plan['mode'] == 'code')
                if normalized['mode'] == 'code':
                    roots = [unit['relativePath'] for unit in normalized['repositories']]
                    scopes = scope_paths(task['spec'].get('writeScope', ['.']))
                    if any(not any(root == '.' or scope == root or scope.startswith(root + '/') for root in roots) for scope in scopes):
                        raise ContractError('task_workspace_scope', 'Code write scope must be contained in the selected repositories')
                flow = 'conductor-' + hashlib.sha256(('conductor-queue:' + task['id']).encode()).hexdigest()[:32]
                state = {'schemaVersion': 1, 'kind': 'conductor-queue-workspace', 'loopId': 'cq-' + task['id'], 'projectRoot': str(self.root), 'statePath': str(path),
                         'workAgentId': request['session']['agentId'], 'requestHash': digest(task),
                         'execution': {'workspacePlan': normalized, 'taskMode': 'work',
                             'taskBinding': {'taskId': task['id'], 'workflowId': flow, 'workAgentId': request['session']['agentId']}}}
            save = lambda: files.atomic_write_json(path, state)
            save()
            try:
                workspaces.prepare(runtime, state, path, save)
                value = state.get('taskWorkspaces', {}).get(task['id'])
                if value:
                    value.pop('error', None)
                    save()
            except (ContractError, OSError) as error:
                value = state.get('taskWorkspaces', {}).get(task['id'])
                if value:
                    value['phase'] = 'creation-failed'
                    value['error'] = {'code': getattr(error, 'code', 'workspace_error'), 'message': str(error)}
                    save()
                raise
            return Path(state['execution']['taskWorkspacePath'])

    def snapshot(self, task_id):
        path = self.state_path(task_id)
        if not path.exists():
            return None
        state = files.safe_read_json(path)
        return state.get('taskWorkspaces', {}).get(task_id) or state.get('taskContexts', {}).get(task_id)

    def action(self, task_id, action, *, work=None, receipt=None, authorization=None):
        import exec as runtime
        if not authorization:
            raise ContractError('authority_missing', 'Exact operator authorization reference required')
        path = self.state_path(task_id)
        with files.file_lock(path.with_suffix('.lock')):
            state = files.safe_read_json(path)
            value = state.get('taskWorkspaces', {}).get(task_id)
            if not value:
                raise ContractError('task_workspace_missing', 'This task has no isolated Work Unit')
            save = lambda: files.atomic_write_json(path, state)
            state['operatorAuthorization'] = {'action': action, 'reference': authorization, 'taskId': task_id}
            save()
            try:
                if action == 'integrate':
                    result = workspaces.integrate(runtime, state, work, receipt, save, cleanup_after=False)
                elif action == 'cleanup':
                    workspaces.cleanup(runtime, state, value, save)
                    result = {'status': 'cleanup-pending' if any(u.get('cleanupPending') for u in value['repositories']) else 'cleaned'}
                else:
                    raise ContractError('command_unknown', 'Select integrate or cleanup')
                return {**result, 'workspace': self.snapshot(task_id)}
            except (ContractError, OSError) as error:
                value['error'] = {'code': getattr(error, 'code', 'workspace_error'), 'message': str(error)}
                save()
                raise
