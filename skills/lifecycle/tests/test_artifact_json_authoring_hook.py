from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
GUARD = PLUGIN_ROOT / "hooks" / "artifact_json_guard.py"
GENERATOR = PLUGIN_ROOT / "hooks" / "generate_hooks_config.py"
HOOKS_CONFIG = PLUGIN_ROOT / "hooks" / "hooks.json"
SESSION_ID = "019f9c41-ba3a-7003-8ab6-bfa0d75d7b26"


def hook_payload(
    tool_name: str,
    command: str,
    cwd: Path,
    *,
    session_id: str = SESSION_ID,
) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "turn_id": "turn-test",
            "cwd": str(cwd),
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": {"command": command},
            "tool_use_id": "tool-test",
        }
    )


def run_guard(
    tool_name: str,
    command: str,
    cwd: Path,
    plugin_data: Path,
    *,
    session_id: str = SESSION_ID,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    environment["PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run(
        [sys.executable, str(GUARD), "hook"],
        input=hook_payload(tool_name, command, cwd, session_id=session_id),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )


class ArtifactJsonAuthoringHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.root.mkdir()
        self.target = (
            self.root
            / ".agent-factory"
            / "intakes"
            / "intake-001"
            / "data"
            / "metadata.json"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_apply_patch_add_update_delete_and_move_are_denied(self) -> None:
        operations = [
            f"*** Add File: {self.target}",
            f"*** Update File: {self.target}",
            f"*** Delete File: {self.target}",
            f"*** Move to: {self.target}",
        ]
        for operation in operations:
            patch = f"*** Begin Patch\n{operation}\n+x\n*** End Patch\n"
            with self.subTest(operation=operation):
                result = run_guard(
                    "apply_patch", patch, self.root, self.plugin_data
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("canonical Artifact JSON", result.stderr)
                self.assertIn(str(self.target), result.stderr)
                self.assertEqual(result.stdout, "")

    def test_apply_patch_outside_canonical_artifacts_is_allowed(self) -> None:
        patch = (
            "*** Begin Patch\n"
            "*** Add File: config/example.json\n"
            "+{}\n"
            "*** End Patch\n"
        )
        result = run_guard("apply_patch", patch, self.root, self.plugin_data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_apply_patch_aliases_are_denied(self) -> None:
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {self.target}\n"
            "@@\n"
            "-old\n"
            "+new\n"
            "*** End Patch\n"
        )
        for tool_name in ("Edit", "Write"):
            with self.subTest(tool_name=tool_name):
                result = run_guard(
                    tool_name,
                    patch,
                    self.root,
                    self.plugin_data,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("canonical Artifact JSON", result.stderr)

    def test_bash_direct_write_variants_are_denied(self) -> None:
        target = str(self.target)
        commands = [
            f"printf '%s' '{{}}' > '{target}'",
            f"python3 -c \"from pathlib import Path; Path('{target}').write_text('{{}}')\"",
            f"cp source.json '{target}'",
            f"mv source.json '{target}'",
            (
                "python3 - <<'PY'\n"
                "from pathlib import Path\n"
                f"Path('{target}').write_text('{{}}')\n"
                "PY"
            ),
        ]
        for command in commands:
            with self.subTest(command=command):
                result = run_guard("Bash", command, self.root, self.plugin_data)
                self.assertEqual(result.returncode, 2)
                self.assertIn("canonical Artifact JSON", result.stderr)

    def test_each_canonical_artifact_collection_is_denied(self) -> None:
        targets = [
            self.target,
            (
                self.root
                / ".agent-factory"
                / "work-units"
                / "work-001"
                / "data"
                / "metadata.json"
            ),
            (
                self.root
                / ".agent-factory"
                / "specifications"
                / "spec-001"
                / "data"
                / "metadata.json"
            ),
        ]
        for target in targets:
            command = f"custom-json-writer '{target}'"
            with self.subTest(target=target):
                result = run_guard("Bash", command, self.root, self.plugin_data)
                self.assertEqual(result.returncode, 2)
                self.assertIn(str(target), result.stderr)

    def test_split_canonical_root_with_write_intent_is_denied(self) -> None:
        command = (
            "base=.agent-factory; kind=intakes; "
            "python3 -c \"from pathlib import Path; "
            "Path(f'{base}/{kind}/x/data/metadata.json').write_text('{}')\""
        )
        result = run_guard("Bash", command, self.root, self.plugin_data)
        self.assertEqual(result.returncode, 2)
        self.assertIn("dynamically constructed canonical path", result.stderr)

    def test_obfuscated_collection_and_root_writes_are_denied(self) -> None:
        commands = [
            (
                "root=.agent-factory; left=inta; right=kes; "
                "printf '{}' > \"$root/$left$right/x/data/metadata.json\""
            ),
            "root=.agent-factory; rm -rf \"$root\"",
        ]
        for command in commands:
            with self.subTest(command=command):
                result = run_guard("Bash", command, self.root, self.plugin_data)
                self.assertEqual(result.returncode, 2)
                self.assertIn(
                    "dynamically constructed canonical path",
                    result.stderr,
                )

    def test_exact_manager_commands_are_allowed(self) -> None:
        manager_commands = [
            (
                f"python3 '{PLUGIN_ROOT / 'skills/intake/scripts/intake.py'}' "
                f"title-set '{self.root / '.agent-factory/intakes/intake-001'}' "
                "'Title'"
            ),
            (
                "python3 "
                f"'{PLUGIN_ROOT / 'skills/work-unit-planner/assets/scripts/work_unit.py'}' "
                f"validate '{self.root / '.agent-factory/work-units/work-001'}' "
                "--full"
            ),
            (
                f"python3 '{PLUGIN_ROOT / 'skills/specification/scripts/specification.py'}' "
                f"validate '{self.root / '.agent-factory/specifications/spec-001'}' "
                "--full"
            ),
        ]
        for command in manager_commands:
            with self.subTest(command=command):
                result = run_guard("Bash", command, self.root, self.plugin_data)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_manager_suffix_outside_plugin_root_is_denied(self) -> None:
        command = (
            "python3 /tmp/evil/skills/intake/scripts/intake.py title-set "
            f"'{self.root / '.agent-factory/intakes/intake-001'}' 'Title'"
        )
        result = run_guard("Bash", command, self.root, self.plugin_data)
        self.assertEqual(result.returncode, 2)

    def test_manager_command_chaining_is_denied(self) -> None:
        command = (
            "python3 skills/intake/scripts/intake.py validate "
            ".agent-factory/intakes/intake-001 --full; "
            "printf '{}' > .agent-factory/intakes/intake-001/data/metadata.json"
        )
        result = run_guard("Bash", command, self.root, self.plugin_data)
        self.assertEqual(result.returncode, 2)

    def test_read_only_and_non_artifact_json_commands_are_allowed(self) -> None:
        commands = [
            "rg -n title .agent-factory/intakes/intake-001/data/metadata.json",
            "git diff -- .agent-factory/work-units/work-001/data/metadata.json",
            "printf '%s' '{}' > config/example.json",
        ]
        for command in commands:
            with self.subTest(command=command):
                result = run_guard("Bash", command, self.root, self.plugin_data)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_hook_input_fails_closed(self) -> None:
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        result = subprocess.run(
            [sys.executable, str(GUARD), "hook"],
            input="{",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid PreToolUse input", result.stderr)

    def grant(
        self,
        path: Path,
        *,
        tool_name: str = "apply_patch",
        session_id: str = SESSION_ID,
        ttl_seconds: int = 300,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(GUARD),
                "grant",
                "--plugin-data",
                str(self.plugin_data),
                "--session-id",
                session_id,
                "--tool-name",
                tool_name,
                "--path",
                str(path),
                "--reason",
                "manager recovery cannot express this repair",
                "--approval-reference",
                "Human message approval-test",
                "--human-decision",
                "approved",
                "--ttl-seconds",
                str(ttl_seconds),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_grant_requires_explicit_approved_decision(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(GUARD),
                "grant",
                "--plugin-data",
                str(self.plugin_data),
                "--session-id",
                SESSION_ID,
                "--tool-name",
                "apply_patch",
                "--path",
                str(self.target),
                "--reason",
                "recovery",
                "--approval-reference",
                "Human message approval-test",
                "--human-decision",
                "rejected",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.plugin_data / "artifact-json-exceptions").exists())

    def test_exact_grant_command_is_not_recursively_blocked(self) -> None:
        command = (
            f"python3 '{GUARD}' grant "
            f"--plugin-data '{self.plugin_data}' "
            f"--session-id '{SESSION_ID}' "
            "--tool-name apply_patch "
            f"--path '{self.target}' "
            "--reason 'manager recovery cannot express this repair' "
            "--approval-reference 'Human message approval-test' "
            "--human-decision approved"
        )
        result = run_guard("Bash", command, self.root, self.plugin_data)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_one_shot_exact_scope_grant_is_consumed_and_audited(self) -> None:
        granted = self.grant(self.target)
        self.assertEqual(granted.returncode, 0, granted.stderr)
        self.assertIn("grant recorded", granted.stdout)

        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {self.target}\n"
            "@@\n"
            "-old\n"
            "+new\n"
            "*** End Patch\n"
        )
        first = run_guard("apply_patch", patch, self.root, self.plugin_data)
        second = run_guard("apply_patch", patch, self.root, self.plugin_data)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 2)

        audit_path = (
            self.plugin_data
            / "artifact-json-exceptions"
            / "audit.jsonl"
        )
        events = [
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual([event["event"] for event in events], ["granted", "consumed"])
        self.assertEqual(events[0]["artifactType"], "intake")
        self.assertEqual(events[0]["artifactId"], "intake-001")
        self.assertEqual(events[0]["paths"], [str(self.target)])
        self.assertEqual(events[0]["approvalReference"], "Human message approval-test")

    def test_scope_session_tool_and_expiry_mismatch_fail_closed(self) -> None:
        other = self.target.with_name("title.json")
        scenarios = [
            ("path", self.target, "apply_patch", "different-session", other),
            ("tool", self.target, "Bash", SESSION_ID, self.target),
            ("session", self.target, "apply_patch", "different-session", self.target),
        ]
        for name, granted_path, tool_name, session_id, attempted_path in scenarios:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as plugin_data_raw:
                    plugin_data = Path(plugin_data_raw)
                    original = self.plugin_data
                    self.plugin_data = plugin_data
                    try:
                        granted = self.grant(
                            granted_path,
                            tool_name=tool_name,
                            session_id=session_id,
                        )
                        self.assertEqual(granted.returncode, 0, granted.stderr)
                        patch = (
                            "*** Begin Patch\n"
                            f"*** Update File: {attempted_path}\n"
                            "@@\n-old\n+new\n"
                            "*** End Patch\n"
                        )
                        result = run_guard(
                            "apply_patch",
                            patch,
                            self.root,
                            plugin_data,
                            session_id=SESSION_ID,
                        )
                        self.assertEqual(result.returncode, 2)
                    finally:
                        self.plugin_data = original

        granted = self.grant(self.target, ttl_seconds=1)
        self.assertEqual(granted.returncode, 0, granted.stderr)
        grants = list(
            (self.plugin_data / "artifact-json-exceptions" / "grants").glob("*.json")
        )
        self.assertEqual(len(grants), 1)
        record = json.loads(grants[0].read_text(encoding="utf-8"))
        record["expiresAtEpoch"] = 0
        grants[0].write_text(
            json.dumps(record, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {self.target}\n"
            "@@\n-old\n+new\n"
            "*** End Patch\n"
        )
        expired = run_guard("apply_patch", patch, self.root, self.plugin_data)
        self.assertEqual(expired.returncode, 2)

    def test_multi_path_patch_requires_exact_grant_scope(self) -> None:
        self.assertEqual(self.grant(self.target).returncode, 0)
        other = self.target.with_name("title.json")
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {self.target}\n"
            "@@\n-old\n+new\n"
            f"*** Update File: {other}\n"
            "@@\n-old\n+new\n"
            "*** End Patch\n"
        )
        result = run_guard("apply_patch", patch, self.root, self.plugin_data)
        self.assertEqual(result.returncode, 2)

    def test_hook_configuration_is_generated_and_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(HOOKS_CONFIG.read_text(encoding="utf-8"))
        groups = value["hooks"]["PreToolUse"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0]["matcher"],
            "^(Bash|apply_patch|Edit|Write)$",
        )
        command = groups[0]["hooks"][0]["command"]
        self.assertEqual(
            command,
            'python3 "$PLUGIN_ROOT/hooks/artifact_json_guard.py" hook',
        )

    def test_skill_contracts_require_manager_only_and_human_approved_exception(
        self,
    ) -> None:
        skill_paths = [
            PLUGIN_ROOT / "skills" / "intake" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "work-unit-planner" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "specification" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "lifecycle" / "SKILL.md",
        ]
        for path in skill_paths:
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path):
                self.assertIn("apply_patch", text)
                self.assertIn("shell redirection", text)
                self.assertIn("explicit Human approval", text)
                self.assertIn("filesystem-capable", text)
                self.assertIn("manager", text)


if __name__ == "__main__":
    unittest.main()
