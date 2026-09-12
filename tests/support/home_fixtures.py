"""Shared isolated home and legacy migration evidence setup."""
import runtime_test_home
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).parents[2] / "skills/agent/runtime"
sys.path.insert(0, str(RUNTIME))
import paths
import migration


class HomeRuntimeFixture:
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
            'requestHash':state['requestHash'], 'outcome':'completed', 'changedPaths':[],
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
