from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "gather" / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_test", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


class GatherProviderScriptTests(unittest.TestCase):
    def test_gmail_evidence_interruption_preserves_prior_complete_bytes(self) -> None:
        gmail = load_script("sync_gmail")
        support_os = sys.modules[gmail.DestinationStore.__module__].os
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "original"
            relative = Path("messages") / "M1.eml"
            with gmail.DestinationStore(destination) as store:
                store.write_bytes(relative, b"complete-old-message")
                with mock.patch.object(
                    support_os, "replace", side_effect=OSError("interrupted")
                ):
                    with self.assertRaisesRegex(OSError, "interrupted"):
                        store.write_bytes(relative, b"partial-new-message")

            self.assertEqual(
                (destination / relative).read_bytes(), b"complete-old-message"
            )
            self.assertEqual(
                list((destination / "messages").glob(".gather.*")), []
            )

    def test_private_files_are_external_regular_atomic_and_user_only(self) -> None:
        support = load_script("provider_support")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "project"
            external = base / "config" / "token.json"
            project.mkdir()

            with self.assertRaisesRegex(RuntimeError, "outside the Git project"):
                support.write_private_text(
                    project / "token.json", "secret", project, "OAuth token"
                )

            support.write_private_text(external, "old-secret", project, "OAuth token")
            self.assertEqual(
                stat.S_IMODE(external.stat().st_mode),
                0o600,
            )
            with mock.patch.object(
                support.os, "replace", side_effect=OSError("interrupted")
            ):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    support.write_private_text(
                        external, "new-secret", project, "OAuth token"
                    )
            self.assertEqual(external.read_text(encoding="utf-8"), "old-secret")
            self.assertEqual(list(external.parent.glob(".credential.*")), [])

            symlink = base / "config" / "linked-token.json"
            symlink.symlink_to(external)
            with self.assertRaises((OSError, RuntimeError)):
                support.read_private_text(symlink, project, "OAuth token")
            with self.assertRaises((OSError, RuntimeError)):
                support.write_private_text(
                    symlink, "replacement", project, "OAuth token"
                )
            self.assertEqual(external.read_text(encoding="utf-8"), "old-secret")

            directory_target = base / "config" / "directory-token"
            directory_target.mkdir()
            with self.assertRaises(RuntimeError):
                support.read_private_text(
                    directory_target, project, "OAuth token", required=True
                )
            with self.assertRaises(RuntimeError):
                support.write_private_text(
                    directory_target, "replacement", project, "OAuth token"
                )

    def test_all_oauth_providers_reject_project_local_secret_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            client = project / "client.json"
            client.write_text("{}", encoding="utf-8")
            token = project / "token.json"

            gmail = load_script("sync_gmail")
            drive = load_script("sync_google_drive")
            onedrive = load_script("sync_onedrive")

            with self.assertRaisesRegex(RuntimeError, "outside the Git project"):
                gmail.load_credentials(client, token, project)
            with self.assertRaisesRegex(RuntimeError, "outside the Git project"):
                drive.credentials(client, token, project)
            with self.assertRaisesRegex(RuntimeError, "outside the Git project"):
                onedrive.access_token("client-id", "common", token, False, project)

    def test_slack_snapshot_removes_private_download_urls(self) -> None:
        module = load_script("sync_slack")
        messages = [
            {
                "ts": "1.0",
                "files": [
                    {
                        "id": "F1",
                        "name": "evidence.txt",
                        "url_private": "https://files.slack.test/private",
                        "url_private_download": "https://files.slack.test/download",
                        "permalink": "https://workspace.slack.test/files/F1",
                    }
                ],
            }
        ]

        sanitized = module.sanitized_messages(messages)

        serialized = json.dumps(sanitized)
        self.assertNotIn("url_private", serialized)
        self.assertIn("permalink", serialized)
        self.assertIn("url_private_download", messages[0]["files"][0])

    def test_provider_resolves_destination_before_reading_secret(self) -> None:
        for script_name, argv in (
            ("sync_slack", ["sync_slack.py", "--channel-id", "C1"]),
            ("sync_notion", ["sync_notion.py", "--page-id", "P1"]),
            ("sync_discord", ["sync_discord.py", "--channel-id", "C1"]),
        ):
            module = load_script(script_name)
            with self.subTest(script=script_name), mock.patch.object(
                module, "resolve", side_effect=RuntimeError("resolved-first")
            ) as resolved, mock.patch.object(module, "require_env") as secret, mock.patch(
                "sys.argv", argv
            ):
                with self.assertRaisesRegex(RuntimeError, "resolved-first"):
                    module.main()
                resolved.assert_called_once()
                secret.assert_not_called()

    def test_drive_providers_resolve_before_credentials_or_authentication(self) -> None:
        cases = (
            (
                "sync_google_drive",
                ["sync_google_drive.py", "--folder-id", "F1"],
                "credentials",
            ),
            (
                "sync_onedrive",
                ["sync_onedrive.py", "--item-id", "I1"],
                "access_token",
            ),
        )
        for script_name, argv, auth_name in cases:
            module = load_script(script_name)
            with self.subTest(script=script_name), mock.patch.object(
                module, "resolve", side_effect=RuntimeError("resolved-first")
            ) as resolved, mock.patch.object(module, auth_name) as authenticate, mock.patch(
                "sys.argv", argv
            ):
                with self.assertRaisesRegex(RuntimeError, "resolved-first"):
                    module.main()
                resolved.assert_called_once()
                authenticate.assert_not_called()

    def test_destination_store_replaces_regular_files_atomically(self) -> None:
        support = load_script("provider_support")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "original"
            with support.DestinationStore(destination) as store:
                store.write_bytes("evidence/item.bin", b"first")
                store.write_bytes("evidence/item.bin", b"second")

            self.assertEqual(
                (destination / "evidence/item.bin").read_bytes(), b"second"
            )
            self.assertEqual(list((destination / "evidence").glob(".gather.*")), [])

    def test_provider_sanitizers_encoding_pagination_and_provenance(self) -> None:
        discord = load_script("sync_discord")
        drive = load_script("sync_google_drive")
        gmail = load_script("sync_gmail")
        notion = load_script("sync_notion")
        onedrive = load_script("sync_onedrive")
        support = load_script("provider_support")

        discord_source = [
            {
                "id": "M1",
                "attachments": [
                    {"id": "A1", "url": "signed", "proxy_url": "proxy"}
                ],
            }
        ]
        discord_saved = discord.sanitized_messages(discord_source)
        self.assertNotIn("url", discord_saved[0]["attachments"][0])
        self.assertIn("url", discord_source[0]["attachments"][0])

        notion_source = {
            "type": "file",
            "file": {"url": "temporary", "expiry_time": "soon"},
        }
        notion_saved = notion.sanitized_evidence(notion_source)
        self.assertNotIn("url", notion_saved["file"])
        self.assertEqual(notion_source["file"]["url"], "temporary")

        self.assertEqual(
            onedrive.graph_selected_path("folder one/a#b"),
            "folder%20one/a%23b",
        )
        drive_files = mock.Mock()
        first_page = mock.Mock()
        first_page.execute.return_value = {
            "files": [{"id": "D1"}],
            "nextPageToken": "page-2",
        }
        second_page = mock.Mock()
        second_page.execute.return_value = {"files": [{"id": "D2"}]}
        drive_files.list.side_effect = [first_page, second_page]
        drive_service = mock.Mock()
        drive_service.files.return_value = drive_files
        self.assertEqual(
            [item["id"] for item in drive.children(drive_service, "F1")],
            ["D1", "D2"],
        )
        self.assertEqual(
            drive_files.list.call_args_list[1].kwargs["pageToken"], "page-2"
        )

        gmail_messages = mock.Mock()
        gmail_first = mock.Mock()
        gmail_first.execute.return_value = {"messages": [{"id": "G1"}, {"id": "G2"}]}
        gmail_second = mock.Mock()
        gmail_second.execute.return_value = {"messages": [{"id": "G3"}, {"id": "G4"}]}
        gmail_messages.list.return_value = gmail_first
        gmail_messages.list_next.return_value = gmail_second
        gmail_service = mock.Mock()
        gmail_service.users.return_value.messages.return_value = gmail_messages
        self.assertEqual(
            gmail.list_message_ids(gmail_service, "subject:test", 3),
            ["G1", "G2", "G3"],
        )

        payload = b"abc"
        entry = support.provenance(
            "I1", "https://source.test/I1", Path("files/I1"), payload
        )
        self.assertEqual(entry["size"], len(payload))
        self.assertEqual(
            entry["sha256"],
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )
        with tempfile.TemporaryDirectory() as temporary:
            with support.DestinationStore(Path(temporary) / "original") as store:
                support.save_index(store, {entry["id"]: entry})
                loaded = support.load_index(store)
            self.assertEqual(loaded["I1"]["source_url"], entry["source_url"])
            self.assertEqual(loaded["I1"]["sha256"], entry["sha256"])


if __name__ == "__main__":
    unittest.main()
