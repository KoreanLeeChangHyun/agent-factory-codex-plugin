"""Behavioral cache regressions for independent Verification (no timing assertions)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/agent/runtime'))
import native_codex as native


class CapabilityCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = mock.patch.dict(os.environ, {
            'HOME': str(self.root), 'CODEX_HOME': str(self.root / 'codex-home'),
            'AGENT_FACTORY_HOME': str(self.root / 'runtime'), 'AF_CODEX_CAPABILITY_CACHE': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.binary = self.root / 'codex'
        self.binary.write_text('#!' + sys.executable + '\n' + '''
import json, sys
from pathlib import Path
root = Path(__file__).parent
with (root / 'probes').open('a') as stream:
    stream.write('probe\\n')
if (root / 'fail').exists():
    sys.exit(1)
out = Path(sys.argv[-1])
(out / 'v2').mkdir()
for name in ('TurnStartParams', 'ThreadStartParams', 'ThreadResumeParams'):
    (out / 'v2' / (name + '.json')).write_text(json.dumps({'properties': {'serviceTier': {}, 'outputSchema': {}}}))
(out / 'v2/ModelListResponse.json').write_text(json.dumps({'definitions': {'Model': {'properties': {'serviceTiers': {}}}}}))
(out / 'v2/ThreadGoalSetParams.json').write_text(json.dumps({'definitions': {'ThreadGoalStatus': {'enum': ['active', 'paused', 'complete']}}}))
(out / 'ClientRequest.json').write_text(json.dumps(['thread/goal/set', 'thread/goal/get', 'thread/goal/clear']))
''')
        self.binary.chmod(0o700)
        self.cache = self.root / 'runtime/cache/native-capabilities/capabilities.json'

    def probe(self):
        return native.inspect_capabilities(str(self.binary), refresh=True,
                                           runtime_home=self.root / 'runtime')

    def count(self):
        return len((self.root / 'probes').read_text().splitlines())

    def child(self):
        source = 'import sys; sys.path.insert(0, sys.argv[1]); import native_codex; native_codex.inspect_capabilities(sys.argv[2], refresh=True, runtime_home=sys.argv[3])'
        return subprocess.Popen([sys.executable, '-c', source, str(Path(native.__file__).parent),
                                 str(self.binary), str(self.root / 'runtime')], env=dict(os.environ))

    def test_pure_query_does_not_create_or_change_runtime_home(self):
        runtime_home = self.root / 'runtime'
        before = runtime_home.exists()
        result = native.inspect_capabilities(str(self.binary), runtime_home=self.root / 'runtime')
        self.assertTrue(result['submit']['fast'])
        self.assertEqual(before, runtime_home.exists())

    def test_calls_and_processes_reuse_success(self):
        first = self.probe()
        self.assertTrue(first['submit']['fast'])
        first['submit']['fast'] = False
        self.assertTrue(self.probe()['submit']['fast'])
        self.assertEqual(self.child().wait(timeout=10), 0)
        self.assertEqual(self.count(), 1)

    def test_concurrent_processes_share_success(self):
        children = [self.child() for _ in range(3)]
        for child in children:
            self.assertEqual(child.wait(timeout=10), 0)
        self.assertEqual(self.count(), 1)

    def test_binary_change_and_symlink_target_invalidate(self):
        self.probe()
        self.binary.write_text(self.binary.read_text() + '\n# changed\n')
        self.probe()
        other = self.root / 'other'
        other.write_bytes(self.binary.read_bytes())
        other.chmod(0o700)
        link = self.root / 'selected'
        link.symlink_to(self.binary)
        self.assertIsNone(native.inspect_capabilities(str(link))['diagnostic'])
        self.assertEqual(self.count(), 2)
        link.unlink()
        link.symlink_to(other)
        native.inspect_capabilities(str(link))
        self.assertEqual(self.count(), 3)

    def test_expiry_future_timestamp_and_codex_home_isolation(self):
        self.probe()
        for created in (0, 10**20):
            value = json.loads(self.cache.read_text())
            value['created'] = created
            self.cache.write_text(json.dumps(value))
            self.probe()
        with mock.patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'different')}):
            self.probe()
        self.assertEqual(self.count(), 4)

    def test_oversized_integer_timestamp_is_reprobed(self):
        expected = self.probe()
        self.assertIsNone(expected['diagnostic'])
        for index, created in enumerate((10**400, -(10**400)), start=2):
            with self.subTest(created=created):
                value = json.loads(self.cache.read_text())
                value['created'] = created
                self.cache.write_text(json.dumps(value))
                self.assertEqual(self.probe(), expected)
                self.assertEqual(self.count(), index)

    def test_failures_and_corruption_are_reprobed(self):
        (self.root / 'fail').touch()
        self.assertIsNotNone(self.probe()['diagnostic'])
        self.assertIsNotNone(self.probe()['diagnostic'])
        self.assertFalse(self.cache.exists())
        (self.root / 'fail').unlink()
        self.probe()
        for bad in ('not json', '[]', '{"version":1}', self.cache.read_text().replace('true', '1')):
            self.cache.write_text(bad)
            self.assertIsNone(self.probe()['diagnostic'])
        self.assertEqual(self.count(), 7)

    def test_disabled_and_unwritable_fallback(self):
        with mock.patch.dict(os.environ, {'AF_CODEX_CAPABILITY_CACHE': '0'}):
            self.probe()
            self.probe()
        self.assertFalse(self.cache.exists())
        import paths
        with mock.patch.object(paths, 'mkdir', side_effect=PermissionError('read-only cache')):
            self.probe()
        with mock.patch.object(paths, 'write', side_effect=PermissionError('read-only cache')):
            self.probe()
        self.assertEqual(self.count(), 4)

    def test_unsafe_cache_link_and_missing_executable_fall_back(self):
        outside = self.root / 'outside'
        outside.mkdir()
        cache_root = self.root / 'runtime/cache'
        cache_root.mkdir(parents=True)
        (cache_root / 'native-capabilities').symlink_to(outside)
        self.probe()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertIsNotNone(native.inspect_capabilities(str(self.root / 'missing'))['diagnostic'])
        self.assertEqual(self.count(), 1)


if __name__ == '__main__':
    unittest.main()
