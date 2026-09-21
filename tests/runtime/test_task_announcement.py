import runtime_test_home
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_agent_exec import load_module


class TaskAnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_module()
        import task_announcement
        self.announcement = task_announcement
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        binding = self.runtime.runtime_paths.resolve(self.root, create=True)
        self.parent_path = self.runtime.agent_directory(self.root, 'main-tasks', create=True) / 'runs' / 'run-main' / 'state.json'
        self.state = {'agentId': 'main-tasks', 'runId': 'run-main', 'role': 'main',
                      'status': 'running', 'conversationId': 'conversation-one', 'runtimeBinding': binding}
        self.runtime.atomic_write_json(self.parent_path, self.state)
        env = mock.patch.dict(os.environ, {'AGENT_FACTORY_PARENT_STATE': str(self.parent_path)})
        env.start()
        self.addCleanup(env.stop)
        session = mock.patch.object(self.runtime, 'load_session', return_value={'conversationId': 'conversation-one'})
        session.start()
        self.addCleanup(session.stop)
        self.document = {'id': 'workflow-six', 'title': '여섯 작업', 'tasks': []}
        for index in range(6):
            request = self.root / f'request-{index}.md'
            request.write_text(f'요청 {index}\nScope and constraints.\n', encoding='utf-8')
            self.document['tasks'].append({'id': f'task-{index}', 'title': f'작업 {index}',
                'description': f'요청 설명 {index}', 'completionCriteria': f'완료 기준 {index}',
                'requestFile': str(request), 'workAgentId': 'one-worker'})
        self.source = self.root / 'tasks.json'
        self.source.write_text(json.dumps(self.document), encoding='utf-8')
        self.args = self.runtime.parse_args(['announce-tasks', '--project-root', str(self.root),
                                            '--task-list-file', str(self.source)])

    def prepare(self):
        return self.announcement.prepare(self.runtime, self.args)

    def test_presentation_and_submission_share_order_content_and_parent(self):
        original = self.source.read_bytes()
        result = self.prepare()
        saved = self.runtime.safe_read_json(Path(result['taskListFile']))
        record = self.runtime.safe_read_json(Path(result['announcementPath']))
        self.assertEqual(record['taskList'], saved)
        self.assertEqual(record['parentAgentId'], 'main-tasks')
        self.assertEqual(record['parentRunId'], 'run-main')
        self.assertEqual(record['runtimeBinding'], self.state['runtimeBinding'])
        self.assertEqual(result['taskFlow'], self.announcement.task_flow(saved))
        self.assertEqual(len(result['taskFlow']['tasks']), 6)
        for source, task, flow in zip(self.document['tasks'], saved['tasks'], result['taskFlow']['tasks']):
            for key in ('id', 'title', 'description', 'completionCriteria'):
                self.assertEqual(source[key], task[key])
                self.assertEqual(source[key], flow[key])
            self.assertEqual(Path(source['requestFile']).read_bytes(), Path(task['requestFile']).read_bytes())
            self.assertEqual(task['workAgentId'], 'one-worker')
        self.assertEqual(result['requestFile'], saved['tasks'][0]['requestFile'])
        self.assertEqual(result['taskId'], saved['tasks'][0]['id'])
        import task_binding
        binding = task_binding.load(self.runtime.safe_read_json, Path(result['taskListFile']),
                                    result['taskId'], saved['tasks'][0]['requestHash'])
        self.assertEqual(binding['workflowId'], result['taskFlow']['id'])
        self.assertEqual(binding['title'], result['taskFlow']['tasks'][0]['title'])
        self.assertEqual(binding['completionCriteria'], result['taskFlow']['tasks'][0]['completionCriteria'])
        self.assertEqual(self.source.read_bytes(), original)

    def test_retry_reuses_snapshot_and_changed_request_cannot_replace_it(self):
        result = self.prepare()
        original = Path(result['announcementPath']).read_bytes()
        self.assertEqual(self.prepare(), result)
        Path(self.document['tasks'][0]['requestFile']).write_text('Changed request')
        with self.assertRaises(self.runtime.ContractError) as error:
            self.prepare()
        self.assertEqual(error.exception.code, 'task_announcement_conflict')
        self.assertEqual(Path(result['announcementPath']).read_bytes(), original)
        self.assertIn('Scope and constraints.', Path(result['requestFile']).read_text())

    def test_reordered_tasks_cannot_replace_announcement(self):
        self.prepare()
        reordered = copy.deepcopy(self.document)
        reordered['tasks'].reverse()
        self.source.write_text(json.dumps(reordered))
        with self.assertRaises(self.runtime.ContractError) as error:
            self.prepare()
        self.assertEqual(error.exception.code, 'task_announcement_conflict')

    def test_requires_current_active_main_in_bound_project(self):
        for change in ({'role': 'work'}, {'status': 'completed'}, {'conversationId': 'old'},
                       {'runtimeBinding': {'projectRoot': '/different-project'}}):
            with self.subTest(change=change):
                self.runtime.atomic_write_json(self.parent_path, {**self.state, **change})
                with self.assertRaises(self.runtime.ContractError):
                    self.prepare()
        with mock.patch.dict(os.environ, {'AGENT_FACTORY_PARENT_STATE': ''}):
            with self.assertRaises(self.runtime.ContractError) as error:
                self.prepare()
            self.assertEqual(error.exception.code, 'task_announcement_parent_required')
        self.assertFalse((self.parent_path.parent / 'task-announcements').exists())

    def test_persisted_parent_binding_mismatch_is_contract_error_without_side_effects(self):
        for field, value in (('projectRoot', '/different-project'), ('projectId', 'project-other'),
                             ('home', '/different-runtime-home')):
            invalid = {**self.state, 'runtimeBinding': {**self.state['runtimeBinding'], field: value}}
            self.runtime.atomic_write_json(self.parent_path, invalid)
            original = self.parent_path.read_bytes()
            with self.subTest(field=field), \
                    mock.patch.object(self.runtime, 'atomic_write_json') as write, \
                    mock.patch.object(self.runtime, 'create_run') as create, \
                    mock.patch.object(self.runtime, 'spawn_worker') as spawn:
                with self.assertRaises(self.runtime.ContractError) as error:
                    self.prepare()
                self.assertEqual(error.exception.code, 'parent_session_invalid')
                self.assertIsInstance(error.exception.__cause__, ValueError)
                self.assertIn('persisted runtime binding mismatch', str(error.exception.__cause__))
                write.assert_not_called()
                create.assert_not_called()
                spawn.assert_not_called()
            self.assertEqual(self.parent_path.read_bytes(), original)
            self.assertFalse((self.parent_path.parent / 'task-announcements').exists())

    def test_cli_reports_invalid_parent_binding_as_contract_error(self):
        self.runtime.atomic_write_json(self.parent_path, {**self.state,
            'runtimeBinding': {**self.state['runtimeBinding'], 'projectRoot': '/different-project'}})
        response = subprocess.run([sys.executable, self.runtime.__file__, 'announce-tasks',
            '--project-root', str(self.root), '--task-list-file', str(self.source)],
            capture_output=True, text=True, timeout=30, env=os.environ.copy())
        self.assertEqual(response.returncode, 2, response.stdout + response.stderr)
        error = json.loads(response.stdout.splitlines()[-1])
        self.assertEqual(error['error']['code'], 'parent_session_invalid')
        self.assertIn('persisted runtime binding mismatch', error['error']['message'])
        self.assertFalse((self.parent_path.parent / 'task-announcements').exists())
        self.assertFalse(self.runtime.agent_directory(self.root, 'one-worker').exists())

    def test_invalid_metadata_or_missing_request_creates_no_announcement(self):
        for key in ('completionCriteria', 'requestFile'):
            document = copy.deepcopy(self.document)
            del document['tasks'][2][key]
            self.source.write_text(json.dumps(document))
            with self.subTest(key=key), self.assertRaises(self.runtime.ContractError):
                self.prepare()
        self.assertFalse((self.parent_path.parent / 'task-announcements').exists())

    def check_submission(self, document):
        return self.announcement.check_submission(self.runtime.safe_read_json, self.parent_path,
            {'agentId': 'main-tasks', 'runId': 'run-main'}, document)

    def test_missing_announcement_requires_new_contract_but_preserves_history(self):
        self.check_submission(self.document)
        self.runtime.atomic_write_json(self.parent_path, {**self.state, 'taskAnnouncementContract': 1})
        with self.assertRaises(self.runtime.ContractError) as error:
            self.check_submission(self.document)
        self.assertEqual(error.exception.code, 'task_announcement_required')
        self.announcement.check_submission(self.runtime.safe_read_json, None, None, self.document)

    def mismatches(self):
        cases = []
        for change, code in (
            (lambda d: d['tasks'].pop(), 'count_mismatch'),
            (lambda d: d.update(tasks=d['tasks'][:1]), 'count_mismatch'),
            (lambda d: d['tasks'][1].update(id=d['tasks'][0]['id']), 'duplicate'),
            (lambda d: d['tasks'].reverse(), 'order_mismatch'),
            (lambda d: d['tasks'][0].update(id='replacement'), 'ids_mismatch'),
            (lambda d: d['tasks'][0].update(title='Changed name'), 'metadata_mismatch'),
            (lambda d: d['tasks'][0].update(completionCriteria='Changed criterion'), 'metadata_mismatch'),
            (lambda d: d['tasks'][0].update(description='Changed scope'), 'metadata_mismatch'),
            (lambda d: d.update(id='different-workflow'), 'required'),
        ):
            document = copy.deepcopy(self.document)
            change(document)
            cases.append((document, 'task_announcement_' + code))
        return cases

    def test_mismatches_are_rejected_before_exec_child_creation(self):
        self.prepare()
        policy = {'schemaVersion': 1, 'sandboxPolicy': {'type': 'danger-full-access', 'network_access': True}, 'approvalPolicy': 'never'}
        for document, code in self.mismatches():
            self.source.write_text(json.dumps(document))
            args = self.runtime.parse_args(['submit', '--project-root', str(self.root),
                '--agent', 'one-worker', '--role', 'work', '--task-mode', 'work',
                '--request-file', self.document['tasks'][0]['requestFile'],
                '--task-list-file', str(self.source), '--task-id', 'task-0'])
            with self.subTest(code=code), mock.patch.object(self.runtime, 'resolve_execution_policy', return_value=policy), \
                    mock.patch.object(self.runtime, 'resolve_human_approval_policy', return_value='bypass'), \
                    mock.patch.object(self.runtime, 'create_session') as create, \
                    mock.patch.object(self.runtime, 'spawn_worker') as spawn:
                with self.assertRaises(self.runtime.ContractError) as error:
                    self.runtime.submit(args, True)
                self.assertEqual(error.exception.code, code)
                create.assert_not_called()
                spawn.assert_not_called()
        self.assertFalse(self.runtime.agent_directory(self.root, 'one-worker').exists())

    def test_loop_checks_before_creation_and_accepts_six_tasks_without_caller_hashes(self):
        from test_agent_loop import load_modules, FakeRuntime
        _, loop = load_modules()
        loop.agent_exec = self.runtime
        fake = FakeRuntime(self.root, self.runtime)
        self.prepare()
        args = loop.build_parser().parse_args(['start', '--project-root', str(self.root),
            '--work-agent', 'one-worker', '--task-mode', 'work',
            '--request-file', self.document['tasks'][0]['requestFile'],
            '--task-list-file', str(self.source), '--task-id', 'task-0'])
        with mock.patch.object(loop, 'AgentRuntime', return_value=fake):
            for document, code in self.mismatches():
                self.source.write_text(json.dumps(document))
                with self.subTest(code=code), self.assertRaises(self.runtime.ContractError) as error:
                    loop.start_loop(args)
                self.assertEqual(error.exception.code, code)
                self.assertEqual(fake.dispatches, [])
                self.assertFalse(self.runtime.agent_directory(self.root, 'one-worker').exists())
            self.source.write_text(json.dumps(self.document))
            policy = {'schemaVersion': 1, 'sandboxPolicy': {'type': 'danger-full-access', 'network_access': True}, 'approvalPolicy': 'never'}
            with mock.patch.object(self.runtime, 'resolve_execution_policy', return_value=policy):
                accepted = loop.start_loop(args)
        saved = self.runtime.safe_read_json(Path(accepted['statePath']))
        self.assertEqual([task['id'] for task in saved['workflow']['tasks']],
                         [task['id'] for task in self.document['tasks']])
        self.assertEqual(len(fake.dispatches), 1)

    def test_caller_path_or_count_cannot_replace_parent_snapshot(self):
        result = self.prepare()
        document = copy.deepcopy(self.document)
        document.update(taskCount=6, announcementPath=result['announcementPath'])
        document['tasks'] = document['tasks'][:1]
        with self.assertRaises(self.runtime.ContractError) as error:
            self.check_submission(document)
        self.assertEqual(error.exception.code, 'task_announcement_count_mismatch')
        record = self.runtime.safe_read_json(Path(result['announcementPath']))
        record['parentRunId'] = 'other-run'
        self.runtime.atomic_write_json(Path(result['announcementPath']), record)
        with self.assertRaises(self.runtime.ContractError) as error:
            self.check_submission(self.document)
        self.assertEqual(error.exception.code, 'task_announcement_binding_invalid')

    def test_send_and_standalone_verification_check_before_launch(self):
        self.prepare()
        document = copy.deepcopy(self.document)
        document['tasks'][0]['title'] = 'Changed name'
        self.source.write_text(json.dumps(document))
        policy = {'schemaVersion': 1, 'sandboxPolicy': {'type': 'danger-full-access', 'network_access': True}, 'approvalPolicy': 'never'}
        for operation, role in (('send', 'work'), ('submit', 'verification'), ('send', 'verification')):
            argv = [operation, '--project-root', str(self.root), '--agent', 'one-worker',
                '--task-mode', 'verification' if role == 'verification' else 'work',
                '--request-file', self.document['tasks'][0]['requestFile'],
                '--task-list-file', str(self.source), '--task-id', 'task-0']
            if operation == 'submit':
                argv.extend(['--role', role])
            with self.subTest(operation=operation, role=role), \
                    mock.patch.object(self.runtime, 'load_session', return_value={'role': role, 'conversationId': 'conversation-one'}), \
                    mock.patch.object(self.runtime, 'resolve_execution_policy', return_value=policy), \
                    mock.patch.object(self.runtime, 'resolve_human_approval_policy', return_value='bypass'), \
                    mock.patch.object(self.runtime, 'create_run') as create, \
                    mock.patch.object(self.runtime, 'spawn_worker') as spawn:
                with self.assertRaises(self.runtime.ContractError) as error:
                    self.runtime.submit(self.runtime.parse_args(argv), operation == 'submit')
                self.assertEqual(error.exception.code, 'task_announcement_metadata_mismatch')
                create.assert_not_called()
                spawn.assert_not_called()

    def test_accepted_retry_returns_existing_run_without_reregistering(self):
        announcement = self.prepare()
        args = self.runtime.parse_args(['submit', '--project-root', str(self.root),
            '--agent', 'one-worker', '--role', 'work', '--task-mode', 'work', '--codex', '/bin/true',
            '--dispatch-id', 'dispatch-repeat', '--request-file', self.document['tasks'][0]['requestFile'],
            '--task-list-file', str(self.source), '--task-id', 'task-0'])
        policy = {'schemaVersion': 1, 'sandboxPolicy': {'type': 'danger-full-access', 'network_access': True}, 'approvalPolicy': 'never'}
        def session(root, agent):
            if agent == 'main-tasks':
                return {'conversationId': 'conversation-one'}
            return self.runtime.safe_read_json(self.runtime.session_file(root, agent))
        with mock.patch.object(self.runtime, 'load_session', side_effect=session), \
                mock.patch.object(self.runtime, 'resolve_execution_policy', return_value=policy), \
                mock.patch.object(self.runtime, 'resolve_human_approval_policy', return_value='bypass'), \
                mock.patch.object(self.runtime.native_codex, 'inspect_capabilities', return_value={
                    'submit': {'goal': True}, 'send': {'goal': True}, 'diagnostic': None}), \
                mock.patch.object(self.runtime, 'spawn_worker', return_value=123) as spawn, \
                mock.patch.object(self.runtime, 'emit') as emit:
            self.runtime.submit(args, True)
            first = emit.call_args.args[0]
            record = self.runtime.safe_read_json(Path(announcement['announcementPath']))
            record['taskList']['tasks'][0]['title'] = 'Unavailable old presentation'
            self.runtime.atomic_write_json(Path(announcement['announcementPath']), record)
            self.runtime.submit(args, True)
            retry = emit.call_args.args[0]
            self.assertEqual(retry['runId'], first['runId'])
            self.assertTrue(retry['deduplicated'])
            spawn.assert_called_once()

    def test_cli_announcement_then_mismatched_loop_blocks_before_child_creation(self):
        # Exercise public entrypoints across processes, without a provider or real Agent.
        self.runtime.atomic_write_json(self.runtime.session_file(self.root, 'main-tasks'), {
            'agentId': 'main-tasks', 'role': 'main', 'projectRoot': str(self.root),
            'conversationId': 'conversation-one', 'sessionId': None})
        self.runtime.atomic_write_json(self.parent_path, {**self.state, 'taskAnnouncementContract': 1})
        script = Path(self.runtime.__file__)
        prepared = subprocess.run([sys.executable, str(script), 'announce-tasks',
            '--project-root', str(self.root), '--task-list-file', str(self.source)],
            capture_output=True, text=True, timeout=30, env=os.environ.copy())
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        announcement = json.loads(prepared.stdout.splitlines()[-1])
        self.assertEqual(len(announcement['taskFlow']['tasks']), 6)
        self.assertEqual(announcement['parentRunId'], 'run-main')
        submitted = self.runtime.safe_read_json(Path(announcement['taskListFile']))
        self.assertEqual(announcement['taskFlow'], self.announcement.task_flow(submitted))
        # Submit a separate edited document; never mutate the owning runtime snapshot.
        submitted['tasks'] = submitted['tasks'][:1]
        submitted['taskCount'] = 6
        self.source.write_text(json.dumps(submitted))
        rejected = subprocess.run([sys.executable, str(script.with_name('loop.py')), 'start',
            '--project-root', str(self.root), '--task-mode', 'work', '--work-agent', 'one-worker',
            '--request-file', announcement['requestFile'], '--task-list-file', str(self.source),
            '--task-id', announcement['taskId']], capture_output=True, text=True, timeout=30, env=os.environ.copy())
        self.assertNotEqual(rejected.returncode, 0)
        error = json.loads(rejected.stdout.splitlines()[-1])
        self.assertEqual(error['error']['code'], 'task_announcement_count_mismatch')
        self.assertFalse(self.runtime.agent_directory(self.root, 'one-worker').exists())
