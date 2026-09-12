"""Home isolation, relocation and migration regressions for Verification only."""
from __future__ import annotations
import runtime_test_home
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

from home_fixtures import HomeRuntimeFixture, RUNTIME, paths, migration
import permissions

class HomeRuntimeTests(HomeRuntimeFixture, unittest.TestCase):
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

    def test_external_rebind_rejects_cached_client_with_existing_old_root(self):
        binding = paths.resolve(self.root, create=True)
        spec = importlib.util.spec_from_file_location('independent_paths', RUNTIME / 'paths.py')
        other = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(other)
        destination = self.base / 'destination'
        destination.mkdir()
        moved = other.rebind(self.home, binding['projectId'], self.root, destination)
        self.assertTrue(self.root.is_dir())
        self.assertEqual(moved['projectId'], binding['projectId'])
        for operation in (lambda: paths.resolve(self.root),
                          lambda: paths.bind(binding),
                          lambda: paths.resolve(self.root, create=True)):
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()
        self.assertEqual(paths._BINDINGS[str(self.root)], binding)

    def test_same_binding_cache_survives_unrelated_registry_update(self):
        binding = paths.resolve(self.root, create=True)
        cached = paths._BINDINGS[str(self.root)]
        other_root = self.base / 'other-code'
        other_root.mkdir()
        paths.resolve(other_root, create=True)
        self.assertEqual(paths.resolve(self.root), binding)
        self.assertEqual(paths.bind(binding), binding)
        self.assertIs(paths._BINDINGS[str(self.root)], cached)


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

    def test_gate_rejects_extra_fields_in_actual_managed_result(self):
        self.legacy()
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        evidence = self.evidence(plan)
        envelope = paths.read(evidence)
        work = migration.runtime_owner().safe_read_json(Path(envelope['workStatePath']))
        result = json.loads(Path(work['resultPath']).read_text())
        result['unbound'] = True
        Path(work['resultPath']).write_text(json.dumps(result))
        with self.assertRaises(ValueError): migration.activate(plan, evidence)

    def test_activation_rejects_forged_same_plan_marker(self):
        self.legacy()
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        binding = plan['projects'][0]
        paths.write(Path(binding['runtimeRoot'])/'migration.json',
            {'schemaVersion':1,'planId':plan['planId'],'planPath':'/wrong','unknown':True})
        with self.assertRaises(ValueError):
            migration.activate(plan, self.evidence(plan))
        self.assertEqual(list(Path(binding['agentsRoot']).iterdir()), [])

    def test_activation_final_inventory_rejects_during_copy_foreign_file(self):
        self.legacy()
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        evidence = self.evidence(plan)
        agents = Path(plan['projects'][0]['agentsRoot'])
        original = migration.copy_member
        injected = False
        def inject(source, target, proof):
            nonlocal injected
            original(source, target, proof)
            if Path(target).is_relative_to(agents) and not injected:
                injected = True
                (agents/'foreign-after-preflight').write_text('preserve')
        with mock.patch.object(migration, 'copy_member', side_effect=inject):
            with self.assertRaises(ValueError):
                migration.activate(plan, evidence)
        self.assertEqual((agents/'foreign-after-preflight').read_text(), 'preserve')

    def test_retirement_retry_refuses_foreign_tombstone_content(self):
        self.legacy()
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        evidence = self.evidence(plan)
        migration.activate(plan, evidence)
        original = Path.unlink
        def interrupt(target, *args, **kwargs):
            if '.agent-factory-retired-' in str(target):
                raise OSError('fixture interruption before first unlink')
            return original(target, *args, **kwargs)
        with mock.patch.object(Path, 'unlink', interrupt):
            with self.assertRaises(OSError):
                migration.retire(plan, evidence, 'fixture Human authority')
        tomb = self.root/('.agent-factory-retired-'+plan['planId'])
        foreign = tomb/'foreign-after-interruption.txt'
        foreign.write_text('must survive')
        with self.assertRaises(ValueError):
            migration.retire(plan, evidence, 'fixture Human authority')
        self.assertEqual(foreign.read_text(), 'must survive')

    def test_failed_legacy_run_maps_absent_optional_outputs(self):
        _, state = self.legacy(status='failed')
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        migration.activate(plan, self.evidence(plan))
        moved = migration.runtime_owner().find_run(self.root, 'work', state['runId'])
        self.assertEqual(Path(moved['resultPath']).parent, Path(moved['statePath']).parent)
        self.assertFalse(Path(moved['resultPath']).exists())

    def test_real_legacy_reporting_outbox_replays_after_activation(self):
        config = {'version':1, 'endpoint':'http://127.0.0.1:9/mcp',
            'recipient_id':'recipient-one','project_ref':'project-one',
            'organization_id':str(uuid.uuid4()),'workspace_id':str(uuid.uuid4()),
            'reporter_user_id':str(uuid.uuid4()),'cloud_agent_id':str(uuid.uuid4()),
            'credential_file':str(self.base/'credential.json'),'allow_loopback_http':True}
        source, _ = self.legacy_reporting_subprocess(config)
        before = json.loads((source/'reporting.json').read_text())
        plan = migration.make_plan([str(self.root)], self.home)
        migration.copy(plan, self.base/'backup')
        migration.activate(plan, self.evidence(plan))
        runtime = migration.runtime_owner()
        moved = runtime.find_run(self.root, 'work', 'run-one')
        _, box = runtime.cloud_reporting.load_box(runtime, self.root, moved)
        self.assertEqual(box['config'], config)
        self.assertEqual(box['entries'], before['entries'])
        first_keys = [entry['command']['key'] for entry in box['entries']]
        runtime.cloud_reporting.collect(runtime, self.root, moved,
            ('2099-01-01T00:00:00Z','process_exited'))
        _, resumed = runtime.cloud_reporting.load_box(runtime, self.root, moved)
        self.assertEqual([entry['command']['key'] for entry in resumed['entries'][:len(first_keys)]], first_keys)

    def test_exec_sandbox_grants_exact_external_run_and_resumes_exact_session(self):
        spec = importlib.util.spec_from_file_location('home_test_exec', RUNTIME.parent/'scripts/exec.py')
        runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
        state = runtime.create_run(project_root=self.root, agent_id='work', actor='main',
            request=b'bounded', session={'role':'work', 'maxAttempts':1})
        session = {'codex':'fixture-codex', 'projectRoot':str(self.root), 'sandbox':'read-only', 'executionPolicy':runtime_test_home.policy('read-only')}
        for identity in (None, 'exact-thread'):
            command = runtime.build_codex_command(session, state, identity)
            expected = runtime.execution_policy.arguments(runtime.execution_policy.session_policy(session), Path(state['statePath']).parent)
            self.assertTrue(all(item in command for item in expected))
            self.assertNotIn('--sandbox', command)
            self.assertNotIn('--last', command)
            if identity: self.assertIn(identity, command)
        self.assertFalse((self.root/'.agent-factory').exists())


    def test_malformed_inactive_records_are_archive_only(self):
        source, _ = self.legacy(malformed=True)
        plan = migration.make_plan([str(self.root)], self.home)
        self.assertTrue(plan['archiveOnly'])
        self.assertNotIn(str(source/'state.json'), plan['mapping'])
        migration.copy(plan, self.base/'backup')
        self.assertTrue((migration.area(plan)/'archive'/migration.archive_member(plan,str(source/'state.json'))).exists())

if __name__ == '__main__': unittest.main()
