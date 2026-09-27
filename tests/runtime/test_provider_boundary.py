"""Provider isolation and the moved native bridge's real entry point."""
import runtime_test_home
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from native_fixtures import native, runtime, native_fixture


class ProviderBoundaryTests(unittest.TestCase):
    def test_claude_import_does_not_load_codex_or_its_policy(self):
        directory = Path(__file__).parents[2] / 'skills/agent/runtime'
        probe = '''import sys
sys.path.insert(0, sys.argv[1])
import adapters
provider = adapters.adapter('claude')
assert provider.session_fields('claude')['provider'] == 'claude'
assert not any(name.startswith('adapters.codex') for name in sys.modules)
assert 'native_codex' not in sys.modules
assert 'preflight' not in sys.modules
'''
        subprocess.run([sys.executable, '-c', probe, str(directory)], check=True, capture_output=True)

    def test_native_entrypoint_uses_explicit_services_and_preserves_result(self):
        # Exercise main -> Bridge -> native Goal/result contract, rather than
        # injecting the orchestrator as the bridge's service container.
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, state = native_fixture(Path(directory), goal=False, existing=False)
            state['nativeSessionPath'] = str(Path(state['statePath']).parent / 'native-session.json')
            runtime.atomic_write_json(Path(state['nativeSessionPath']), bridge.session)
            runtime.atomic_write_json(Path(state['statePath']), state)
            process = mock.Mock()
            rpc.process = process
            with mock.patch.object(native.sys, 'argv', ['transport.py', state['statePath']]), \
                 mock.patch.object(native.sys, 'stdin', io.StringIO('bounded request')), \
                 mock.patch.object(native.subprocess, 'Popen', return_value=process), \
                 mock.patch.object(native, 'Rpc', return_value=rpc):
                self.assertEqual(native.main(), 0)
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            final = next(e['item']['text'] for e in events if e.get('item', {}).get('type') == 'agent_message')
            self.assertEqual(json.loads(final)['resultPath'], state['resultPath'])
            process.terminate.assert_called_once()

    def test_both_providers_implement_the_same_lifecycle_contract(self):
        from adapters.contracts import ProviderAdapter
        import adapters
        methods = [key for key, value in ProviderAdapter.__dict__.items() if callable(value) and not key.startswith('_')]
        for name in ('codex', 'claude'):
            provider = adapters.adapter(name)
            for method in methods:
                self.assertTrue(callable(getattr(provider, method, None)), (name, method))
            self.assertEqual(provider.persisted_fields({'provider': name, 'sessionId': 'private'}), {'provider': name})

    def test_goal_commands_dispatch_through_bounded_services(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, _ = native_fixture(root, goal=False)
            args = SimpleNamespace(project_root=root, agent="main-test", action="get")
            for provider in ("codex", "claude"):
                session_path = runtime.session_file(root, "main-test")
                session = runtime.safe_read_json(session_path)
                session["provider"] = provider
                session["agentId"] = "main-test"
                runtime.atomic_write_json(session_path, session)
                with mock.patch.object(runtime, "emit") as emit:
                    self.assertEqual(runtime.command_goal(args), 0)
                self.assertIsNone(emit.call_args.args[0]["goal"])
            args.action = "resume"
            with self.assertRaisesRegex(runtime.ContractError, "Claude does not support"):
                runtime.command_goal(args)

    def test_orchestrator_import_does_not_eagerly_load_providers(self):
        path = Path(runtime.__file__)
        probe = '''import importlib.util, sys
spec = importlib.util.spec_from_file_location('isolated_exec', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert not any(name.startswith(('adapters.codex', 'adapters.claude')) for name in sys.modules)
'''
        subprocess.run([sys.executable, '-c', probe, str(path)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
