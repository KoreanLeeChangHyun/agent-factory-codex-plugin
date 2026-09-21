"""Former transport and payload ceilings must not reject valid user work."""
import runtime_test_home
import io
import json
import queue
import tempfile
import unittest
from pathlib import Path
from native_fixtures import runtime


class UnlimitedPayloads(unittest.TestCase):
    def test_large_request_logs_and_result_keep_all_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b'x' * (9 * 1024 * 1024)
            request = root / 'request.md'
            request.write_bytes(content)
            self.assertEqual(runtime.safe_read_bytes(request, runtime.MAX_REQUEST_BYTES), content)
            events = root / 'events.jsonl'
            writer = runtime.process_transport.EventLogWriter(events)
            try:
                self.assertTrue(writer.append(content.decode() + '\n'))
            finally:
                writer.close()
            self.assertEqual(events.read_bytes(), content + b'\n')
            stderr = root / 'stderr.log'
            output = queue.Queue()
            runtime.process_transport.stream_stderr(io.StringIO(content.decode()), stderr, output)
            self.assertEqual(stderr.read_bytes(), content)
            self.assertEqual(output.get_nowait(), ('stderr_eof', None))
            state = {'resultPath': str(root / 'result.md'), 'responseSchemaPath': str(root / 'schema.json')}
            (root / 'schema.json').write_text(json.dumps(runtime.process_transport.response_schema_document(state['resultPath'])))
            result = {'status': 'completed', 'resultPath': state['resultPath'], 'resultText': '한' * 40000}
            self.assertEqual(runtime.process_transport.validate_terminal_result(result, state), result['resultText'].encode())

    def test_default_rpc_has_no_deadline(self):
        import inspect
        self.assertIsNone(inspect.signature(runtime.native_codex.Rpc.call).parameters['timeout'].default)

    def test_large_internal_event_preserves_following_event(self):
        output = queue.Queue()
        line = 'x' * (2 * 1024 * 1024) + '\n'
        runtime.read_process_lines(io.StringIO(line + 'next\n'), output)
        self.assertEqual(output.get_nowait(), ('line', line))
        self.assertEqual(output.get_nowait(), ('line', 'next\n'))
        self.assertEqual(output.get_nowait(), ('stdout_eof', None))
