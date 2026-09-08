"""Installed Codex permission enforcement against an isolated project."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from home_fixtures import HomeRuntimeFixture, paths
import native_codex
import permissions


class NativePermissionTests(HomeRuntimeFixture, unittest.TestCase):
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
