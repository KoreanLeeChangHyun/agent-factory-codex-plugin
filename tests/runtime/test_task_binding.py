import runtime_test_home
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from test_agent_exec import load_module


class TaskBindingTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_module()
        capability = mock.patch.object(self.runtime.native_codex, "inspect_capabilities",
            return_value={"submit": {"goal": True}, "send": {"goal": True}, "diagnostic": None})
        capability.start()
        self.addCleanup(capability.stop)
        import task_binding
        self.binding = task_binding
        self.request = 'Implement the named change'
        self.digest = hashlib.sha256(self.request.encode()).hexdigest()
        self.document = {'id': 'flow-one', 'title': 'User changes', 'tasks': [
            {'id': 'task-one', 'title': 'Fix scroll', 'description': self.request,
             'completionCriteria': 'Scroll remains at the bottom', 'requestHash': self.digest}]}

    def test_rejects_missing_fields_unknown_task_and_mismatched_request(self):
        for key in ('id', 'title', 'description', 'completionCriteria', 'requestHash'):
            document = json.loads(json.dumps(self.document))
            del document['tasks'][0][key]
            with self.subTest(key=key), self.assertRaises(self.runtime.ContractError):
                self.binding.validate(document, 'task-one', self.digest)
        for task, digest in [('missing', self.digest), ('task-one', '0' * 64)]:
            with self.assertRaises(self.runtime.ContractError):
                self.binding.validate(self.document, task, digest)

    def test_submit_blocks_before_launch_and_persists_accepted_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.runtime.parse_args(['submit', '--project-root', directory,
                '--agent', 'work-task', '--role', 'work', '--codex', '/bin/true', '--message', self.request])
            with mock.patch.object(self.runtime, 'spawn_worker', return_value=123) as spawn, mock.patch.object(self.runtime, 'emit') as emit:
                with self.assertRaises(self.runtime.ContractError) as error:
                    self.runtime.submit(args, True)
                self.assertEqual(error.exception.code, 'task_binding_required')
                spawn.assert_not_called()
                path = root / 'tasks.json'
                path.write_text(json.dumps(self.document))
                args.task_list_file, args.task_id = path, 'task-one'
                self.runtime.submit(args, True)
                spawn.assert_called_once()
                state = json.loads(Path(emit.call_args.args[0]['statePath']).read_text())
                self.assertEqual(state['taskBinding']['taskId'], 'task-one')
                self.assertEqual(state['dispatchTuple']['taskBinding'], state['taskBinding'])
                self.assertEqual(state['requestHash'], self.digest)
                self.assertEqual(self.runtime.public_state(state)['taskBinding'], state['taskBinding'])

    def test_loop_rejects_before_creating_or_dispatching(self):
        from test_agent_loop import load_modules
        runtime, loop = load_modules()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / 'request.md'
            request.write_text(self.request)
            tasks = root / 'tasks.json'
            tasks.write_text(json.dumps(self.document))
            args = loop.build_parser().parse_args(['start', '--project-root', directory,
                '--work-agent', 'work-task', '--task-mode', 'work', '--request-file', str(request),
                '--task-list-file', str(tasks), '--task-id', 'absent'])
            with mock.patch.object(loop, 'AgentRuntime') as child, mock.patch.object(loop, 'loop_directory') as create:
                with self.assertRaises(runtime.ContractError):
                    loop.start_loop(args)
                child.assert_not_called()
                create.assert_not_called()

    def test_omitted_hash_is_normalized_without_mutating_source(self):
        document = json.loads(json.dumps(self.document))
        del document['tasks'][0]['requestHash']
        snapshot, binding = self.binding.resolve(document, 'task-one', self.digest)
        self.assertNotIn('requestHash', document['tasks'][0])
        self.assertEqual(snapshot['tasks'][0]['requestHash'], self.digest)
        self.assertEqual(binding['requestHash'], self.digest)
        for value in [None, '', '0' * 64, 'not-a-hash']:
            document['tasks'][0]['requestHash'] = value
            with self.subTest(value=value):
                snapshot, binding = self.binding.resolve(document, 'task-one', self.digest)
                self.assertEqual(binding['requestHash'], self.digest)
                self.assertEqual(snapshot['tasks'][0]['requestHash'], self.digest)
                self.assertEqual(document['tasks'][0]['requestHash'], value)

    def test_direct_submit_automatic_hash_preserves_exact_bytes_and_retry_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = '한글 요청\r\n\n'.encode('utf-8')
            request = root / 'request.md'
            request.write_bytes(content)
            document = json.loads(json.dumps(self.document))
            document['tasks'][0]['requestHash'] = 'obsolete caller value'
            tasks = root / 'tasks.json'
            original = json.dumps(document).encode()
            tasks.write_bytes(original)
            args = self.runtime.parse_args(['submit', '--project-root', directory,
                '--agent', 'automatic-work', '--role', 'work', '--codex', '/bin/true',
                '--request-file', str(request), '--task-list-file', str(tasks),
                '--task-id', 'task-one', '--dispatch-id', 'dispatch-auto'])
            with mock.patch.object(self.runtime, 'spawn_worker', return_value=123) as spawn, mock.patch.object(self.runtime, 'emit') as emit:
                self.runtime.submit(args, True)
                state = json.loads(Path(emit.call_args.args[0]['statePath']).read_text())
                digest = hashlib.sha256(content).hexdigest()
                self.assertEqual(state['requestHash'], digest)
                self.assertEqual(state['taskBinding']['requestHash'], digest)
                self.assertEqual(Path(state['requestPath']).read_bytes(), content)
                self.assertEqual(tasks.read_bytes(), original)
                self.runtime.submit(args, True)
                self.assertEqual(spawn.call_count, 1)
                request.write_bytes(content + b'changed')
                with self.assertRaises(self.runtime.ContractError):
                    self.runtime.submit(args, True)
                self.assertEqual(Path(state['requestPath']).read_bytes(), content)

    def test_capabilities_advertise_automatic_hashes_for_both_operations(self):
        native = {'model': True, 'reasoning': True, 'fast': False, 'goal': False}
        with tempfile.TemporaryDirectory() as directory:
            self.runtime.runtime_paths.resolve(Path(directory), create=True)
            with mock.patch.object(self.runtime.native_codex, 'inspect_capabilities', return_value={
                    'schemaVersion': '0.1.0', 'kind': 'execution-capabilities',
                    'submit': dict(native), 'send': dict(native)}), mock.patch.object(self.runtime, 'emit') as emit:
                self.assertEqual(self.runtime.main(['capabilities', '--project-root', directory, '--codex', '/bin/true']), 0)
                for operation in ('submit', 'send'):
                    self.assertIs(emit.call_args.args[0][operation]['automaticRequestHash'], True)
