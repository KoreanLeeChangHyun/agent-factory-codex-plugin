from __future__ import annotations

import runtime_test_home
import importlib.util
import io
import contextlib
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "skills/agent/scripts/exec.py"
spec = importlib.util.spec_from_file_location("worktree_runtime", SCRIPT)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
import worktrees


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Worktree Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "file.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-m", "base")
        runtime.runtime_paths.resolve(self.root, create=True)
        self.session("main-one")

    def git(self, *args, root=None):
        return worktrees.git(root or self.root, *args).stdout.decode().strip()

    def session(self, agent):
        path = runtime.agent_directory(self.root, agent, create=True) / "session.json"
        runtime.atomic_write_json(path, {"agentId": agent, "role": "main", "projectRoot": str(self.root),
            "sessionId": "thread-kept", "maxAttempts": 1})

    def command(self, action, *extra, agent="main-one"):
        args = runtime.parse_args(["worktree", "--project-root", str(self.root), "--agent", agent, action, *extra])
        out = io.StringIO()
        original = runtime.emit
        runtime.emit = lambda value: out.write(json.dumps(value))
        try:
            worktrees.command(runtime, args)
        finally:
            runtime.emit = original
        return json.loads(out.getvalue())

    def test_create_isolated_edit_merge_restore_and_history(self):
        created = self.command("create")
        path = Path(created["workingDirectory"])
        self.assertFalse(path.is_relative_to(self.root))
        self.assertEqual(path.parent.name, "worktrees")
        self.assertEqual(self.command("create")["workingDirectory"], str(path))
        (path / "file.txt").write_text("isolated\n")
        self.assertEqual((self.root / "file.txt").read_text(), "base\n")
        self.git("add", ".", root=path)
        self.git("commit", "-m", "isolated", root=path)
        result = self.command("merge")
        self.assertEqual(result["workingDirectory"], str(self.root))
        self.assertEqual(result["worktree"]["phase"], "merged")
        self.assertEqual((self.root / "file.txt").read_text(), "isolated\n")
        self.assertTrue(path.exists())
        self.assertEqual(runtime.load_session(self.root, "main-one")["sessionId"], "thread-kept")

    def test_conflict_stays_in_worktree_until_resolved_and_retried(self):
        path = Path(self.command("create")["workingDirectory"])
        for root, text in ((self.root, "workspace\n"), (path, "isolated\n")):
            (root / "file.txt").write_text(text)
            self.git("add", ".", root=root)
            self.git("commit", "-m", text.strip(), root=root)
        result = self.command("merge")
        self.assertEqual(result["worktree"]["phase"], "conflict")
        self.assertEqual(result["conflicts"], ["file.txt"])
        self.assertEqual(result["workingDirectory"], str(path))
        self.assertFalse(worktrees.dirty(self.root))
        self.assertFalse(worktrees.merge_pending(self.root))
        with self.assertRaisesRegex(runtime.ContractError, "Resolve conflicts"):
            self.command("merge")
        (path / "file.txt").write_text("both\n")
        self.git("add", ".", root=path)
        self.git("commit", "--no-edit", root=path)
        self.assertEqual(self.command("merge")["workingDirectory"], str(self.root))
        self.assertEqual((self.root / "file.txt").read_text(), "both\n")

    def test_copy_preserves_source_and_merge_refuses_dirty_target(self):
        (self.root / "file.txt").write_text("uncommitted\n")
        (self.root / "new.bin").write_bytes(b"\0\1")
        before = self.git("status", "--porcelain")
        with self.assertRaisesRegex(runtime.ContractError, "Choose whether"):
            self.command("create")
        path = Path(self.command("create", "--changes", "copy")["workingDirectory"])
        self.assertEqual((path / "file.txt").read_text(), "uncommitted\n")
        self.assertEqual((path / "new.bin").read_bytes(), b"\0\1")
        self.assertEqual(self.git("status", "--porcelain"), before)
        with self.assertRaisesRegex(runtime.ContractError, "workspace changes"):
            self.command("merge")
        self.assertEqual(self.command("status")["workingDirectory"], str(path))

    def test_multiple_conversations_busy_guard_and_run_capture(self):
        first = self.command("create")
        self.session("main-two")
        second = self.command("create", agent="main-two")
        self.assertNotEqual(first["workingDirectory"], second["workingDirectory"])
        session = runtime.load_session(self.root, "main-one")
        state = runtime.create_run(project_root=self.root, agent_id="main-one", actor="human", request=b"edit", session=session)
        self.assertEqual(state["workingDirectory"], first["workingDirectory"])
        with self.assertRaisesRegex(runtime.ContractError, "active runs"):
            self.command("merge")
        self.assertEqual(self.command("status", agent="main-two")["workingDirectory"], second["workingDirectory"])

    def test_changed_branch_and_missing_directory_fail_closed(self):
        path = Path(self.command("create")["workingDirectory"])
        self.git("checkout", "-b", "unexpected", root=path)
        with self.assertRaisesRegex(runtime.ContractError, "Restore.*branch"):
            worktrees.checked_path(runtime.load_session(self.root, "main-one"))
        path.rename(path.with_name(path.name + "-moved"))
        with self.assertRaisesRegex(runtime.ContractError, "missing"):
            worktrees.checked_path(runtime.load_session(self.root, "main-one"))

    def test_workspace_permissions_follow_the_conversation_and_return(self):
        session_path = runtime.session_file(self.root, "main-one")
        session = runtime.load_session(self.root, "main-one")
        session["executionPolicy"] = runtime_test_home.policy("workspace-write", self.root)
        session["sandbox"] = "workspace-write"
        runtime.atomic_write_json(session_path, session)
        path = Path(self.command("create")["workingDirectory"])
        session = runtime.load_session(self.root, "main-one")
        self.assertEqual(session["executionPolicy"]["sandboxPolicy"]["writable_roots"], [str(path)])
        environment = {key: value for key, value in os.environ.items() if key not in ("AGENT_FACTORY_EXECUTION_POLICY", "AGENT_FACTORY_PARENT_STATE", "CODEX_THREAD_ID")}
        with mock.patch.dict(os.environ, environment, clear=True):
            args = runtime.parse_args(["send", "--agent", "main-one"])
            self.assertEqual(runtime.resolve_execution_policy(args, self.root, session), session["executionPolicy"])
            args = runtime.parse_args(["send", "--agent", "main-one", "--sandbox", "workspace-write", "--approval-policy", "never"])
            self.assertEqual(runtime.resolve_execution_policy(args, self.root, session)["sandboxPolicy"]["writable_roots"], [str(path)])
        self.command("merge")
        self.assertEqual(runtime.load_session(self.root, "main-one")["executionPolicy"]["sandboxPolicy"]["writable_roots"], [str(self.root)])

    def test_cli_restart_restores_location_and_new_conversation_needs_no_turn(self):
        with mock.patch.object(runtime.native_codex, "inspect_capabilities", return_value={"submit": {}}):
            created = self.command("create", "--codex", "/bin/true", agent="main-new")
        self.assertEqual(list(runtime.iter_run_states(self.root, "main-new")), [])
        result = subprocess.run([os.sys.executable, str(SCRIPT), "worktree", "--project-root", str(self.root),
            "--agent", "main-new", "status"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["workingDirectory"], created["workingDirectory"])

    def test_both_provider_transports_use_worktree_without_replacing_thread(self):
        from native_fixtures import native_fixture
        path = Path(self.command("create")["workingDirectory"])
        with contextlib.redirect_stdout(io.StringIO()):
            bridge, rpc, state = native_fixture(self.root, goal=False)
            bridge.session["workingDirectory"] = str(path)
            bridge.setup("Continue in this worktree")
        resumed = next(params for method, params in rpc.calls if method == "thread/resume")
        turn = next(params for method, params in rpc.calls if method == "turn/start")
        self.assertEqual(resumed["cwd"], str(path))
        self.assertEqual(resumed["threadId"], "thread-exact")
        self.assertEqual(turn["cwd"], str(path))
        session = {**bridge.session, "codex": "codex"}
        session.pop("backend", None)
        command = runtime.build_codex_command(session, state, "thread-exact")
        self.assertEqual(command[command.index("--cd") + 1], str(path))
        self.assertEqual(command[-2], "thread-exact")

    def test_custom_location_keep_changes_and_target_branch_guard(self):
        (self.root / "file.txt").write_text("keep here\n")
        path = Path(self.temp.name) / "custom worktree"
        self.command("create", "--changes", "keep", "--path", str(path))
        self.assertEqual((path / "file.txt").read_text(), "base\n")
        self.assertEqual((self.root / "file.txt").read_text(), "keep here\n")
        self.git("checkout", "-b", "different")
        with self.assertRaisesRegex(runtime.ContractError, "original workspace branch"):
            self.command("merge")

    def test_ignored_local_file_is_not_overwritten_during_merge(self):
        (self.root / ".gitignore").write_text("local.txt\n")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore local file")
        path = Path(self.command("create")["workingDirectory"])
        (path / "local.txt").write_text("incoming\n")
        self.git("add", "-f", "local.txt", root=path)
        self.git("commit", "-m", "add local", root=path)
        (self.root / "local.txt").write_text("preserve me\n")
        with self.assertRaises(runtime.ContractError):
            self.command("merge")
        self.assertEqual((self.root / "local.txt").read_text(), "preserve me\n")
        self.assertEqual(self.command("status")["workingDirectory"], str(path))

    def test_child_inheritance_tracks_parent_return_without_moving_history(self):
        self.command("create")
        parent = runtime.load_session(self.root, "main-one")
        child = {"projectRoot": str(self.root), "role": "work", "sessionId": "child-thread",
                 "executionPolicy": runtime_test_home.policy("workspace-write", self.root)}
        isolated = worktrees.inherit(child, parent)
        self.assertEqual(worktrees.checked_path(isolated), Path(parent["worktree"]["path"]))
        self.assertEqual(isolated["sessionId"], "child-thread")
        self.command("merge")
        restored = worktrees.inherit(isolated, runtime.load_session(self.root, "main-one"))
        self.assertEqual(worktrees.checked_path(restored), self.root)
        self.assertEqual(restored["executionPolicy"]["sandboxPolicy"]["writable_roots"], [str(self.root)])


if __name__ == "__main__":
    unittest.main()
