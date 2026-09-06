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
import uuid
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).parents[1] / 'skills/agent/runtime'
sys.path.insert(0, str(RUNTIME))
import paths
import migration
import native_codex
import permissions

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

    def legacy_runtime(self):
        filename = Path(os.environ.get('AF_LEGACY_RUNTIME', '/tmp/af-home-migration-20260906/bootstrap-agent/scripts/exec.py'))
        if not filename.is_file():
            self.skipTest('set AF_LEGACY_RUNTIME to the preserved pre-home runtime')
        return filename

    def legacy(self, *, active=False, malformed=False, status='completed', reporting_config=None):
        legacy = self.legacy_runtime()
        session = {'schemaVersion': '0.1.0', 'agentId': 'work', 'role': 'work', 'sessionId': 'legacy-exact',
            'projectRoot': str(self.root), 'codex': '/bin/true', 'sandbox': 'workspace-write',
            'maxAttempts': 1, 'heartbeatInterval': 1, 'heartbeatTimeout': 5, 'startTimeout': 5, 'turnTimeout': 20}
        program = r'''
import importlib.util,json,pathlib,sys
filename,root,session_json,reporting_json=sys.argv[1:]
spec=importlib.util.spec_from_file_location('isolated_legacy_exec',filename)
legacy=importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
session=json.loads(session_json); reporting=json.loads(reporting_json)
legacy.new_run_id=lambda:'run-one'
options={'reporting_config':reporting,'reporting_loop_id':'loop-one'} if reporting else {}
state=legacy.create_run(project_root=pathlib.Path(root),agent_id='work',actor='main',
 request=b'original request\r\n',session=session,**options)
legacy.atomic_write_json(legacy.session_file(pathlib.Path(root),'work'),session)
print(json.dumps(state))
'''
        produced = subprocess.run([sys.executable,'-c',program,str(legacy),str(self.root),
            json.dumps(session),json.dumps(reporting_config)],capture_output=True,text=True,
            timeout=20,check=True)
        state = json.loads(produced.stdout)
        source = Path(state['statePath']).parent
        state.update(status='running' if active else status, sessionId='legacy-exact', startDisposition='started')
        if status == 'completed' and not active:
            (source/'result.md').write_bytes(b'original result\n')
            receipt = {'schemaVersion':'0.1.0', 'kind':'work-receipt', 'runId':state['runId'],
                'requestHash':state['requestHash'], 'outcome':'implemented', 'changedPaths':['file.py'],
                'addressedFindingIds':[], 'tests':{'run':False,'reason':'work-agent-prohibited'}}
            (source/'receipt.json').write_text(json.dumps(receipt))
        (source/'state.json').write_text('invalid' if malformed else json.dumps(state))
        return source, state

    def legacy_reporting_subprocess(self, config):
        """Produce old reporting bytes without loading old modules into this interpreter."""
        return self.legacy(reporting_config=config)

    def control_completion(self, role, request, result, *, work=None):
        rt = migration.runtime_owner()
        root = self.base/'control'; root.mkdir(exist_ok=True)
        session = {'schemaVersion':'0.1.0', 'agentId':role+'-control', 'role':role,
            'projectRoot':str(root), 'sessionId':role+'-control-session', 'maxAttempts':1}
        state = rt.create_run(project_root=root, agent_id=session['agentId'], actor='main',
            request=json.dumps(request, sort_keys=True).encode(), session=session,
            receipt_request_hash=work['requestHash'] if work else None,
            verified_work_run_id=work['runId'] if work else None)
        rt.atomic_write_json(rt.session_file(root, session['agentId']), session)
        rt.atomic_write(Path(state['resultPath']), json.dumps(result, sort_keys=True).encode())
        receipt = ({'schemaVersion':'0.1.0', 'kind':'work-receipt', 'runId':state['runId'],
            'requestHash':state['requestHash'], 'outcome':'implemented', 'changedPaths':[],
            'addressedFindingIds':[], 'tests':{'run':False,'reason':'work-agent-prohibited'}} if role=='work' else
            {'schemaVersion':'0.1.0', 'kind':'verification-receipt', 'runId':state['runId'],
            'verifiedWorkRunId':work['runId'], 'verifiedRequestHash':work['requestHash'], 'decision':'pass','findings':[]})
        rt.atomic_write_json(Path(state['receiptPath']), receipt)
        state.update(sessionId=session['sessionId'], startDisposition='started')
        rt.atomic_write_json(Path(state['statePath']), state)
        rt.append_event(Path(state['eventsPath']), json.dumps({'type':'item.completed', 'item':{
            'type':'agent_message','text':json.dumps({'status':'completed','resultPath':state['resultPath']})}})+'\n')
        rt.mark_terminal(Path(state['statePath']), 'completed')
        return rt.find_run(root, state['agentId'], state['runId'])

    def evidence(self, plan):
        binding = migration.copy_binding(plan)
        work = self.control_completion('work', {'schemaVersion':1,'kind':'migration-copy-request','binding':binding},
            {'schemaVersion':1,'kind':'migration-copy-result','binding':binding})
        proof = {'schemaVersion':1, 'binding':binding, 'workRunId':work['runId'],
            'workRequestHash':work['requestHash'], 'workResultHash':hashlib.sha256(Path(work['resultPath']).read_bytes()).hexdigest()}
        verification = self.control_completion('verification', {**proof,'kind':'migration-verification-request'},
            {**proof,'kind':'migration-verification-result','decision':'pass'}, work=work)
        evidence = self.base/'evidence.json'
        paths.write(evidence, {'schemaVersion':2,'kind':'migration-verification',
            'workStatePath':work['statePath'],'verificationStatePath':verification['statePath']})
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
        session = {'codex':'fixture-codex', 'projectRoot':str(self.root), 'sandbox':'read-only'}
        for identity in (None, 'exact-thread'):
            command = runtime.build_codex_command(session, state, identity)
            expected = permissions.arguments(Path(state['statePath']).parent)
            self.assertTrue(all(item in command for item in expected))
            self.assertNotIn('--sandbox', command)
            self.assertNotIn('--last', command)
            if identity: self.assertIn(identity, command)
        self.assertFalse((self.root/'.agent-factory').exists())

    @unittest.skipUnless(os.environ.get('AF_VERIFY_LOCAL_CODEX') == '1', 'explicit installed app-server fixture opt-in')
    def test_native_permission_profile_writes_only_exact_run(self):
        import shutil
        binding = paths.resolve(self.root, create=True)
        run = Path(binding['agentsRoot'])/'work/runs/run-sandbox'
        paths.mkdir(run)
        forbidden = self.home/'outside-run.txt'
        forbidden.write_text('preserve')
        code_file = self.root/'owned.py'; code_file.write_text('preserve')
        program = """import pathlib,sys
pathlib.Path(sys.argv[1]).write_text('result')
pathlib.Path(sys.argv[2]).write_text('receipt')
for name in sys.argv[3:]:
    try: pathlib.Path(name).write_text('forbidden')
    except PermissionError: pass
    else: raise RuntimeError('non-run path was writable: '+name)
"""
        codex = os.environ.get('AF_VERIFY_CODEX', shutil.which('codex') or 'codex')
        name, _ = permissions.profile(run)
        isolated_codex_home = self.base/'codex-home'; isolated_codex_home.mkdir()
        process = subprocess.Popen([codex, 'app-server', '--listen', 'stdio://',
                                    *permissions.arguments(run)],
            cwd=self.root, env={**os.environ, 'CODEX_HOME':str(isolated_codex_home)},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(process.kill)
        rpc = native_codex.Rpc(process)
        rpc.call('initialize', {'clientInfo':{'name':'agent_factory_test','version':'0.1.0'},
                                'capabilities':{'experimentalApi':True}})
        rpc.write({'method':'initialized'})
        result = rpc.call('command/exec', {'command':[sys.executable,'-c',program,
            str(run/'result.md'),str(run/'receipt.json'),str(forbidden),str(code_file)],
            'cwd':str(self.root),'permissionProfile':name}, timeout=30)
        self.assertEqual(result['exitCode'], 0, result['stderr'])
        self.assertEqual((run/'result.md').read_text(), 'result')
        self.assertEqual((run/'receipt.json').read_text(), 'receipt')
        self.assertEqual(forbidden.read_text(), 'preserve')
        self.assertEqual(code_file.read_text(), 'preserve')

    def test_malformed_inactive_records_are_archive_only(self):
        source, _ = self.legacy(malformed=True)
        plan = migration.make_plan([str(self.root)], self.home)
        self.assertTrue(plan['archiveOnly'])
        self.assertNotIn(str(source/'state.json'), plan['mapping'])
        migration.copy(plan, self.base/'backup')
        self.assertTrue((migration.area(plan)/'archive'/migration.archive_member(plan,str(source/'state.json'))).exists())

if __name__ == '__main__': unittest.main()
