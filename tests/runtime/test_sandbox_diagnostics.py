"""Host diagnostics are portable; mocked hosts do not prove native execution."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'skills/agent/scripts/exec.py'
SPEC = importlib.util.spec_from_file_location('sandbox_diagnostics', ROOT / 'skills/agent/runtime/sandbox_diagnostics.py')
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


@pytest.mark.parametrize('platform', ['darwin', 'win32', 'freebsd14'])
def test_unsupported_hosts_never_probe(platform):
    with mock.patch.object(sys, 'platform', platform), mock.patch.object(diagnostics.subprocess, 'run') as run:
        result = diagnostics.diagnose(probe=True)
    assert result['issue']['code'] == 'managed_platform_unsupported'
    assert result['sandboxReadiness'] == 'unknown'
    run.assert_not_called()


@pytest.mark.parametrize('restriction', ['1', '0', None])
def test_linux_policy_presence_is_not_a_denial(restriction):
    with mock.patch.object(sys, 'platform', 'linux'), mock.patch.object(diagnostics.shutil, 'which', return_value='/bin/tool'), mock.patch.object(Path, 'read_text', side_effect=OSError() if restriction is None else None, return_value=restriction), mock.patch.object(diagnostics.subprocess, 'run') as run:
        result = diagnostics.diagnose()
    assert result['issue'] is None
    assert result['sandboxReadiness'] == 'unknown'
    assert result['apparmorRestrictsUserNamespaces'] == (None if restriction is None else restriction == '1')
    run.assert_not_called()


@pytest.mark.parametrize('code', [0, 1])
def test_probe_preserves_isolation_and_never_claims_codex_readiness(code):
    with mock.patch.object(sys, 'platform', 'linux'), mock.patch.object(diagnostics.shutil, 'which', return_value='/usr/bin/bwrap'), mock.patch.object(diagnostics.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, '', 'denied' if code else '')) as run:
        result = diagnostics.diagnose(probe=True)
    command = run.call_args.args[0]
    assert '--unshare-net' in command and '--ro-bind' in command
    assert run.call_args.kwargs['timeout'] == 5
    assert result['probe']['status'] == ('passed' if code == 0 else 'failed')
    assert result['sandboxReadiness'] == 'unknown'


def test_missing_system_helper_is_not_proof_bundled_helper_is_absent():
    with mock.patch.object(sys, 'platform', 'linux'), mock.patch.object(diagnostics.shutil, 'which', return_value=None):
        result = diagnostics.diagnose(probe=True)
    assert result['probe']['status'] == 'unavailable'
    assert result['sandboxReadiness'] == 'unknown'


@pytest.mark.parametrize('message', ['Permission denied', 'Operation not permitted', 'bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted', 'Windows sandbox available'])
def test_generic_errors_are_not_misclassified(message):
    assert diagnostics.sandbox_failure(message) is None


@pytest.mark.parametrize('message', ['fs sandbox helper failed with status exit status: 1: bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted', 'fs sandbox helper failed: namespace unavailable', 'sandbox-exec: sandbox_apply: Operation not permitted', 'Windows sandbox setup failed'])
def test_specific_sandbox_errors_have_actionable_diagnostics(message):
    assert diagnostics.sandbox_failure(message)


@pytest.mark.parametrize('platform', ['darwin', 'win32', 'freebsd14'])
@pytest.mark.parametrize('arguments', [['doctor'], ['submit', '--agent', 'a', '--role', 'work', '--message', 'inspect']])
def test_cli_diagnostics_and_refusal_do_not_import_posix_runtime(platform, arguments, tmp_path):
    # Fail if portability handling accidentally imports a POSIX-only runtime module.
    code = '''import sys, runpy, shutil, subprocess
class BlockRuntime:
    def find_spec(self, fullname, *args):
        if fullname in {'paths', 'native_codex', 'cloud_reporting'}:
            raise ImportError('POSIX runtime must not be loaded')
sys.meta_path.insert(0, BlockRuntime())
sys.platform = sys.argv[1]
script = sys.argv[2]
sys.argv = [script] + sys.argv[3:]
runpy.run_path(script, run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', code, platform, str(SCRIPT), *arguments], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2, result.stderr
    document = json.loads(result.stdout)
    assert 'managed_platform_unsupported' in json.dumps(document), document
    assert not list(tmp_path.iterdir())
