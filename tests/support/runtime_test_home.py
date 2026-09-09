"""One isolated runtime home for test processes and their fixture children."""
import atexit
import json
import os
import tempfile
from pathlib import Path

_temporary = tempfile.TemporaryDirectory(prefix='af-test-home-')
os.environ['AGENT_FACTORY_HOME'] = str(Path(_temporary.name) / 'runtime')
os.environ.pop('AGENT_FACTORY_PARENT_STATE', None)
os.environ.pop('CODEX_THREAD_ID', None)
os.environ['AGENT_FACTORY_EXECUTION_POLICY'] = json.dumps({
    'schemaVersion': 1, 'sandboxPolicy': {'type': 'danger-full-access', 'network_access': True}, 'approvalPolicy': 'never'
})
atexit.register(_temporary.cleanup)


def policy(sandbox, project_root=None, *, network=False, approval='never'):
    """Explicit permission evidence for fake-process fixtures, never a runtime default."""
    selected = {'type': sandbox, 'network_access': True if sandbox == 'danger-full-access' else network}
    if sandbox == 'workspace-write':
        selected.update(writable_roots=[str(project_root)], exclude_tmpdir_env_var=False, exclude_slash_tmp=False)
    return {'schemaVersion': 1, 'sandboxPolicy': selected, 'approvalPolicy': approval}
