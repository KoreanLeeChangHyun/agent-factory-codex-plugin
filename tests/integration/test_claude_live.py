"""Opt-in real Claude integration; consumes the operator's CLI authentication.

AF_TEST_CLAUDE_LIVE=1 PYTHONPATH=tests/support:tests/integration python3 -m unittest test_claude_live
"""
import runtime_test_home
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import struct
import zlib

SCRIPT = Path(__file__).resolve().parents[2] / "skills/agent/scripts/exec.py"


@unittest.skipUnless(os.environ.get("AF_TEST_CLAUDE_LIVE") == "1", "real Claude integration is opt-in")
class ClaudeLiveTests(unittest.TestCase):
    def test_submit_resume_tool_execution_and_cancel(self):
        self.assertIsNotNone(shutil.which("claude"))
        with tempfile.TemporaryDirectory(prefix="af-claude-live-") as directory:
            root = Path(directory)
            agent = "main-claude-" + uuid.uuid4().hex

            def command(verb, *args):
                result = subprocess.run([sys.executable, str(SCRIPT), verb, "--project-root", str(root),
                                         "--agent", agent, *args], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                return json.loads(result.stdout)

            def wait(accepted):
                state_path = Path(accepted["statePath"])
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    state = json.loads(state_path.read_text())
                    if state["status"] in ("completed", "failed", "cancelled", "needs-human-decision"):
                        if state["status"] == "failed":
                            stderr = state_path.parent / "stderr.log"
                            print(json.dumps({"failure": state.get("error"),
                                              "stderr": stderr.read_text()[-5000:] if stderr.exists() else ""}), flush=True)
                        return state
                    time.sleep(.2)
                command("cancel", "--run-id", accepted["runId"])
                self.fail("Claude integration did not finish within its test deadline")

            first = command("submit", "--role", "main", "--model", "claude-opus", "--task-mode", "direct",
                            "--sandbox", "danger-full-access", "--approval-policy", "never",
                            "--human-approval-policy", "bypass", "--max-attempts", "1",
                            "--message", "This is a conversation test. Remember token LIVE_RESUME_4829. Reply with only SAVED in resultText. Do not use tools.")
            try:
                saved = wait(first)
                self.assertEqual(saved["status"], "completed", saved.get("error"))
                self.assertEqual(Path(saved["resultPath"]).read_text().strip(), "SAVED")
                second = command("send", "--message", "What token did I ask you to remember? Reply with only that token in resultText. Do not use tools.")
                resumed = wait(second)
                self.assertEqual(resumed["status"], "completed", resumed.get("error"))
                self.assertEqual(saved["sessionId"], resumed["sessionId"])
                self.assertEqual(Path(resumed["resultPath"]).read_text().strip(), "LIVE_RESUME_4829")
                third = command("send", "--message", "Use the Bash tool to run exactly: printf 'TOOL_OK' > adapter-canary.txt . Then read that file and report its exact contents in resultText. This is an authorized test in this temporary project; do not dispatch agents.")
                tool = wait(third)
                self.assertEqual(tool["status"], "completed", tool.get("error"))
                self.assertEqual((root / "adapter-canary.txt").read_text(), "TOOL_OK")
                events = [json.loads(line) for line in Path(tool["eventsPath"]).read_text().splitlines()]
                self.assertTrue(any(e.get("item", {}).get("type") == "command_execution" for e in events))
                # Synthetic fixture: a 32x32 solid red PNG, no external assets.
                def chunk(kind, data):
                    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
                png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 32, 8, 2, 0, 0, 0))
                png += chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\0\0" * 32) * 32)) + chunk(b"IEND", b"")
                (root / "color.png").write_bytes(png)
                image_input = root / "input.json"
                image_input.write_text(json.dumps({"schemaVersion": "0.1.0", "kind": "agent-input",
                    "message": "What is the dominant color in the attached image? Reply with its English color name only in resultText. Do not use tools.",
                    "images": [{"path": "color.png", "mediaType": "image/png"}]}))
                image = wait(command("send", "--input-file", str(image_input)))
                self.assertEqual(image["status"], "completed", image.get("error"))
                self.assertEqual(Path(image["resultPath"]).read_text().strip().lower(), "red")
                fourth = command("send", "--message", "Cancellation test: invoke the Bash tool now with command `sleep 60`. Do not dispatch agents.")
                deadline = time.monotonic() + 45
                active = None
                while time.monotonic() < deadline:
                    active = json.loads(Path(fourth["statePath"]).read_text())
                    event_path = Path(active["eventsPath"])
                    if event_path.exists() and any(e.get("type") == "item.started" and
                            e.get("item", {}).get("type") == "command_execution" and
                            'sleep 60' in e["item"].get("command", "") for e in
                            (json.loads(line) for line in event_path.read_text().splitlines())):
                        break
                    if active["status"] in ("failed", "completed"):
                        self.fail(f"Cancellation target finished before its sleeping tool: {active}")
                    time.sleep(.2)
                else:
                    command("cancel", "--run-id", fourth["runId"])
                    self.fail("Claude never started the cancellation test tool")
                command("cancel", "--run-id", fourth["runId"])
                cancelled = wait(fourth)
                self.assertEqual(cancelled["status"], "cancelled")
                print(json.dumps({"provider": "claude", "submit": saved["status"], "resume": resumed["status"],
                                  "sameSession": saved["sessionId"] == resumed["sessionId"], "tool": tool["status"],
                                  "image": image["status"], "cancel": cancelled["status"], "usage": tool.get("tokenUsage")}), flush=True)
            finally:
                # Stop any test-owned accepted execution even after an assertion fails.
                listing = subprocess.run([sys.executable, str(SCRIPT), "list", "--project-root", str(root)],
                                         capture_output=True, text=True, timeout=15)
                if listing.returncode == 0:
                    # Individual state files provide exact ownership; never cancel user runs.
                    for path in Path(os.environ["AGENT_FACTORY_HOME"]).glob(f"projects/*/agents/{agent}/runs/*/state.json"):
                        value = json.loads(path.read_text())
                        if value["status"] in ("accepted", "starting", "running", "recovering"):
                            command("cancel", "--run-id", value["runId"])


if __name__ == "__main__":
    unittest.main()
