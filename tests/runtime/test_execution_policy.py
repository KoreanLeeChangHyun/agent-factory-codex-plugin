"""Policy inheritance and CLI/native equivalence; run by Verification."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import home_fixtures
import execution_policy as policy


def snapshot(mode="danger-full-access", **sandbox):
    return policy.normalize({"schemaVersion": 1, "sandboxPolicy": {"type": mode, **sandbox}, "approvalPolicy": "never"})


def args(*values):
    parser = argparse.ArgumentParser()
    policy.add_policy_arguments(parser)
    return parser.parse_args(values)


class ExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        patch = mock.patch.dict(os.environ, {}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_default_flags_do_not_silently_select_permissions(self):
        parsed = args()
        self.assertIsNone(parsed.sandbox)
        self.assertIsNone(parsed.approval_policy)
        self.assertIsNone(parsed.network_access)
        with mock.patch.object(policy, "_configured_policy", side_effect=policy.PolicyError("policy_missing", "missing")):
            with self.assertRaisesRegex(policy.PolicyError, "policy_missing"):
                policy.resolve(parsed, self.root)

    def test_parent_snapshot_inherits_full_access_without_explicit_sandbox(self):
        expected = snapshot()
        os.environ[policy.SNAPSHOT_ENV] = json.dumps(expected)
        self.assertEqual(policy.resolve(args(), self.root), expected)
        with self.assertRaisesRegex(policy.PolicyError, "policy_parent_mismatch"):
            policy.resolve(args("--sandbox", "read-only"), self.root)

    def test_explicit_file_cannot_override_parent(self):
        path = self.root / "policy.json"
        path.write_text(json.dumps(snapshot("read-only")))
        self.assertEqual(policy.resolve(args("--execution-policy-file", str(path)), self.root), snapshot("read-only"))
        os.environ[policy.SNAPSHOT_ENV] = json.dumps(snapshot())
        with self.assertRaisesRegex(policy.PolicyError, "policy_parent_mismatch"):
            policy.resolve(args("--execution-policy-file", str(path)), self.root)

    def test_workspace_roots_network_and_tmp_exclusions_survive(self):
        value = snapshot("workspace-write", writable_roots=[str(self.root)], network_access=True,
                         exclude_tmpdir_env_var=True, exclude_slash_tmp=True)
        os.environ[policy.SNAPSHOT_ENV] = json.dumps(value)
        self.assertEqual(policy.resolve(args("--network-access", "--writable-root", str(self.root)), self.root), value)
        with self.assertRaisesRegex(policy.PolicyError, "policy_parent_mismatch"):
            policy.resolve(args("--no-network-access"), self.root)
        with self.assertRaisesRegex(policy.PolicyError, "policy_parent_mismatch"):
            policy.resolve(args("--writable-root", str(self.root / "other")), self.root)
        run = self.root / "run"
        config = policy.config(value, run)
        self.assertEqual(config["sandbox_workspace_write.writable_roots"], [str(self.root), str(run)])
        for key in ("network_access", "exclude_tmpdir_env_var", "exclude_slash_tmp"):
            self.assertTrue(config["sandbox_workspace_write." + key])

    def test_unsupported_or_ambiguous_policy_is_not_downgraded(self):
        for change in ({"schemaVersion": True}, {"approvalPolicy": {"reject": {}}}, {"extra": True},
                       {"sandboxPolicy": {"type": "external-sandbox"}},
                       {"sandboxPolicy": {"type": "read-only", "writable_roots": [str(self.root)]}},
                       {"sandboxPolicy": {"type": "danger-full-access", "network_access": False}}):
            with self.subTest(change=change), self.assertRaises(policy.PolicyError):
                policy.normalize({**snapshot(), **change})
        os.environ[policy.SNAPSHOT_ENV] = '{"schemaVersion":1,"schemaVersion":2}'
        with self.assertRaises(policy.PolicyError):
            policy.resolve(args(), self.root)

    def test_latest_rollout_context_and_missing_parent_fail_closed(self):
        thread = "12345678-1234-1234-1234-123456789abc"
        os.environ.update(CODEX_HOME=str(self.root), CODEX_THREAD_ID=thread)
        with mock.patch.object(policy, "_configured_policy") as configured:
            with self.assertRaisesRegex(policy.PolicyError, "policy_unavailable"):
                policy.resolve(args(), self.root)
            configured.assert_not_called()
        sessions = self.root / "sessions" / "2026"
        sessions.mkdir(parents=True)
        rollout = sessions / f"rollout-2026-09-09-{thread}.jsonl"
        events = [
            {"type": "turn_context", "payload": {"sandbox_policy": {"type": "read-only"}, "approval_policy": "never"}},
            {"type": "turn_context", "payload": {"sandbox_policy": {"type": "workspace-write", "writable_roots": [], "network_access": True}, "approval_policy": "on-request", "cwd": str(self.root)}},
            {"type": "event_msg", "payload": {"message": "after context"}},
        ]
        rollout.write_text("\n".join(json.dumps(event) for event in events) + '\n{"partial":')
        result = policy.resolve(args(), self.root)
        self.assertEqual(result["approvalPolicy"], "on-request")
        self.assertEqual(result["sandboxPolicy"]["writable_roots"], [str(self.root)])
        self.assertTrue(result["sandboxPolicy"]["network_access"])

    def test_new_explicit_root_and_legacy_session_are_distinct(self):
        value = policy.resolve(args("--sandbox", "workspace-write", "--approval-policy", "on-request"), self.root)
        self.assertEqual(value["approvalPolicy"], "on-request")
        with self.assertRaisesRegex(policy.PolicyError, "policy_missing"):
            policy.session_policy({"sandbox": "workspace-write", "projectRoot": str(self.root)})
        with self.assertRaises(policy.PolicyError):
            policy.session_policy({"executionPolicy": {}, "sandbox": "read-only"})

    def test_stored_policy_conflict_and_malformed_parent_never_fall_back(self):
        self.assertEqual(policy.resolve(args(), self.root, fallback_policy=snapshot()), snapshot())
        os.environ[policy.SNAPSHOT_ENV] = json.dumps(snapshot("read-only"))
        with self.assertRaisesRegex(policy.PolicyError, "policy_parent_mismatch"):
            policy.resolve(args(), self.root, fallback_policy=snapshot())
        os.environ[policy.SNAPSHOT_ENV] = "invalid"
        with self.assertRaises(policy.PolicyError):
            policy.resolve(args(), self.root, fallback_policy=snapshot())

    def test_readonly_config_grants_only_exact_run_and_keeps_snapshot(self):
        value = snapshot("read-only", network_access=True)
        original = copy.deepcopy(value)
        directory = self.root / "run"
        config = policy.config(value, directory)
        profile = config["permissions." + config["default_permissions"]]
        self.assertEqual(profile["filesystem"], {"/": "read", str(directory): "write"})
        self.assertEqual(profile["network"], {"enabled": True})
        self.assertEqual(config["approval_policy"], "never")
        self.assertEqual(json.loads(config["shell_environment_policy.set." + policy.SNAPSHOT_ENV]), value)
        self.assertEqual(config["shell_environment_policy.set." + policy.PARENT_STATE_ENV], str(directory / "state.json"))
        self.assertEqual(value, original)
        expected = []
        for key, setting in config.items():
            expected.extend(["-c", key + "=" + policy.permissions.toml(setting)])
        self.assertEqual(policy.arguments(value, directory), expected)

    def test_full_access_selects_its_profile_over_inherited_named_permissions(self):
        config = policy.config(snapshot(), self.root / "run")
        self.assertEqual(config["sandbox_mode"], "danger-full-access")
        self.assertEqual(config["default_permissions"], ":danger-full-access")
        self.assertFalse(any(key.startswith("sandbox_workspace_write") for key in config))

    def test_parent_state_requires_bound_state_and_session(self):
        os.environ[policy.SNAPSHOT_ENV] = json.dumps(snapshot())
        os.environ[policy.PARENT_STATE_ENV] = str(self.root / "state.json")
        (self.root / "state.json").write_text(json.dumps({"statePath": str(self.root / "wrong.json")}))
        with self.assertRaisesRegex(policy.PolicyError, "policy_parent_mismatch"):
            policy.resolve(args(), self.root)

    def test_policy_fifo_and_symlink_are_rejected_without_opening_a_stream(self):
        fifo = self.root / "policy-fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(policy.PolicyError, "regular file"):
            policy._read(fifo)
        target = self.root / "target.json"
        target.write_text(json.dumps(snapshot()))
        link = self.root / "link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(policy.PolicyError, "symlinks"):
            policy._read(link)

    def test_managed_parent_snapshot_checks_registered_run_and_session_identity(self):
        import paths
        home = self.root / "runtime-home"
        project = self.root / "project"
        project.mkdir()
        binding = paths.resolve(project, home=home, create=True)
        agent = Path(binding["agentsRoot"]) / "parent"
        run = agent / "runs" / "run-one"
        run.mkdir(parents=True)
        state_file = run / "state.json"
        state = {"runtimeBinding": binding, "agentId": "parent", "runId": "run-one",
                 "statePath": str(state_file), "executionPolicy": snapshot()}
        state_file.write_text(json.dumps(state))
        session = {"agentId": "parent", "projectRoot": str(project), "executionPolicy": snapshot()}
        (agent / "session.json").write_text(json.dumps(session))
        os.environ.update({policy.SNAPSHOT_ENV: json.dumps(snapshot()), policy.PARENT_STATE_ENV: str(state_file)})
        self.assertEqual(policy.resolve(args(), project), snapshot())
        state["runId"] = "run-other"
        state_file.write_text(json.dumps(state))
        with self.assertRaisesRegex(policy.PolicyError, "registered run"):
            policy.resolve(args(), project)

    def test_standalone_queries_effective_config_without_starting_a_thread(self):
        from native_codex import Rpc
        process = mock.Mock()
        process.poll.return_value = 0
        config = {"sandbox_mode": "workspace-write", "approval_policy": "on-request",
                  "sandbox_workspace_write": {"network_access": True, "exclude_slash_tmp": True}}
        with mock.patch.object(policy.subprocess, "Popen", return_value=process), \
                mock.patch.object(Rpc, "__init__", return_value=None), \
                mock.patch.object(Rpc, "write"), \
                mock.patch.object(Rpc, "call", side_effect=[{}, {"config": config}]) as call:
            result = policy.resolve(args(), self.root)
        self.assertEqual([entry.args[0] for entry in call.call_args_list], ["initialize", "config/read"])
        self.assertEqual(result["approvalPolicy"], "on-request")
        self.assertTrue(result["sandboxPolicy"]["network_access"])
        self.assertTrue(result["sandboxPolicy"]["exclude_slash_tmp"])

    def test_missing_config_uses_native_ephemeral_defaults_without_a_model_turn(self):
        from native_codex import Rpc
        process = mock.Mock()
        process.poll.return_value = 0
        native = {"cwd": str(self.root), "sandbox": {"type": "workspaceWrite", "networkAccess": False},
                  "approvalPolicy": "on-request", "activePermissionProfile": {"id": ":workspace"}}
        with mock.patch.object(policy.subprocess, "Popen", return_value=process), \
                mock.patch.object(Rpc, "__init__", return_value=None), mock.patch.object(Rpc, "write"), \
                mock.patch.object(Rpc, "call", side_effect=[{}, {"config": {}}, native]) as call:
            result = policy.resolve(args(), self.root)
        self.assertEqual([entry.args[0] for entry in call.call_args_list], ["initialize", "config/read", "thread/start"])
        self.assertTrue(call.call_args.args[1]["ephemeral"])
        self.assertEqual(result["approvalPolicy"], "on-request")
        self.assertEqual(result["sandboxPolicy"]["writable_roots"], [str(self.root)])

    def test_native_custom_profile_or_wrong_builtin_cannot_be_flattened(self):
        for active in ({"id": "custom"}, {"id": ":read-only"}, {"id": ":workspace", "extends": "custom"}):
            rpc = mock.Mock()
            rpc.call.return_value = {"cwd": str(self.root), "sandbox": {"type": "workspaceWrite"},
                                     "approvalPolicy": "never", "activePermissionProfile": active}
            with self.subTest(active=active), self.assertRaisesRegex(policy.PolicyError, "policy_unsupported"):
                policy._native_selected_policy(rpc, str(self.root), None, None)

    def test_standalone_network_and_roots_flags_apply_to_native_defaults(self):
        extra = self.root / "extra"
        base = snapshot("workspace-write", writable_roots=[str(self.root)])
        with mock.patch.object(policy, "_configured_policy", return_value=base):
            result = policy.resolve(args("--network-access", "--writable-root", str(extra)), self.root)
        self.assertTrue(result["sandboxPolicy"]["network_access"])
        self.assertEqual(result["sandboxPolicy"]["writable_roots"], [str(self.root), str(extra)])

    def test_completed_malformed_rollout_line_cannot_reuse_older_permissions(self):
        thread = "12345678-1234-1234-1234-123456789abc"
        os.environ.update(CODEX_HOME=str(self.root), CODEX_THREAD_ID=thread)
        sessions = self.root / "sessions"
        sessions.mkdir()
        rollout = sessions / f"rollout-2026-09-09-{thread}.jsonl"
        older = json.dumps({"type": "turn_context", "payload": {
            "sandbox_policy": {"type": "danger-full-access"}, "approval_policy": "never"}})
        for ending in ("\n", "\n\n", "\n  "):
            rollout.write_text(older + '\n{"type":"turn_context","payload":' + ending)
            with self.subTest(ending=ending), mock.patch.object(policy, "_configured_policy") as fallback:
                with self.assertRaisesRegex(policy.PolicyError, "policy_invalid"):
                    policy.resolve(args(), self.root)
                fallback.assert_not_called()

    def test_workspace_command_policy_preserves_all_roots_network_and_tmp_settings(self):
        value = snapshot("workspace-write", writable_roots=[str(self.root)], network_access=True,
                         exclude_tmpdir_env_var=True, exclude_slash_tmp=True)
        run = self.root / "run"
        self.assertEqual(policy.command_params(value, run), {"sandboxPolicy": {
            "type": "workspaceWrite", "writableRoots": [str(self.root), str(run)],
            "networkAccess": True, "excludeTmpdirEnvVar": True, "excludeSlashTmp": True}})
        self.assertNotIn("permissionProfile", policy.command_params(value, run))

    def _parent_rollout_profile(self, profile, sandbox, **extra):
        thread = "12345678-1234-1234-1234-123456789abc"
        os.environ.update(CODEX_HOME=str(self.root), CODEX_THREAD_ID=thread)
        sessions = self.root / "sessions"
        sessions.mkdir(exist_ok=True)
        rollout = sessions / f"rollout-2026-09-09-{thread}.jsonl"
        context = {"sandbox_policy": {"type": sandbox}, "approval_policy": "never",
                   "permission_profile": profile, "permissions": None,
                   "file_system_sandbox_policy": None, **extra}
        rollout.write_text(json.dumps({"type": "turn_context", "payload": context}) + "\n")

    def test_stock_disabled_parent_profile_preserves_full_access(self):
        self._parent_rollout_profile({"type": "disabled"}, "danger-full-access")
        with mock.patch.object(policy, "_configured_policy") as fallback:
            self.assertEqual(policy.resolve(args(), self.root), snapshot())
        fallback.assert_not_called()

    def test_disabled_parent_profile_cannot_override_restricted_sandbox(self):
        self._parent_rollout_profile({"type": "disabled"}, "read-only")
        with self.assertRaisesRegex(policy.PolicyError, "policy_unsupported"):
            policy.resolve(args(), self.root)

    def test_unknown_or_richer_parent_profile_remains_unsupported(self):
        for profile, extra in (({"type": "custom"}, {}),
                               ({"type": "disabled", "filesystem": {}}, {}),
                               ({"type": "disabled"}, {"permissions": {}}),
                               ({"type": "disabled"}, {"file_system_sandbox_policy": {}})):
            self._parent_rollout_profile(profile, "danger-full-access", **extra)
            with self.subTest(profile=profile, extra=extra), self.assertRaisesRegex(policy.PolicyError, "policy_unsupported"):
                policy.resolve(args(), self.root)
