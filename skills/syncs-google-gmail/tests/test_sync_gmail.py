from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_gmail.py"


def load_script():
    spec = importlib.util.spec_from_file_location("sync_gmail_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GmailDestinationTests(unittest.TestCase):
    def test_main_resolves_and_displays_destination_before_credentials_or_writes(
        self,
    ) -> None:
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(
                ["git", "init", "-q", "-b", "main"],
                cwd=root,
                check=True,
            )
            (root / "nested").mkdir()
            client = root / "client.json"
            client.write_text("{}", encoding="utf-8")
            destination = root / "configured/mail"

            with (
                mock.patch.object(
                    module,
                    "resolve_sync_destination",
                    return_value={
                        "source": "google-gmail",
                        "projectRoot": str(root),
                        "destination": str(destination),
                        "origin": "config",
                        "configPath": str(root / ".agent-factory/sync.json"),
                    },
                ),
                mock.patch.object(
                    module, "load_credentials", side_effect=RuntimeError("stop")
                ),
                mock.patch(
                    "sys.argv",
                    [
                        "sync_gmail.py",
                        "--query",
                        "subject:test",
                        "--client",
                        str(client),
                    ],
                ),
                mock.patch("builtins.print") as printed,
            ):
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    module.main()

            first = json.loads(printed.call_args_list[0].args[0])
            self.assertEqual(first["event"], "destination-resolved")
            self.assertEqual(first["destination"], str(destination))
            self.assertFalse(destination.exists())

    def test_destination_store_rejects_directory_swap_without_writing_outside(
        self,
    ) -> None:
        module = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "mail"
            original = root / "mail-original"
            outside = root / "outside"
            destination.mkdir()
            real_open = module.os.open
            swapped = False

            def swapping_open(path, flags, *args, **kwargs):
                nonlocal swapped
                if (
                    path == "mail"
                    and kwargs.get("dir_fd") is not None
                    and not swapped
                ):
                    destination.rename(original)
                    outside.mkdir()
                    destination.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(module.os, "open", side_effect=swapping_open):
                with self.assertRaises(OSError):
                    with module.DestinationStore(destination):
                        pass

            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
