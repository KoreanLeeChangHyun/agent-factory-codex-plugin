"""Real legacy exec/loop serialization and fake-Codex continuation after copying."""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
import test_home_runtime as home_tests
import migration
import paths

RUNTIME = home_tests.RUNTIME

FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
schema = pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1])
run = schema.parent
contract = json.loads((run/'receipt.schema.json').read_text())
props = contract['properties']
role = 'verification' if props['kind']['const']=='verification-receipt' else 'work'
record_path = pathlib.Path(os.environ['AF_FAKE_HISTORY'])
records = json.loads(record_path.read_text()) if record_path.exists() else []
prior = sys.argv[-2] if 'resume' in sys.argv else None
session = prior or 'exact-'+role+'-session'
records.append({'role':role,'resume':prior,'session':session})
record_path.write_text(json.dumps(records))
receipt = {key:value['const'] for key,value in props.items() if 'const' in value}
if role == 'work':
    prior_failure = any(r['role']=='verification' for r in records[:-1])
    receipt.update(changedPaths=[],addressedFindingIds=['fixture-fail'] if prior_failure else [],tests={'run':False,'reason':'work-agent-prohibited'})
else:
    first = len([r for r in records if r['role']=='verification']) == 1
    receipt.update(decision='fail' if first else 'pass',findings=[{'id':'fixture-fail','path':'file.py','location':'1','problem':'fixture','evidence':'fixture','correction':'fixture'}] if first else [])
(run/'receipt.json').write_text(json.dumps(receipt))
(run/'result.md').write_text('bounded fake result')
print(json.dumps({'type':'thread.started','thread_id':session}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'status':'completed','resultPath':str(run/'result.md')})}}))
print(json.dumps({'type':'turn.completed','usage':{}}))
'''

class MigratedGraphTests(unittest.TestCase):
    def setUp(self):
        self.h = home_tests.HomeRuntimeTests(); self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.legacy = self.h.legacy_runtime()
        self.old = self.legacy.parent
        self.new = RUNTIME.parent/'scripts'
        self.fake = self.h.base/'fake-codex'; self.fake.write_text(FAKE); self.fake.chmod(0o700)
        self.history = self.h.base/'fake-history.json'
        self.env = {**os.environ,'AF_FAKE_HISTORY':str(self.history), 'PYTHONDONTWRITEBYTECODE':'1'}
        request = self.h.base/'request.md'; request.write_text('bounded migration fixture')
        self.request = request

    def command(self, scripts, script, *args):
        value = subprocess.run([sys.executable,str(scripts/script),*args,'--project-root',str(self.h.root)],
            env=self.env, capture_output=True,text=True,timeout=30)
        self.assertEqual(value.returncode,0,value.stdout+value.stderr)
        return json.loads(value.stdout)

    def wait_child(self, scripts, child):
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            state = self.command(scripts,'exec.py','status','--agent',child['agentId'],'--run-id',child['runId'])['run']
            if state['status']=='completed':
                # Wait for supervisor containment to empty; no status fabrication.
                directory = (self.h.root/'.agent-factory/agent' if scripts==self.old else Path(paths.resolve(self.h.root)['agentsRoot']))
                raw = json.loads((directory/child['agentId']/'runs'/child['runId']/'state.json').read_text())
                try: migration.writer_free(raw)
                except ValueError: time.sleep(.05); continue
                return
            self.assertNotIn(state['status'], {'failed','cancelled','needs-human-decision'})
            time.sleep(.05)
        self.fail('fake managed child did not complete')

    def start(self):
        return self.command(self.old,'loop.py','start','--request-file',str(self.request),
            '--work-agent','work','--verification-agent','verification','--codex',str(self.fake), '--sandbox','danger-full-access')

    def migrate(self):
        plan = migration.make_plan([str(self.h.root)],self.h.home)
        migration.copy(plan,self.h.base/'backup')
        evidence = self.h.evidence(plan)
        migration.activate(plan,evidence)
        return plan

    def test_fail_returns_to_same_work_and_same_verification_then_pass(self):
        state = self.start(); self.wait_child(self.old,state['currentChild'])
        state = self.command(self.old,'loop.py','reconcile','--work-agent','work','--loop-id',state['loopId'])
        self.wait_child(self.old,state['currentChild'])
        plan = self.migrate()
        for _ in range(5):
            state = self.command(self.new,'loop.py','reconcile','--work-agent','work','--loop-id',state['loopId'])
            if state['status']=='completed': break
            self.wait_child(self.new,state['currentChild'])
        self.assertEqual(state['status'],'completed')
        records = json.loads(self.history.read_text())
        self.assertEqual([r['role'] for r in records],['work','verification','work','verification'])
        self.assertEqual([r['resume'] for r in records],[None,None,'exact-work-session','exact-verification-session'])
        migration.copied_inventory(plan)  # Runtime mutation must never alter archive/projection.

    def test_human_skip_after_migrated_work_starts_no_verification(self):
        state = self.start(); self.wait_child(self.old,state['currentChild'])
        plan = self.migrate()
        self.command(self.new,'loop.py','skip','--work-agent','work','--loop-id',state['loopId'],
            '--actor','human','--authorization-reference','fixture-only','--decision-evidence','fixture Human skip')
        state = self.command(self.new,'loop.py','reconcile','--work-agent','work','--loop-id',state['loopId'])
        self.assertEqual(state['status'],'completed')
        self.assertEqual(len(json.loads(self.history.read_text())),1)
        migration.copied_inventory(plan)
