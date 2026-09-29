"""Detached worker launch under systemd containment or the portable fallback."""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Sequence


def _launch_systemd_worker(
    runtime,
    project_root: Path,
    agent_id: str,
    run_id: str,
    command: Sequence[str],
    environment_resource: tuple[int, str],
) -> int:
    environment_fd, environment_path = environment_resource
    try:
        path = runtime.state_file(project_root, agent_id, run_id)
        state = runtime.safe_read_json(path)
        attempt = int(state.get("containmentAttempt", 0)) + 1
        containment = {
            "kind": "systemd-user-service",
            "unitName": runtime.systemd_unit_name(agent_id, run_id, attempt),
            "bindingToken": uuid.uuid4().hex,
            "invocationId": None,
            "weakerDescendantContainment": False,
        }
        runtime.update_json(
            path,
            path.parent / ".state.lock",
            lambda value: value.update(
                {
                    "containmentAttempt": attempt,
                    "containment": containment,
                    "containmentLaunchDisposition": "launching",
                    "status": "starting",
                }
            ),
        )
        result = runtime._systemd_command((
            "systemd-run", "--user", f"--unit={containment['unitName']}",
            f"--description={runtime.SYSTEMD_DESCRIPTION_PREFIX}{containment['bindingToken']}",
            "--collect", "--service-type=exec",
            "--property=KillMode=control-group",
            f"--property=TimeoutStopSec={runtime.PROCESS_TERM_TIMEOUT}s",
            "--property=SendSIGKILL=no",
            f"--property=EnvironmentFile={environment_path}",
            f"--working-directory={project_root}", "--", *command,
        ))
    finally:
        with contextlib.suppress(OSError):
            os.close(environment_fd)
    if result.returncode != 0:
        raise runtime.ContractError(
            "containment_launch_failed",
            "the bound systemd service launch was not acknowledged; the run will not be replayed without reconciliation",
        )
    observed = runtime.query_systemd_containment(containment)
    if observed["invocationId"] is None:
        raise runtime.ContractError("containment_launch_ack_missing", "systemd returned no invocation identity")
    containment = {**containment, "invocationId": observed["invocationId"]}
    state = runtime.update_json(
        path,
        path.parent / ".state.lock",
        lambda value: value.update(
            {
                "containment": containment,
                "containmentLaunchDisposition": "launched",
                "workerPid": observed["mainPid"],
                "status": "queued",
            }
        ),
    )
    worker_pid = state.get("workerPid")
    return worker_pid if isinstance(worker_pid, int) and worker_pid > 0 else 0


def _launch_fallback_worker(
    runtime,
    project_root: Path, agent_id: str, run_id: str, command: Sequence[str]
) -> int:
    command = [
        *command,
    ]
    try:
        process, identity, release_fd = runtime.spawn_contained_process(
            command,
            detach=True,
            cwd=project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except runtime.ContractError as error:
        raise runtime.ContractError(error.code, error.message) from error
    except OSError as error:
        raise runtime.ContractError("worker_start_failed", "background worker could not start") from error
    release_attempted = False
    try:
        path = runtime.state_file(project_root, agent_id, run_id)
        runtime.update_json(
            path,
            path.parent / ".state.lock",
            lambda state: state.update(
                {
                    "workerPid": process.pid,
                    "workerIdentity": identity,
                    "containmentAttempt": int(state.get("containmentAttempt", 0)) + 1,
                    "containment": {
                        "kind": "windows-job",
                        "identity": identity,
                        "weakerDescendantContainment": False,
                    } if runtime.portable.WINDOWS else {
                        "kind": "process-group",
                        "identity": identity,
                        "weakerDescendantContainment": True,
                    },
                    "containmentLaunchDisposition": "launched",
                    "status": "queued",
                }
            ),
        )
        release_attempted = True
        runtime.release_contained_process(process, identity, release_fd)
    except (runtime.ContractError, OSError) as error:
        runtime.abort_contained_process(
            process,
            identity,
            None if release_attempted else release_fd,
        )
        if isinstance(error, runtime.ContractError):
            raise runtime.ContractError(error.code, error.message) from error
        raise runtime.ContractError("worker_start_failed", "background worker could not start") from error
    return process.pid


def spawn_worker(runtime, project_root: Path, agent_id: str, run_id: str) -> int:
    command = [
        sys.executable,
        str(runtime.SCRIPT_PATH),
        "_worker",
        *runtime.runtime_paths.arguments(project_root),
        "--project-root",
        str(project_root),
        "--agent",
        agent_id,
        "--run-id",
        run_id,
    ]
    if runtime.systemd_manager_usable():
        try:
            environment_resource = runtime.create_systemd_environment_file()
        except runtime.ContractError as error:
            if error.code not in {
                "containment_environment_invalid",
                "containment_environment_unavailable",
            }:
                raise
        else:
            return runtime._launch_systemd_worker(
                project_root, agent_id, run_id, command, environment_resource
            )
    return runtime._launch_fallback_worker(project_root, agent_id, run_id, command)


def pid_alive(runtime, pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if runtime.portable.WINDOWS:
        # os.kill(pid, 0) would terminate the process on Windows.
        return runtime.process_containment.process_group_exists(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
