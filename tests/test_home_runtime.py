"""Home isolation, relocation and migration regressions for Verification only."""
from __future__ import annotations
import runtime_test_home
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).parents[1] / 'skills/agent/runtime'
sys.path.insert(0, str(RUNTIME))
import paths
import migration

class HomeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'private-home'
        self.root = self.base / 'code'
        self.root.mkdir()
        paths._BINDINGS.clear()
        patch = mock.patch.dict(os.environ, {'AGENT_FACTORY_HOME': str(self.home)})
        patch.start(); self.addCleanup(patch.stop)
        self.addCleanup(paths._BINDINGS.clear)

    def test_discovery_does_not_initialize_and_init_is_idempotent(self):
        self.assertFalse(paths.resolve(self.root)['registered'])
        self.assertFalse(self.home.exists())
        binding = paths.resolve(self.root, create=True)
        original = (self.home / 'registry.json').read_bytes()
        self.assertEqual(paths.resolve(self.root, create=True), binding)
        self.assertEqual((self.home / 'registry.json').read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(Path(binding['runtimeRoot']).stat().st_mode & 0o777, 0o700)

    def test_separate_copies_and_explicit_relocation_preserve_id(self):
        first = paths.resolve(self.root, create=True)
        copy = self.base / 'copy'; copy.mkdir()
        second = paths.resolve(copy, create=True)
        self.assertNotEqual(first['projectId'], second['projectId'])
        new = self.base / 'relocated'; self.root.rename(new)
        moved = paths.rebind(self.home, first['projectId'], self.root, new)
        self.assertEqual(first['projectId'], moved['projectId'])
        with self.assertRaises(ValueError):
            paths.rebind(self.home, moved['projectId'], new, copy)

    def test_concurrent_initialization_has_one_identity(self):
        code = 'import paths,json,sys; print(json.dumps(paths.resolve(sys.argv[1], create=True)))'
        env = {**os.environ, 'PYTHONPATH': str(RUNTIME)}
        children = [subprocess.Popen([sys.executable, '-c', code, str(self.root)], env=env, stdout=subprocess.PIPE, text=True) for _ in range(4)]
        values = [json.loads(child.communicate(timeout=10)[0]) for child in children]
        self.assertEqual(len({value['projectId'] for value in values}), 1)
        self.assertTrue(all(child.returncode == 0 for child in children))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_symlink_home_and_ancestor_are_rejected(self):
        target = self.base / 'target'; target.mkdir()
        self.home.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError): paths.resolve(self.root, create=True)
        self.home.unlink()
        ancestor = self.base / 'link'; ancestor.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError): paths.resolve(self.root, create=True, home=ancestor / 'home')

    def test_immutable_binding_ignores_environment_changes(self):
        binding = paths.resolve(self.root, create=True)
        with mock.patch.dict(os.environ, {'AGENT_FACTORY_HOME': str(self.base / 'other')}):
            self.assertEqual(paths.resolve(self.root), binding)
            self.assertEqual(paths.arguments(self.root)[1], binding['home'])

    def legacy(self, *, active=False, malformed=False):
        source = self.root / '.agent-factory/agent/work/runs/run-one'
        source.mkdir(parents=True)
        request = b'original request\r\n'
        (source / 'request.md').write_bytes(request)
        (source / 'result.md').write_bytes(b'original result\n')
        state = {'schemaVersion': '0.1.0', 'role': 'work', 'agentId': 'work', 'runId': 'run-one',
                 'requestHash': hashlib.sha256(request).hexdigest(), 'status': 'running' if active else 'completed',
                 'statePath': str(source / 'state.json'), 'resultPath': str(source / 'result.md'),
                 'receiptSchemaPath': str(source / 'receipt.schema.json'), 'receiptPath': str(source / 'receipt.json')}
        (source / 'state.json').write_text('invalid' if malformed else json.dumps(state))
        (source / 'receipt.schema.json').write_text('{}')
        receipt = {'schemaVersion': '0.1.0', 'kind': 'work-receipt', 'runId': 'run-one',
                   'requestHash': state['requestHash'], 'outcome': 'implemented', 'changedPaths': ['file.py'],
                   'addressedFindingIds': [], 'tests': {'run': False, 'reason': 'work-agent-prohibited'}}
        (source / 'receipt.json').write_text(json.dumps(receipt))
        return source, state

    def evidence(self, plan):
        request = self.base / 'copy-request.md'
        request.write_text('Copy exact migration plan ' + plan['planId'])
        request_hash = hashlib.sha256(request.read_bytes()).hexdigest()
        work = self.base / 'copy-receipt.json'
        work.write_text(json.dumps({'schemaVersion': '0.1.0', 'kind': 'work-receipt', 'runId': 'copy-fixture',
            'requestHash': request_hash, 'outcome': 'implemented', 'changedPaths': [], 'addressedFindingIds': [],
            'tests': {'run': False, 'reason': 'work-agent-prohibited'}}))
        receipt = self.base / 'independent-receipt.json'
        receipt.write_text(json.dumps({'schemaVersion': '0.1.0', 'kind': 'verification-receipt',
            'runId': 'verification-fixture', 'verifiedWorkRunId': 'copy-fixture', 'verifiedRequestHash': request_hash,
            'decision': 'pass', 'findings': []}))
        evidence = self.base / 'evidence.json'
        paths.write(evidence, {'schemaVersion': 1, 'kind': 'migration-verification', 'planId': plan['planId'],
            'decision': 'pass', 'verifierRunId': 'verification-fixture', 'verificationReceiptPath': str(receipt),
            'verificationReceiptHash': hashlib.sha256(receipt.read_bytes()).hexdigest(),
            'copyWorkRequestPath': str(request), 'copyWorkReceiptPath': str(work),
            'copyWorkReceiptHash': hashlib.sha256(work.read_bytes()).hexdigest()})
        return evidence

    def test_copy_archive_overlay_receipt_validation_and_no_cutover_without_gate(self):
        source, state = self.legacy()
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base / 'backup')
        migration.copy(plan, self.base / 'backup')
        self.assertTrue(source.exists())
        with self.assertRaises((ValueError, TypeError)): migration.activate(plan, None)
        evidence = self.evidence(plan)
        migration.activate(plan, evidence)
        script = RUNTIME.parent / 'scripts/exec.py'
        spec = importlib.util.spec_from_file_location('migration_test_exec', script)
        runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
        moved = runtime.find_run(self.root, 'work', 'run-one')
        self.assertNotEqual(moved['statePath'], state['statePath'])
        self.assertEqual(runtime.validate_receipt(self.root, moved, agent_id='work', run_id='run-one')['requestHash'], state['requestHash'])
        receipt_path = Path(moved['receiptPath'])
        receipt = json.loads(receipt_path.read_text()); receipt['requestHash'] = '0'*64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(runtime.ContractError): runtime.validate_receipt(self.root, moved, agent_id='work', run_id='run-one')
        archived = migration.area(plan) / 'archive' / migration.archive_member(plan, str(source / 'receipt.json'))
        self.assertEqual(archived.read_bytes(), (source / 'receipt.json').read_bytes())

    def test_changed_source_backup_conflict_and_active_writer_fail_closed(self):
        source, _ = self.legacy(active=True)
        plan = migration.make_plan([str(self.root)], self.home)
        with self.assertRaises(ValueError): migration.copy(plan, self.base / 'backup')
        state = json.loads((source/'state.json').read_text()); state['status'] = 'completed'
        (source/'state.json').write_text(json.dumps(state))
        with self.assertRaises(ValueError): migration.copy(plan, self.base/'backup')
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        archived = migration.area(plan)/'archive'/migration.archive_member(plan, str(source/'request.md'))
        archived.write_bytes(b'conflict')
        with self.assertRaises(ValueError): migration.eligible(plan)

    def test_interrupted_copy_and_activation_resume_the_same_manifest(self):
        self.legacy()
        plan = migration.make_plan([str(self.root)], self.home)
        original = migration.copy_member
        count = 0
        def interrupted(*args):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('fixture interruption')
            return original(*args)
        with mock.patch.object(migration, 'copy_member', side_effect=interrupted):
            with self.assertRaises(OSError): migration.copy(plan, self.base/'backup')
        migration.copy(plan, self.base/'backup')
        evidence = self.evidence(plan)
        count = 0
        with mock.patch.object(migration, 'copy_member', side_effect=interrupted):
            with self.assertRaises(OSError): migration.activate(plan, evidence)
        with self.assertRaises(ValueError): paths.require_ready(plan['projects'][0])
        migration.activate(plan, evidence)
        paths.require_ready(plan['projects'][0])

    def test_locked_writer_and_destination_conflict_refuse_publication(self):
        import fcntl
        source, _ = self.legacy()
        lock = source / '.state.lock'; lock.write_bytes(b'')
        plan = migration.make_plan([str(self.root)], self.home)
        with lock.open('r') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            with self.assertRaises(BlockingIOError): migration.copy(plan, self.base/'backup')
        migration.copy(plan, self.base/'backup')
        destination = Path(plan['projects'][0]['agentsRoot'])/'unrelated'
        destination.mkdir()
        with self.assertRaises(ValueError): migration.activate(plan, self.evidence(plan))
        self.assertTrue(destination.exists())

    def test_exec_sandbox_grants_exact_external_run_and_resumes_exact_session(self):
        spec = importlib.util.spec_from_file_location('home_test_exec', RUNTIME.parent/'scripts/exec.py')
        runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
        state = runtime.create_run(project_root=self.root, agent_id='work', actor='main',
            request=b'bounded', session={'role':'work', 'maxAttempts':1})
        session = {'codex':'fixture-codex', 'projectRoot':str(self.root), 'sandbox':'workspace-write'}
        for identity in (None, 'exact-thread'):
            command = runtime.build_codex_command(session, state, identity)
            roots = next(item for item in command if item.startswith('sandbox_workspace_write.writable_roots='))
            self.assertEqual(json.loads(roots.split('=',1)[1]), [str(Path(state['statePath']).parent)])
            self.assertNotIn('--last', command)
            if identity: self.assertIn(identity, command)
        self.assertFalse((self.root/'.agent-factory').exists())

    @unittest.skipUnless(os.environ.get('AF_VERIFY_LOCAL_CODEX') == '1', 'explicit installed sandbox fixture opt-in')
    def test_native_sandbox_can_write_only_the_granted_run_in_runtime_home(self):
        import shutil
        binding = paths.resolve(self.root, create=True)
        run = Path(binding['agentsRoot'])/'work/runs/run-sandbox'
        paths.mkdir(run)
        forbidden = self.home/'outside-run.txt'
        forbidden.write_text('preserve')
        program = "import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('result')\np = pathlib.Path(sys.argv[2])\ntry:\n    p.write_text('forbidden')\nexcept PermissionError:\n    pass\nelse:\n    raise RuntimeError('runtime home was writable')\n"
        command = [os.environ.get('AF_VERIFY_CODEX', shutil.which('codex') or 'codex'),
            'sandbox', 'linux', '--full-auto', '-c',
            'sandbox_workspace_write.writable_roots='+json.dumps([str(run)]),
            '--', sys.executable, '-c', program, str(run/'result.md'), str(forbidden)]
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((run/'result.md').read_text(), 'result')
        self.assertEqual(forbidden.read_text(), 'preserve')

    def test_malformed_inactive_records_are_archive_only(self):
        source, _ = self.legacy(malformed=True)
        plan = migration.make_plan([str(self.root)], self.home)
        self.assertTrue(plan['archiveOnly'])
        self.assertNotIn(str(source/'state.json'), plan['mapping'])
        migration.copy(plan, self.base/'backup')
        self.assertTrue((migration.area(plan)/'archive'/migration.archive_member(plan,str(source/'state.json'))).exists())

if __name__ == '__main__': unittest.main()
