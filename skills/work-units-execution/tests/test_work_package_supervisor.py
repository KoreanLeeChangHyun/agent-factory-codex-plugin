from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "work_package_supervisor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("work_package_supervisor", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Work Package supervisor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkPackageSupervisorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_process_death_after_ack_reinvokes_same_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            count = root / "count"
            fake = root / "fake.py"
            fake.write_text(
                textwrap.dedent(
                    f"""\
                    import json
                    from pathlib import Path

                    count = Path({str(count)!r})
                    attempt = int(count.read_text() if count.exists() else "0") + 1
                    count.write_text(str(attempt))
                    print(json.dumps({{"type": "ack", "packageId": "pkg", "invocationId": f"i-{{attempt}}"}}), flush=True)
                    if attempt == 1:
                        raise SystemExit(7)
                    print(json.dumps({{"type": "heartbeat", "packageId": "pkg"}}), flush=True)
                    print(json.dumps({{"type": "terminal", "ok": True, "packageId": "pkg", "state": "review"}}), flush=True)
                    """
                ),
                encoding="utf-8",
            )
            events = []
            result = self.module.supervise(
                command_factory=lambda _attempt: [sys.executable, str(fake)],
                package_id="pkg",
                heartbeat_timeout=1,
                emit=events.append,
                max_restarts=2,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(count.read_text(), "2")
            self.assertTrue(
                any(event.get("type") == "supervisor-restart" for event in events)
            )

    def test_refusal_before_ack_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "fake.py"
            fake.write_text(
                "import sys\nsys.stderr.write('preflight refused\\n')\nraise SystemExit(2)\n",
                encoding="utf-8",
            )
            with self.assertRaises(self.module.SupervisorError):
                self.module.supervise(
                    command_factory=lambda _attempt: [sys.executable, str(fake)],
                    package_id="pkg",
                    heartbeat_timeout=1,
                    emit=lambda _event: None,
                    max_restarts=2,
                )


if __name__ == "__main__":
    unittest.main()
