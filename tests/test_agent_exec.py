from __future__ import annotations

import argparse
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "agent"
    / "scripts"
    / "exec.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("exec", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exec runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentExecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_build_prompt_embeds_each_validated_role_prompt(self) -> None:
        for role in ("main", "work", "verification"):
            with self.subTest(role=role):
                source = self.module.role_path(role).read_text(encoding="utf-8")
                prompt = self.module.build_prompt(
                    agent_id=f"{role}-agent", role=role,
                    request_path=Path("/managed/request.md"),
                    result_path=Path("/managed/result.md"), run_id="run-one",
                )
                self.assertIn(source, prompt)
                self.assertIn("<agent-factory-role-prompt>", prompt)

    def test_role_path_rejects_role_outside_graph(self) -> None:
        with self.assertRaises(self.module.ContractError) as raised:
            self.module.role_path("review")
        self.assertEqual(raised.exception.code, "role_not_found")

    def test_generated_result_path_schema_has_string_type_and_exact_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            schema = json.loads(
                Path(state["responseSchemaPath"]).read_text(encoding="utf-8")
            )

        self.assertEqual(
            schema["properties"]["resultPath"],
            {"type": "string", "const": state["resultPath"]},
        )

    def _new_containment_state(self, root: Path) -> dict:
        return self.module.create_run(
            project_root=root, agent_id="work-agent", actor="main",
            request=b"bounded request", session={"role": "work", "maxAttempts": 2},
        )

    def test_containment_backend_selection_is_capability_negotiated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment_fd = os.open("/dev/null", os.O_RDONLY)

            def launch(_root, _agent, _run, _command, resource):
                os.close(resource[0])
                return 31

            with mock.patch.object(self.module, "systemd_manager_usable", return_value=True), mock.patch.object(
                self.module, "create_systemd_environment_file",
                return_value=(environment_fd, f"/proc/{os.getpid()}/fd/{environment_fd}"),
            ), mock.patch.object(
                self.module, "_launch_systemd_worker", side_effect=launch
            ) as systemd_launch, mock.patch.object(self.module, "_launch_fallback_worker") as fallback:
                self.assertEqual(self.module.spawn_worker(root, "work-agent", "run-one"), 31)
                systemd_launch.assert_called_once()
                fallback.assert_not_called()
            with mock.patch.object(self.module, "systemd_manager_usable", return_value=False), mock.patch.object(
                self.module, "_launch_fallback_worker", return_value=32
            ) as fallback:
                self.assertEqual(self.module.spawn_worker(root, "work-agent", "run-one"), 32)
                fallback.assert_called_once()

    def test_systemd_launch_durably_binds_service_before_ack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            calls = []

            def command(argv):
                calls.append(tuple(argv))
                persisted = self.module.safe_read_json(Path(state["statePath"]))
                self.assertEqual(persisted["containmentLaunchDisposition"], "launching")
                self.assertEqual(persisted["containment"]["kind"], "systemd-user-service")
                if argv[0] == "systemd-run":
                    return subprocess.CompletedProcess(argv, 0, "Running as unit\n", "")
                token = persisted["containment"]["bindingToken"]
                output = (
                    "LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=73\n"
                    f"Description={self.module.SYSTEMD_DESCRIPTION_PREFIX}{token}\n"
                    "InvocationID=0123456789abcdef0123456789abcdef\n"
                    "ControlGroup=/user.slice/agent-factory.service\n"
                )
                return subprocess.CompletedProcess(argv, 0, output, "")

            with mock.patch.object(self.module, "_systemd_command", side_effect=command), mock.patch.object(
                self.module, "systemd_cgroup_populated", return_value=False
            ):
                environment_fd = os.open("/dev/null", os.O_RDONLY)
                pid = self.module._launch_systemd_worker(
                    root,
                    "work-agent",
                    state["runId"],
                    ["python", "worker"],
                    (environment_fd, f"/proc/{os.getpid()}/fd/{environment_fd}"),
                )
            with self.assertRaises(OSError):
                os.fstat(environment_fd)
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            self.assertEqual(pid, 73)
            self.assertEqual(persisted["containmentLaunchDisposition"], "launched")
            self.assertEqual(persisted["containment"]["invocationId"], "0123456789abcdef0123456789abcdef")
            launch = calls[0]
            self.assertIn("--service-type=exec", launch)
            self.assertIn("--collect", launch)
            self.assertIn("--property=KillMode=control-group", launch)
            self.assertTrue(any(value.startswith("--property=EnvironmentFile=/proc/") for value in launch))
            self.assertNotIn("--scope", launch)

    def test_systemd_launch_failure_remains_ambiguously_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            failed = subprocess.CompletedProcess(["systemd-run"], 1, "", "failed")
            environment_fd = os.open("/dev/null", os.O_RDONLY)
            with mock.patch.object(self.module, "_systemd_command", return_value=failed):
                with self.assertRaises(self.module.ContractError) as raised:
                    self.module._launch_systemd_worker(
                        root,
                        "work-agent",
                        state["runId"],
                        ["worker"],
                        (environment_fd, f"/proc/{os.getpid()}/fd/{environment_fd}"),
                    )
            with self.assertRaises(OSError):
                os.fstat(environment_fd)
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            self.assertEqual(raised.exception.code, "containment_launch_failed")
            self.assertEqual(persisted["containmentLaunchDisposition"], "launching")
            self.assertFalse(self.module.durably_never_started(persisted))

    def test_exact_systemd_unit_binding_and_invocation_are_enforced(self) -> None:
        state = {
            "agentId": "work-agent", "runId": "run-one", "containmentAttempt": 1,
            "workerIdentity": None, "containmentLaunchDisposition": "launched",
            "containment": {
                "kind": "systemd-user-service",
                "unitName": self.module.systemd_unit_name("other-agent", "run-one", 1),
                "bindingToken": "a" * 32, "invocationId": None,
                "weakerDescendantContainment": False,
            },
        }
        with self.assertRaises(self.module.ContractError) as raised:
            self.module._validate_state_containment(state)
        self.assertEqual(raised.exception.code, "containment_identity_mismatch")
        malformed = dict(state["containment"], unitName="not-a-bound-unit.service")
        with self.assertRaises(self.module.ContractError):
            self.module.validate_containment(malformed)
        unbound = dict(state, containment=None, containmentAttempt=1, containmentLaunchDisposition="launching")
        with self.assertRaises(self.module.ContractError) as unbound_error:
            self.module.validate_state_containment_fields(unbound)
        self.assertEqual(unbound_error.exception.code, "containment_identity_unbound")

    def test_systemd_query_checks_binding_and_reports_emptiness(self) -> None:
        containment = {
            "kind": "systemd-user-service", "unitName": "agent-factory-" + "a" * 24 + ".service",
            "bindingToken": "b" * 32, "invocationId": "c" * 32,
            "weakerDescendantContainment": False,
        }
        missing = subprocess.CompletedProcess([], 1, "LoadState=not-found\n", "")
        with mock.patch.object(self.module, "_systemd_command", return_value=missing):
            self.assertTrue(self.module.containment_is_empty(containment))
        mismatch = subprocess.CompletedProcess(
            [], 0,
            "LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=9\n"
            "Description=wrong\nInvocationID=" + "c" * 32 +
            "\nControlGroup=/user.slice/wrong.service\n", "",
        )
        with mock.patch.object(self.module, "_systemd_command", return_value=mismatch):
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.containment_is_empty(containment)
        self.assertEqual(raised.exception.code, "containment_identity_mismatch")

    def test_systemd_query_fails_closed_on_manager_failure_and_malformed_output(self) -> None:
        containment = {
            "kind": "systemd-user-service", "unitName": "agent-factory-" + "a" * 24 + ".service",
            "bindingToken": "b" * 32, "invocationId": "c" * 32,
            "weakerDescendantContainment": False,
        }
        failed = subprocess.CompletedProcess([], 1, "", "manager unavailable")
        with mock.patch.object(self.module, "_systemd_command", return_value=failed):
            with self.assertRaises(self.module.ContractError) as failure:
                self.module.containment_is_empty(containment)
        self.assertEqual(failure.exception.code, "containment_query_unknown")
        malformed = subprocess.CompletedProcess([], 0, "LoadState=loaded\nActiveState=failed\n", "")
        with mock.patch.object(self.module, "_systemd_command", return_value=malformed):
            with self.assertRaises(self.module.ContractError) as invalid:
                self.module.containment_is_empty(containment)
        self.assertEqual(invalid.exception.code, "containment_query_invalid")

    def test_systemd_emptiness_uses_cgroup_population_not_active_state(self) -> None:
        containment = {
            "kind": "systemd-user-service", "unitName": "agent-factory-" + "a" * 24 + ".service",
            "bindingToken": "b" * 32, "invocationId": "c" * 32,
            "weakerDescendantContainment": False,
        }
        output = (
            "LoadState=loaded\nActiveState=failed\nSubState=failed\nMainPID=0\n"
            f"Description={self.module.SYSTEMD_DESCRIPTION_PREFIX}{containment['bindingToken']}\n"
            f"InvocationID={containment['invocationId']}\nControlGroup=/user.slice/bound.service\n"
        )
        result = subprocess.CompletedProcess([], 0, output, "")
        with mock.patch.object(self.module, "_systemd_command", return_value=result), mock.patch.object(
            self.module, "systemd_cgroup_populated", return_value=True
        ):
            self.assertFalse(self.module.containment_is_empty(containment))
        with mock.patch.object(self.module, "_systemd_command", return_value=result), mock.patch.object(
            self.module, "systemd_cgroup_populated", return_value=False
        ):
            self.assertTrue(self.module.containment_is_empty(containment))

    def test_systemd_stop_and_force_stop_signal_the_bound_control_group(self) -> None:
        containment = {
            "kind": "systemd-user-service", "unitName": "agent-factory-" + "a" * 24 + ".service",
            "bindingToken": "b" * 32, "invocationId": "c" * 32,
            "weakerDescendantContainment": False,
        }
        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(
            self.module, "query_systemd_containment", return_value={"empty": False}
        ), mock.patch.object(self.module, "_systemd_command", return_value=completed) as command:
            self.module.request_containment_stop(containment)
            self.module.force_containment_stop(containment)
        term = command.call_args_list[0].args[0]
        kill = command.call_args_list[1].args[0]
        self.assertIn("--signal=TERM", term)
        self.assertIn("--signal=KILL", kill)
        self.assertIn("--kill-whom=all", term)
        self.assertIn("--kill-whom=all", kill)

    def test_systemd_environment_transfer_keeps_values_out_of_argv(self) -> None:
        environment = {"PATH": "/runtime/bin:/usr/bin", "AGENT_RUNTIME_TOKEN": "secret-value"}
        descriptor, environment_path = self.module.create_systemd_environment_file(environment)
        try:
            content = os.read(descriptor, 4096).decode("utf-8")
        finally:
            os.close(descriptor)
        self.assertIn('PATH="/runtime/bin:/usr/bin"', content)
        self.assertIn('AGENT_RUNTIME_TOKEN="secret-value"', content)
        self.assertNotIn("secret-value", environment_path)
        self.assertTrue(environment_path.startswith(f"/proc/{os.getpid()}/fd/"))
        self.assertFalse(self.module.systemd_environment_supported({"INVALID-NAME": "value"}))

    def test_environment_acquisition_failure_selects_fallback_before_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            with mock.patch.object(self.module, "systemd_manager_usable", return_value=True), mock.patch.object(
                self.module.os, "memfd_create", side_effect=OSError("memfd blocked")
            ), mock.patch.object(self.module, "_launch_systemd_worker") as systemd_launch, mock.patch.object(
                self.module, "_launch_fallback_worker", return_value=44
            ) as fallback:
                self.assertEqual(self.module.spawn_worker(root, "work-agent", state["runId"]), 44)
            systemd_launch.assert_not_called()
            fallback.assert_called_once()
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            self.assertEqual(persisted["containmentAttempt"], 0)
            self.assertIsNone(persisted["containment"])
            self.assertEqual(persisted["containmentLaunchDisposition"], "not-launched")

    def test_environment_write_failure_closes_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            descriptor = os.open("/dev/null", os.O_RDONLY)
            with mock.patch.object(self.module, "systemd_manager_usable", return_value=True), mock.patch.object(
                self.module.os, "memfd_create", return_value=descriptor
            ), mock.patch.object(self.module.os, "write", side_effect=OSError("write blocked")), mock.patch.object(
                self.module, "_launch_systemd_worker"
            ) as systemd_launch, mock.patch.object(
                self.module, "_launch_fallback_worker", return_value=45
            ) as fallback:
                self.assertEqual(self.module.spawn_worker(root, "work-agent", state["runId"]), 45)
            systemd_launch.assert_not_called()
            fallback.assert_called_once()
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            self.assertIsNone(persisted["containment"])
            self.assertEqual(persisted["containmentLaunchDisposition"], "not-launched")
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_systemd_launch_closes_environment_when_binding_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            descriptor = os.open("/dev/null", os.O_RDONLY)
            failure = self.module.ContractError("state_invalid", "cannot bind")
            with mock.patch.object(self.module, "update_json", side_effect=failure), mock.patch.object(
                self.module, "_systemd_command"
            ) as command:
                with self.assertRaises(self.module.ContractError):
                    self.module._launch_systemd_worker(
                        root,
                        "work-agent",
                        state["runId"],
                        ["worker"],
                        (descriptor, f"/proc/{os.getpid()}/fd/{descriptor}"),
                    )
            command.assert_not_called()
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_systemd_capability_probe_requires_commands_manager_features_cgroup_and_environment(self) -> None:
        help_text = " ".join(self.module.SYSTEMD_REQUIRED_OPTIONS)
        success = [
            subprocess.CompletedProcess([], 0, "manager", ""),
            subprocess.CompletedProcess([], 0, help_text, ""),
        ]
        common = (
            mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/tool"),
            mock.patch.object(self.module, "cgroup_v2_available", return_value=True),
            mock.patch.object(self.module, "systemd_environment_supported", return_value=True),
        )
        with common[0], common[1], common[2], mock.patch.object(
            self.module, "_systemd_command", side_effect=success
        ):
            self.assertTrue(self.module.systemd_manager_usable())
        with mock.patch.object(self.module.shutil, "which", return_value=None), mock.patch.object(
            self.module, "_systemd_command"
        ) as command:
            self.assertFalse(self.module.systemd_manager_usable())
            command.assert_not_called()
        missing_feature = [success[0], subprocess.CompletedProcess([], 0, "--collect --user", "")]
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/tool"), mock.patch.object(
            self.module, "cgroup_v2_available", return_value=True
        ), mock.patch.object(self.module, "systemd_environment_supported", return_value=True), mock.patch.object(
            self.module, "_systemd_command", side_effect=missing_feature
        ):
            self.assertFalse(self.module.systemd_manager_usable())
        unavailable = self.module.ContractError("containment_backend_unavailable", "timeout")
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/tool"), mock.patch.object(
            self.module, "cgroup_v2_available", return_value=True
        ), mock.patch.object(self.module, "systemd_environment_supported", return_value=True), mock.patch.object(
            self.module, "_systemd_command", side_effect=unavailable
        ):
            self.assertFalse(self.module.systemd_manager_usable())

    def test_cancel_is_state_first_and_escalates_backend_wide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update({
                "containmentAttempt": 1,
                "containment": {
                    "kind": "systemd-user-service",
                    "unitName": self.module.systemd_unit_name("work-agent", state["runId"], 1),
                    "bindingToken": "d" * 32, "invocationId": "e" * 32,
                    "weakerDescendantContainment": False,
                },
                "containmentLaunchDisposition": "launched",
            })
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            args = argparse.Namespace(project_root=root, agent="work-agent", run_id=state["runId"])

            def requested(_containment):
                current = self.module.safe_read_json(Path(state["statePath"]))
                self.assertTrue(current["cancelRequested"])
                self.assertEqual(current["status"], "cancelling")

            with mock.patch.object(self.module, "request_containment_stop", side_effect=requested) as request, mock.patch.object(
                self.module, "wait_containment_empty", side_effect=[False, True]
            ), mock.patch.object(self.module, "force_containment_stop") as force, mock.patch.object(self.module, "emit"):
                self.module.command_cancel(args)
            request.assert_called_once()
            force.assert_called_once()

    def test_fallback_launch_preserves_barrier_and_weaker_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            process = mock.Mock(pid=87)
            identity = {"pid": 87, "bootId": "f" * 36, "startTicks": 9}
            with mock.patch.object(
                self.module, "spawn_contained_process", return_value=(process, identity, 4)
            ), mock.patch.object(self.module, "release_contained_process") as release:
                self.module._launch_fallback_worker(root, "work-agent", state["runId"], ["worker"])
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            self.assertEqual(persisted["containment"]["kind"], "process-group")
            self.assertTrue(persisted["containment"]["weakerDescendantContainment"])
            release.assert_called_once_with(process, identity, 4)

    def test_reconcile_queries_bound_containment_before_pid_and_fails_ambiguous_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._new_containment_state(root)
            self.module.atomic_write_json(
                self.module.session_file(root, "work-agent"),
                {"agentId": "work-agent", "role": "work", "sessionId": None,
                 "projectRoot": str(root), "heartbeatTimeout": 1},
            )
            heartbeat = self.module.safe_read_json(Path(state["heartbeatPath"]))
            heartbeat["observedAt"] = "2000-01-01T00:00:00Z"
            self.module.atomic_write_json(Path(state["heartbeatPath"]), heartbeat)
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update({
                "status": "starting", "containmentAttempt": 1,
                "containmentLaunchDisposition": "launching",
                "containment": {
                    "kind": "systemd-user-service",
                    "unitName": self.module.systemd_unit_name("work-agent", state["runId"], 1),
                    "bindingToken": "1" * 32, "invocationId": None,
                    "weakerDescendantContainment": False,
                },
            })
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            args = argparse.Namespace(project_root=root, agent="work-agent")
            with mock.patch.object(self.module, "containment_is_empty", return_value=True) as empty, mock.patch.object(
                self.module, "process_identity_status"
            ) as pid_status, mock.patch.object(self.module, "spawn_worker") as spawn, mock.patch.object(self.module, "emit") as emit:
                self.module.command_reconcile(args)
            empty.assert_called_once()
            pid_status.assert_not_called()
            spawn.assert_not_called()
            final = self.module.safe_read_json(Path(state["statePath"]))
            self.assertEqual(final["error"]["code"], "run_start_unknown")
            self.assertEqual(emit.call_args.args[0]["runs"][0]["action"], "failed-not-replayable")

    def dispatch_args(self, directory: str, dispatch_id: str, message: str = "bounded request") -> argparse.Namespace:
        return argparse.Namespace(
            project_root=Path(directory), agent="work-agent", actor="main", message=message,
            request_file=None, receipt_request_hash="a" * 64, verified_work_run_id=None,
            dispatch_id=dispatch_id, role="work", codex="/bin/true", sandbox=self.module.DEFAULT_SANDBOX,
            model=None, heartbeat_interval=5.0, heartbeat_timeout=20.0,
            start_timeout=60.0, turn_timeout=1800.0, max_attempts=2,
        )

    def test_dispatch_id_deduplicates_and_collisions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "spawn_worker", return_value=123) as spawn, mock.patch.object(self.module, "emit") as emit:
            self.module.submit(self.dispatch_args(directory, "dispatch-one"), True)
            first = emit.call_args.args[0]
            emit.reset_mock()
            self.module.submit(self.dispatch_args(directory, "dispatch-one"), True)
            duplicate = emit.call_args.args[0]
            self.assertEqual(first["runId"], duplicate["runId"])
            self.assertFalse(first["deduplicated"])
            self.assertTrue(duplicate["deduplicated"])
            self.assertEqual(spawn.call_count, 1)
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.submit(self.dispatch_args(directory, "dispatch-one", "different"), True)
            self.assertEqual(raised.exception.code, "dispatch_id_collision")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are required")
    def test_submit_and_send_reject_symlinked_capability_binding_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = root / "binding.json"
            binding.write_text("{}", encoding="utf-8")
            linked = root / "binding-link.json"
            linked.symlink_to(binding)
            for new_agent in (True, False):
                with self.subTest(operation="submit" if new_agent else "send"):
                    args = self.dispatch_args(directory, f"dispatch-symlink-{new_agent}")
                    args.capability_binding_file = linked
                    with self.assertRaises(self.module.ContractError) as raised:
                        self.module.submit(args, new_agent)
                    self.assertEqual(raised.exception.code, "capability_binding_invalid")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are required")
    def test_submit_rejects_symlinked_capability_binding_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual"
            actual.mkdir()
            (actual / "binding.json").write_text("{}", encoding="utf-8")
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(actual, target_is_directory=True)
            args = self.dispatch_args(directory, "dispatch-parent-symlink")
            args.capability_binding_file = linked_parent / "binding.json"
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.submit(args, True)
            self.assertEqual(raised.exception.code, "capability_binding_invalid")

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "FIFO nonblocking open is required")
    def test_capability_binding_fifo_is_rejected_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / "binding.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.safe_read_caller_file(
                    fifo, self.module.MAX_CAPABILITY_BINDING_BYTES
                )
            self.assertEqual(raised.exception.code, "capability_binding_invalid")

    def test_identical_requests_with_distinct_dispatches_create_distinct_runs_and_send_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "spawn_worker", return_value=123) as spawn, mock.patch.object(self.module, "emit") as emit:
            self.module.submit(self.dispatch_args(directory, "dispatch-submit"), True)
            send_one = self.dispatch_args(directory, "dispatch-send-one")
            send_two = self.dispatch_args(directory, "dispatch-send-two")
            outputs = []
            for values in (send_one, send_one, send_two):
                emit.reset_mock()
                self.module.submit(values, False)
                outputs.append(emit.call_args.args[0])
            self.assertEqual(outputs[0]["runId"], outputs[1]["runId"])
            self.assertNotEqual(outputs[0]["runId"], outputs[2]["runId"])
            self.assertTrue(outputs[1]["deduplicated"])
            self.assertEqual(spawn.call_count, 3)

    def test_crash_after_creation_before_ack_is_adopted_by_exact_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "spawn_worker", return_value=123), mock.patch.object(self.module, "emit", side_effect=RuntimeError("lost ack")):
            with self.assertRaises(RuntimeError):
                self.module.submit(self.dispatch_args(directory, "dispatch-crash"), True)
            states = list(self.module.iter_run_states(Path(directory), "work-agent"))
            self.assertEqual(len(states), 1)
            self.assertEqual(states[0]["dispatchId"], "dispatch-crash")

    def test_initial_dispatch_reservation_recovers_session_created_run_missing_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.dispatch_args(directory, "dispatch-initial-reserved")
            original_create_run = self.module.create_run
            calls = 0

            def crash_once(**values):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("crash after session creation")
                return original_create_run(**values)

            with mock.patch.object(self.module, "create_run", side_effect=crash_once), mock.patch.object(self.module, "spawn_worker", return_value=123), mock.patch.object(self.module, "emit") as emit:
                with self.assertRaises(RuntimeError):
                    self.module.submit(args, True)
                self.assertTrue(self.module.session_file(Path(directory), "work-agent").is_file())
                self.assertEqual(list(self.module.iter_run_states(Path(directory), "work-agent")), [])
                with self.assertRaises(self.module.ContractError) as collision:
                    self.module.submit(
                        self.dispatch_args(directory, "dispatch-initial-reserved", "different"),
                        True,
                    )
                self.assertEqual(collision.exception.code, "dispatch_id_collision")
                self.module.submit(args, True)
                recovered = emit.call_args.args[0]
                with self.assertRaises(self.module.ContractError) as established:
                    self.module.submit(
                        self.dispatch_args(directory, "dispatch-another-initial"), True
                    )

            self.assertEqual(recovered["dispatchId"], "dispatch-initial-reserved")
            self.assertFalse(recovered["deduplicated"])
            self.assertEqual(established.exception.code, "agent_exists")

    def test_worker_does_not_retry_failure_after_process_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.dispatch_args(directory, "dispatch-post-launch")
            with mock.patch.object(self.module, "spawn_worker", return_value=123), mock.patch.object(self.module, "emit"):
                self.module.submit(args, True)
            state = next(self.module.iter_run_states(root, "work-agent"))
            heartbeat = mock.Mock()
            worker_args = argparse.Namespace(
                project_root=root, agent="work-agent", run_id=state["runId"]
            )
            failure = self.module.AttemptFailure(
                "start_ack_missing", "process exited without a start event", False, True
            )
            original_update = self.module.update_json
            with mock.patch.object(self.module, "Heartbeat", return_value=heartbeat), mock.patch.object(self.module, "run_codex_attempt", side_effect=failure) as attempt, mock.patch.object(self.module, "update_json", wraps=original_update) as updates:
                outcome = self.module.worker(worker_args)
            final = self.module.safe_read_json(Path(state["statePath"]))

        self.assertEqual(outcome, 1)
        self.assertEqual(attempt.call_count, 1)
        self.assertEqual(final["attempt"], 1)
        self.assertEqual(final["startDisposition"], "launching")
        self.assertEqual(final["error"]["code"], "start_ack_missing")
        self.assertEqual(updates.call_count, 2)

    def test_reconcile_never_replays_ambiguous_or_started_stale_run(self) -> None:
        cases = (
            ("launching", {"startDisposition": "launching"}, None, "run_start_unknown"),
            ("thread-marker", {}, '{"type":"thread.started"}\n', "started_run_not_replayable"),
            ("started-at", {"startedAt": "2026-08-28T00:00:00Z"}, None, "started_run_not_replayable"),
            ("session", {"sessionId": "session-work"}, None, "started_run_not_replayable"),
        )
        for label, updates, events, expected_code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = self.module.create_run(
                    project_root=root, agent_id="work-agent", actor="main",
                    request=b"bounded", session={"role": "work", "maxAttempts": 2},
                )
                self.module.atomic_write_json(
                    self.module.session_file(root, "work-agent"),
                    {"agentId": "work-agent", "role": "work", "sessionId": None,
                     "projectRoot": str(root), "heartbeatTimeout": 1},
                )
                persisted = self.module.safe_read_json(Path(state["statePath"]))
                for field in ("containmentAttempt", "containment", "containmentLaunchDisposition"):
                    persisted.pop(field)
                persisted.update(updates)
                persisted.update(
                    {
                        "workerPid": 999999,
                        "workerIdentity": {"pid": 999999, "bootId": "old", "startTicks": 1},
                        "codexPid": 999998,
                        "codexIdentity": {"pid": 999998, "bootId": "old", "startTicks": 2},
                    }
                )
                self.module.atomic_write_json(Path(state["statePath"]), persisted)
                if events is not None:
                    self.module.atomic_write(Path(state["eventsPath"]), events.encode())
                heartbeat = self.module.safe_read_json(Path(state["heartbeatPath"]))
                heartbeat["observedAt"] = "2000-01-01T00:00:00Z"
                self.module.atomic_write_json(Path(state["heartbeatPath"]), heartbeat)
                args = argparse.Namespace(project_root=root, agent="work-agent")
                with mock.patch.object(self.module, "process_identity_status", return_value="dead"), mock.patch.object(self.module, "spawn_worker") as spawn, mock.patch.object(self.module, "emit") as emit:
                    self.module.command_reconcile(args)
                final = self.module.safe_read_json(Path(state["statePath"]))
                self.assertEqual(emit.call_args.args[0]["runs"][0]["action"], "failed-not-replayable")
                self.assertEqual(final["error"]["code"], expected_code)
                spawn.assert_not_called()

    def test_reconcile_resubmits_only_explicit_not_started_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root, agent_id="work-agent", actor="main",
                request=b"bounded", session={"role": "work", "maxAttempts": 2},
            )
            self.module.atomic_write_json(
                self.module.session_file(root, "work-agent"),
                {"agentId": "work-agent", "role": "work", "sessionId": None,
                 "projectRoot": str(root), "heartbeatTimeout": 1},
            )
            heartbeat = self.module.safe_read_json(Path(state["heartbeatPath"]))
            heartbeat["observedAt"] = "2000-01-01T00:00:00Z"
            self.module.atomic_write_json(Path(state["heartbeatPath"]), heartbeat)
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            for field in ("containmentAttempt", "containment", "containmentLaunchDisposition"):
                persisted.pop(field)
            persisted.update(
                {
                    "workerPid": 77,
                    "workerIdentity": {"pid": 77, "bootId": "old", "startTicks": 3},
                }
            )
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            args = argparse.Namespace(project_root=root, agent="work-agent")
            with mock.patch.object(self.module, "process_identity_status", return_value="mismatch"), mock.patch.object(self.module, "spawn_worker", return_value=42) as spawn, mock.patch.object(self.module, "emit") as emit:
                self.module.command_reconcile(args)
        spawn.assert_called_once_with(root, "work-agent", state["runId"])
        self.assertEqual(emit.call_args.args[0]["runs"][0]["action"], "resubmitted")

    def test_linux_process_identity_matches_exact_start_and_detects_pid_reuse(self) -> None:
        expected = {"pid": 41, "bootId": "boot", "startTicks": 99}
        with mock.patch.object(self.module, "linux_process_identity", return_value=expected):
            self.assertEqual(self.module.process_identity_status(expected), "match")
            self.assertEqual(
                self.module.process_identity_status(
                    {"pid": 41, "bootId": "boot", "startTicks": 98}
                ),
                "mismatch",
            )

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_attempt_group_termination_reaches_nested_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "child.pid"
            script = (
                "import pathlib,subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(child_path)],
                start_new_session=True,
            )
            deadline = time.monotonic() + 5
            while not child_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            child_pid = int(child_path.read_text())
            identity = self.module.linux_process_identity(process.pid)
            self.module.terminate_attempt_group(process, identity)
            deadline = time.monotonic() + 2
            while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(Path(f"/proc/{child_pid}").exists())

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_attempt_group_termination_cleans_child_after_leader_exits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "child.pid"
            release_path = Path(directory) / "release"
            script = (
                "import os,pathlib,subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); "
                "release=pathlib.Path(sys.argv[2]); "
                "exec('while not release.exists(): time.sleep(0.01)'); os._exit(0)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(child_path), str(release_path)],
                start_new_session=True,
            )
            identity = self.module.linux_process_identity(process.pid)
            deadline = time.monotonic() + 5
            while not child_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            child_pid = int(child_path.read_text())
            release_path.touch()
            process.wait(timeout=5)
            self.assertTrue(Path(f"/proc/{child_pid}").exists())
            self.module.terminate_attempt_group(process, identity)
            deadline = time.monotonic() + 2
            while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(Path(f"/proc/{child_pid}").exists())

    def test_post_exit_failure_invokes_group_cleanup_before_returning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            fake_process = mock.Mock()
            fake_process.pid = 101
            fake_process.stdin = io.StringIO()
            fake_process.stdout = io.StringIO("")
            fake_process.stderr = io.StringIO("")
            fake_process.wait.return_value = 1
            session = {
                "codex": "codex",
                "projectRoot": str(root),
                "sandbox": "workspace-write",
                "sessionId": None,
                "startTimeout": 5,
                "turnTimeout": 5,
            }
            identity = {"pid": 101, "bootId": "boot", "startTicks": 7}
            with mock.patch.object(self.module, "spawn_contained_process", return_value=(fake_process, identity, 55)), mock.patch.object(self.module, "release_contained_process"), mock.patch.object(self.module, "terminate_attempt_group") as terminate:
                with self.assertRaises(self.module.AttemptFailure) as raised:
                    self.module.run_codex_attempt(
                        project_root=root,
                        session=session,
                        state=state,
                        attempt=1,
                        heartbeat=mock.Mock(),
                        cancel_event=self.module.threading.Event(),
                        expected_agent_id="work-agent",
                        expected_run_id=state["runId"],
                    )
            self.assertEqual(raised.exception.code, "codex_failed")
            terminate.assert_called_once_with(fake_process, identity)

    def test_codex_pre_release_failure_aborts_barrier_without_pid_signal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            fake_process = mock.Mock()
            fake_process.pid = 202
            fake_process.wait.return_value = 125
            release_read, release_write = os.pipe()
            failure = self.module.ContractError(
                "process_identity_unavailable", "identity unavailable"
            )
            identity = {"pid": 202, "bootId": "boot", "startTicks": 8}
            session = {
                "codex": "codex",
                "projectRoot": str(root),
                "sandbox": "workspace-write",
                "sessionId": None,
                "startTimeout": 5,
                "turnTimeout": 5,
            }
            heartbeat = mock.Mock()
            heartbeat.update.side_effect = failure
            with mock.patch.object(self.module, "spawn_contained_process", return_value=(fake_process, identity, release_write)):
                with self.assertRaises(self.module.AttemptFailure) as raised:
                    self.module.run_codex_attempt(
                        project_root=root,
                        session=session,
                        state=state,
                        attempt=1,
                        heartbeat=heartbeat,
                        cancel_event=self.module.threading.Event(),
                        expected_agent_id="work-agent",
                        expected_run_id=state["runId"],
                    )
            self.assertEqual(raised.exception.code, "process_identity_unavailable")
            self.assertEqual(os.read(release_read, 1), b"")
            os.close(release_read)
            fake_process.kill.assert_not_called()
            fake_process.terminate.assert_not_called()

    def test_worker_pre_release_failure_aborts_barrier_without_pid_signal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            fake_process = mock.Mock()
            fake_process.pid = 303
            fake_process.wait.return_value = 125
            release_read, release_write = os.pipe()
            failure = self.module.ContractError(
                "process_identity_unavailable", "identity unavailable"
            )
            identity = {"pid": 303, "bootId": "boot", "startTicks": 9}
            with mock.patch.object(self.module, "systemd_manager_usable", return_value=False), mock.patch.object(self.module, "spawn_contained_process", return_value=(fake_process, identity, release_write)), mock.patch.object(self.module, "update_json", side_effect=failure):
                with self.assertRaises(self.module.ContractError) as raised:
                    self.module.spawn_worker(root, "work-agent", state["runId"])
            self.assertEqual(raised.exception.code, "process_identity_unavailable")
            self.assertEqual(os.read(release_read, 1), b"")
            os.close(release_read)
            fake_process.kill.assert_not_called()
            fake_process.terminate.assert_not_called()

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_readiness_timeout_terminates_only_verified_bootstrap_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "timeout-child.pid"
            unrelated = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
            )
            real_popen = subprocess.Popen
            real_killpg = os.killpg
            launched: dict[str, subprocess.Popen] = {}

            def nonready_bootstrap(_command, **options):
                script = (
                    "import pathlib,subprocess,sys,time; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
                )
                process = real_popen(
                    [sys.executable, "-c", script, str(child_path)],
                    cwd=options.get("cwd"),
                    pass_fds=options["pass_fds"],
                    start_new_session=True,
                    close_fds=True,
                )
                launched["process"] = process
                return process

            try:
                with mock.patch.object(self.module, "CONTAINMENT_START_TIMEOUT", 0.5), mock.patch.object(self.module, "PROCESS_TERM_TIMEOUT", 0.05), mock.patch.object(self.module.subprocess, "Popen", side_effect=nonready_bootstrap), mock.patch.object(self.module.os, "killpg", wraps=real_killpg) as killpg:
                    with self.assertRaises(self.module.ContractError) as raised:
                        self.module.spawn_contained_process(["ignored"])
                self.assertEqual(raised.exception.code, "containment_start_failed")
                leader_pid = launched["process"].pid
                signalled_groups = {call.args[0] for call in killpg.call_args_list}
                self.assertEqual(signalled_groups, {leader_pid})
                deadline = time.monotonic() + 2
                while Path(f"/proc/{leader_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{leader_pid}").exists())
                self.assertTrue(child_path.exists())
                child_pid = int(child_path.read_text())
                deadline = time.monotonic() + 2
                while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{child_pid}").exists())
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_pre_release_abort_terminates_only_verified_bootstrap_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "abort-child.pid"
            unrelated = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
            )
            real_popen = subprocess.Popen
            real_killpg = os.killpg
            launched: dict[str, subprocess.Popen] = {}

            def nonexiting_bootstrap(_command, **options):
                ready_fd = options["pass_fds"][0]
                script = (
                    "import os,pathlib,subprocess,sys,time; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); "
                    "os.write(int(sys.argv[2]),b'R'); time.sleep(60)"
                )
                process = real_popen(
                    [sys.executable, "-c", script, str(child_path), str(ready_fd)],
                    cwd=options.get("cwd"),
                    pass_fds=options["pass_fds"],
                    start_new_session=True,
                    close_fds=True,
                )
                launched["process"] = process
                return process

            try:
                with mock.patch.object(self.module, "PROCESS_TERM_TIMEOUT", 0.05), mock.patch.object(self.module.subprocess, "Popen", side_effect=nonexiting_bootstrap), mock.patch.object(self.module.os, "killpg", wraps=real_killpg) as killpg:
                    process, identity, release_fd = self.module.spawn_contained_process(
                        ["ignored"]
                    )
                    self.module.abort_contained_process(process, identity, release_fd)
                leader_pid = launched["process"].pid
                signalled_groups = {call.args[0] for call in killpg.call_args_list}
                self.assertEqual(signalled_groups, {leader_pid})
                deadline = time.monotonic() + 2
                while Path(f"/proc/{leader_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{leader_pid}").exists())
                self.assertTrue(child_path.exists())
                child_pid = int(child_path.read_text())
                deadline = time.monotonic() + 2
                while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{child_pid}").exists())
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_aggregate_event_and_stderr_caps_never_grow_past_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "events.jsonl"
            with mock.patch.object(self.module, "MAX_EVENTS_BYTES", 8):
                self.assertTrue(self.module.append_event(event_path, "1234"))
                self.assertFalse(self.module.append_event(event_path, "56789"))
            self.assertEqual(event_path.stat().st_size, 4)

            stderr_path = Path(directory) / "stderr.log"
            output = self.module.queue.Queue()
            with mock.patch.object(self.module, "MAX_STDERR_BYTES", 4):
                self.module.stream_stderr(io.StringIO("12345"), stderr_path, output)
            self.assertEqual(output.get_nowait()[0], "stderr_overflow")
            self.assertEqual(stderr_path.read_bytes(), b"")

    def test_terminal_transition_atomically_clears_active_codex_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            identity = {"pid": 17, "bootId": "boot", "startTicks": 5}
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update(
                {"codexPid": 17, "codexIdentity": identity, "lastCodexIdentity": identity}
            )
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            self.module.mark_terminal(Path(state["statePath"]), "failed")
            final = self.module.safe_read_json(Path(state["statePath"]))
            self.assertIsNone(final["codexPid"])
            self.assertIsNone(final["codexIdentity"])
            self.assertEqual(final["lastCodexIdentity"], identity)

    def test_cancel_refuses_reused_pid_without_signalling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update(
                {"workerIdentity": {"pid": 22, "bootId": "old", "startTicks": 1}}
            )
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            args = argparse.Namespace(
                project_root=root, agent="work-agent", run_id=state["runId"]
            )
            with mock.patch.object(self.module, "process_identity_status", return_value="mismatch"), mock.patch.object(self.module.os, "kill") as kill:
                with self.assertRaises(self.module.ContractError) as raised:
                    self.module.command_cancel(args)
            self.assertEqual(raised.exception.code, "process_identity_mismatch")
            kill.assert_not_called()

    def test_new_command_keeps_configured_sandbox_without_bypass(self) -> None:
        command = self.module.build_codex_command(
            {
                "codex": "codex",
                "projectRoot": "/tmp/project",
                "sandbox": "danger-full-access",
            },
            {"responseSchemaPath": "/tmp/schema.json"},
            None,
        )

        self.assertIn("--sandbox", command)
        self.assertIn("danger-full-access", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_submit_defaults_new_session_sandbox_and_preserves_explicit_overrides(self) -> None:
        base = ["submit", "--agent", "work-agent", "--role", "work"]

        self.assertEqual(
            self.module.parse_args(base).sandbox,
            "danger-full-access",
        )
        for sandbox in self.module.SANDBOXES:
            with self.subTest(sandbox=sandbox):
                self.assertEqual(
                    self.module.parse_args([*base, "--sandbox", sandbox]).sandbox,
                    sandbox,
                )

    def test_resume_reasserts_project_root_and_stored_sandbox(self) -> None:
        for sandbox in ("danger-full-access", "workspace-write", "read-only"):
            with self.subTest(sandbox=sandbox):
                command = self.module.build_codex_command(
                    {
                        "codex": "codex",
                        "projectRoot": "/tmp/project",
                        "sandbox": sandbox,
                    },
                    {
                        "responseSchemaPath": "/tmp/schema.json",
                    },
                    "session-1",
                )

                self.assertEqual(
                    command[:7],
                    [
                        "codex",
                        "exec",
                        "--cd",
                        "/tmp/project",
                        "--sandbox",
                        sandbox,
                        "resume",
                    ],
                )
                self.assertEqual(
                    command[7:],
                    [
                        "--json",
                        "--output-schema",
                        "/tmp/schema.json",
                        "session-1",
                        "-",
                    ],
                )
                self.assertNotIn(
                    "--dangerously-bypass-approvals-and-sandbox", command
                )

    def test_sandbox_failure_classification_requires_observed_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stderr_path = Path(directory) / "stderr.log"
            stderr_path.write_text(
                "apply_patch verification failed: fs sandbox helper failed with status "
                "exit status: 1: bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
                encoding="utf-8",
            )

            failure = self.module.missing_result_failure(stderr_path)
            self.assertEqual(failure.code, "sandbox_unavailable")

            stderr_path.write_text(
                "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
                encoding="utf-8",
            )
            failure = self.module.missing_result_failure(stderr_path)
            self.assertEqual(failure.code, "result_file_missing")

    def test_work_receipt_requires_exact_binding_and_no_test_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "work-receipt",
                "runId": state["runId"],
                "requestHash": state["requestHash"],
                "outcome": "implemented",
                "changedPaths": ["skills/agent/SKILL.md"],
                "addressedFindingIds": [],
                "tests": {"run": False, "reason": "work-agent-prohibited"},
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")

            self.assertEqual(
                self.module.validate_receipt(
                    Path(directory), state, agent_id="work-agent", run_id=state["runId"]
                ),
                receipt,
            )
            receipt["tests"]["run"] = True
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_tests_invalid")

    def test_capability_binding_is_copied_and_receipt_outcome_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = {
                "schemaVersion": "0.1.0",
                "bindings": [{
                    "capabilityId": "playwright.browser.execute",
                    "authority": {"kind": "project-cli", "reference": "package-lock.json#playwright"},
                    "invocationRoute": "node_modules/.bin/playwright",
                    "exactTarget": "https://example.invalid/health",
                    "allowedEffects": ["navigate"],
                    "allowedScopes": ["network:https://example.invalid"],
                    "approvalReference": "human-request-1",
                }],
            }
            canonical = (json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n").encode()
            state = self.module.create_run(
                project_root=root, agent_id="work-agent", actor="main",
                request=b"bounded request", session={"role": "work", "maxAttempts": 1},
                capability_bindings=canonical,
            )
            outcome = {
                "requestHash": state["requestHash"], "runId": state["runId"],
                "capabilityId": "playwright.browser.execute",
                "authority": {"kind": "project-cli", "reference": "package-lock.json#playwright"},
                "exactTarget": "https://example.invalid/health", "outcome": "succeeded",
            }
            receipt = {
                "schemaVersion": "0.1.0", "kind": "work-receipt", "runId": state["runId"],
                "requestHash": state["requestHash"], "outcome": "implemented",
                "changedPaths": [], "addressedFindingIds": [],
                "tests": {"run": False, "reason": "work-agent-prohibited"},
                "capabilityOutcomes": [outcome],
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(
                self.module.validate_receipt(root, state, agent_id="work-agent", run_id=state["runId"]),
                receipt,
            )
            receipt["capabilityOutcomes"][0]["exactTarget"] = "https://other.invalid"
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(root, state, agent_id="work-agent", run_id=state["runId"])
            self.assertEqual(raised.exception.code, "receipt_binding_invalid")

    def test_verification_receipt_enforces_unique_ids_and_decision_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="verification-agent",
                actor="main",
                request=b"verification request",
                session={"role": "verification", "maxAttempts": 1},
                receipt_request_hash="a" * 64,
                verified_work_run_id="run-work-1",
            )
            finding = {
                "id": "REV-001",
                "path": "skills/agent/scripts/exec.py",
                "location": "validate_receipt",
                "problem": "binding is not checked",
                "evidence": "the expected value is available in state",
                "correction": "compare the exact values",
            }
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "verification-receipt",
                "runId": state["runId"],
                "verifiedWorkRunId": "run-work-1",
                "verifiedRequestHash": "a" * 64,
                "decision": "fail",
                "findings": [finding],
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                ),
                receipt,
            )

            receipt["verifiedWorkRunId"] = "run-work-other"
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as binding_error:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                )
            self.assertEqual(binding_error.exception.code, "receipt_binding_invalid")
            receipt["verifiedWorkRunId"] = "run-work-1"

            receipt["decision"] = "pass"
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                )
            self.assertEqual(raised.exception.code, "receipt_decision_invalid")

            receipt["decision"] = "fail"
            receipt["findings"] = [finding, finding]
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                )
            self.assertEqual(raised.exception.code, "receipt_invalid")

    def test_receipt_rejects_adjacent_noncanonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            adjacent = Path(state["resultPath"]).parent.parent / "adjacent-receipt.json"
            adjacent.write_text("{}\n", encoding="utf-8")
            state["receiptPath"] = str(adjacent)

            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    root, state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_path_invalid")

    def test_receipt_rejects_symlinked_run_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            run_path = Path(state["statePath"]).parent
            relocated = run_path.parent / f"{run_path.name}-relocated"
            run_path.rename(relocated)
            run_path.symlink_to(relocated, target_is_directory=True)

            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    root, state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_path_invalid")


if __name__ == "__main__":
    unittest.main()
