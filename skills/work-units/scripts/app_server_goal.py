#!/usr/bin/env python3
"""Launch a named Work Unit only after app-server confirms its thread Goal."""

from __future__ import annotations

import argparse
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, IO, Sequence


SCHEMA_VERSION = "1.0.0"
CLIENT_NAME = "agent_factory_work_unit_runner"
FACTORY_BRANCH = "factory"
CLIENT_TITLE = "Agent Factory Work Unit Runner"
CLIENT_VERSION = "1.0.0"
WORK_UNIT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MAX_AUTOMATIC_RECOVERIES = 20
MAX_LAUNCHER_FAILURE_RETRIES = 3
WORK_UNIT_MANAGER = (
    Path(__file__).resolve().parents[2]
    / "work-units"
    / "scripts"
    / "work_unit.py"
)
Validator = Callable[[Path, str], dict[str, Any]]
AckEmitter = Callable[[dict[str, Any]], Any]


class ContractError(Exception):
    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError("invalid_arguments", message)


class StreamReader:
    def __init__(self, stream: IO[str]) -> None:
        self.items: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self.thread.start()

    def _read(self, stream: IO[str]) -> None:
        try:
            for line in stream:
                self.items.put(("line", line))
        except (OSError, UnicodeError) as error:
            self.items.put(("error", type(error).__name__))
        finally:
            self.items.put(("eof", None))

    def next(self, deadline: float) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ContractError(
                "app_server_timeout", "timed out waiting for app-server"
            )
        try:
            kind, value = self.items.get(timeout=remaining)
        except queue.Empty as error:
            raise ContractError(
                "app_server_timeout", "timed out waiting for app-server"
            ) from error
        if kind == "line" and value is not None:
            return value
        if kind == "error":
            raise ContractError(
                "app_server_read_failed",
                "unable to read app-server output",
                {"type": value},
            )
        raise ContractError("app_server_eof", "app-server closed its output")


class StderrCollector:
    def __init__(self, stream: IO[str]) -> None:
        self._parts: list[str] = []
        self.thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self.thread.start()

    def _read(self, stream: IO[str]) -> None:
        try:
            for line in stream:
                self._parts.append(line)
                if sum(len(part) for part in self._parts) > 8192:
                    self._parts = ["".join(self._parts)[-4096:]]
        except (OSError, UnicodeError):
            return

    def text(self) -> str:
        return "".join(self._parts).strip()


class AppServerClient:
    def __init__(
        self,
        codex_executable: str,
        deadline: float,
        operations: list[dict[str, Any]],
    ) -> None:
        self.deadline = deadline
        self.operations = operations
        self.next_id = 1
        self.notifications: list[dict[str, Any]] = []
        try:
            self.process = subprocess.Popen(
                [codex_executable, "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="strict",
                bufsize=1,
                shell=False,
            )
        except OSError as error:
            raise ContractError(
                "app_server_start_failed",
                "unable to start codex app-server",
                {"type": type(error).__name__},
            ) from error
        if (
            self.process.stdin is None
            or self.process.stdout is None
            or self.process.stderr is None
        ):
            self.close()
            raise ContractError(
                "app_server_start_failed", "app-server pipes are unavailable"
            )
        self.stdin = self.process.stdin
        self.stdout = StreamReader(self.process.stdout)
        self.stderr = StderrCollector(self.process.stderr)

    def send(self, message: dict[str, Any]) -> None:
        method = message.get("method", "unknown")
        try:
            self.stdin.write(
                json.dumps(
                    message,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            self.stdin.flush()
        except (BrokenPipeError, OSError, UnicodeError) as error:
            raise ContractError(
                "app_server_write_failed",
                "unable to write app-server request",
                {"method": method, "type": type(error).__name__},
            ) from error
        self.operations.append({"direction": "sent", "method": method})

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        self.send(message)

    def read(self) -> dict[str, Any]:
        line = self.stdout.next(self.deadline)
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            raise ContractError(
                "invalid_app_server_json",
                "app-server emitted invalid JSON",
                {"line": line.rstrip("\r\n")[:200]},
            ) from error
        if not isinstance(message, dict):
            raise ContractError(
                "invalid_app_server_message",
                "app-server message must be an object",
            )
        method = message.get("method")
        self.operations.append(
            {
                "direction": "received",
                "method": method if isinstance(method, str) else "response",
            }
        )
        return message

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            message = self.read()
            if message.get("id") == request_id:
                error = message.get("error")
                if error is not None:
                    details = error if isinstance(error, dict) else {"error": error}
                    raise ContractError(
                        "app_server_rpc_error",
                        f"app-server rejected {method}",
                        {"method": method, "rpcError": details},
                    )
                result = message.get("result")
                if not isinstance(result, dict):
                    raise ContractError(
                        "invalid_app_server_response",
                        f"app-server returned an invalid result for {method}",
                        {"method": method},
                    )
                return result
            # Notifications may interleave an RPC response; preserve their
            # arrival order for the protocol state machine instead of dropping them.
            if isinstance(message.get("method"), str) and "id" not in message:
                self.notifications.append(message)
                continue
            raise ContractError(
                "unexpected_app_server_message",
                "received an unrelated app-server message",
            )

    def wait_notification(self, method: str) -> dict[str, Any]:
        for index, message in enumerate(self.notifications):
            if message.get("method") == method:
                return self.notifications.pop(index)
        while True:
            message = self.read()
            if message.get("method") == method and "id" not in message:
                return message
            if isinstance(message.get("method"), str) and "id" not in message:
                self.notifications.append(message)
                continue
            raise ContractError(
                "unexpected_app_server_message",
                "received a response while waiting for a notification",
            )

    def next_notification(self) -> dict[str, Any]:
        if self.notifications:
            return self.notifications.pop(0)
        while True:
            message = self.read()
            if isinstance(message.get("method"), str) and "id" not in message:
                return message
            raise ContractError(
                "unexpected_app_server_message",
                "received a response while waiting for execution events",
            )

    def close(self) -> dict[str, Any]:
        process = getattr(self, "process", None)
        if process is None:
            return {"returnCode": None, "stderr": ""}
        stdin = getattr(self, "stdin", None)
        if stdin is not None:
            try:
                stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
        stderr = getattr(self, "stderr", None)
        stdout = getattr(self, "stdout", None)
        if stdout is not None:
            stdout.thread.join(timeout=1)
        if stderr is not None:
            stderr.thread.join(timeout=1)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        return {
            "returnCode": process.returncode,
            "stderr": stderr.text() if stderr is not None else "",
        }


def absolute_repository(value: Path) -> Path:
    if not value.is_absolute():
        raise ContractError(
            "path_not_absolute",
            "repository must be an absolute path",
            {"value": str(value)},
        )
    try:
        repository = value.resolve(strict=True)
    except OSError as error:
        raise ContractError(
            "invalid_repository",
            "repository does not exist",
            {"type": type(error).__name__},
        ) from error
    if not repository.is_dir():
        raise ContractError("invalid_repository", "repository must be a directory")
    return repository


def manager_validation(package: Path, work_unit_id: str) -> dict[str, Any]:
    validation = subprocess.run(
        [
            sys.executable,
            str(WORK_UNIT_MANAGER),
            "validate",
            str(package),
            "--full",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        shell=False,
    )
    if validation.returncode != 0:
        raise ContractError(
            "work_unit_validation_failed",
            "Work Unit full validation failed",
            {"package": str(package), "stderr": validation.stderr.strip()},
        )
    try:
        payload = json.loads(validation.stdout)
    except json.JSONDecodeError as error:
        raise ContractError(
            "invalid_work_unit_validation",
            "Work Unit manager returned invalid JSON",
            {"package": str(package)},
        ) from error
    if (
        not isinstance(payload, dict)
        or payload.get("valid") is not True
        or payload.get("id") != work_unit_id
    ):
        raise ContractError(
            "work_unit_validation_failed",
            "Work Unit manager did not return a valid matching package",
            {"package": str(package), "validation": payload},
        )
    return payload


def execution_context_section(package: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    shown = subprocess.run(
        [
            sys.executable,
            str(WORK_UNIT_MANAGER),
            "show",
            str(package),
            "--section",
            "execution-context",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        shell=False,
    )
    if shown.returncode != 0:
        raise ContractError(
            "work_unit_show_failed",
            "Work Unit manager could not show the execution context",
            {"package": str(package), "stderr": shown.stderr.strip()},
        )
    try:
        section = json.loads(shown.stdout)
        contexts = [
            item["content"]
            for item in section["content"]
            if item.get("kind") == "execution-context"
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ContractError(
            "invalid_execution_context",
            "Work Unit manager returned an invalid execution context",
            {"package": str(package), "type": type(error).__name__},
        ) from error
    if len(contexts) != 1:
        raise ContractError(
            "invalid_execution_context",
            "Work Unit must contain exactly one execution context",
            {"package": str(package)},
        )
    return section, contexts[0]


def validate_work_unit(repository: Path, work_unit_id: str) -> dict[str, Any]:
    if not WORK_UNIT_ID.fullmatch(work_unit_id):
        raise ContractError(
            "invalid_work_unit_id",
            "work-unit-id contains unsupported characters",
            {"value": work_unit_id},
        )
    git_result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--show-toplevel"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        shell=False,
    )
    if git_result.returncode != 0:
        raise ContractError("invalid_repository", "repository is not a Git worktree")
    reported = Path(git_result.stdout.strip()).resolve(strict=False)
    if reported != repository:
        raise ContractError(
            "repository_root_mismatch",
            "repository must be the Git top-level directory",
            {"expected": str(repository), "actual": str(reported)},
        )
    package = repository / ".agent-factory" / "work-units" / work_unit_id
    validation_payload = manager_validation(package, work_unit_id)
    context_section, context = execution_context_section(package)
    if context.get("goalId") != work_unit_id:
        raise ContractError(
            "goal_id_mismatch",
            "execution context goalId must match work-unit-id",
        )
    if Path(context.get("repository", "")).resolve(strict=False) != repository:
        raise ContractError(
            "execution_repository_mismatch",
            "execution context repository does not match repository",
        )
    execution_route = context.get("executionMode")
    if execution_route not in {
        "workspace-direct",
        "worktree",
        "specification-direct",
    }:
        raise ContractError(
            "invalid_execution_context",
            "executionMode must be workspace-direct, worktree, or "
            "specification-direct",
        )
    mode = launch_mode(validation_payload, context_section, work_unit_id)
    if execution_route == "worktree":
        # A new attempt must start from current factory. Resume and rework keep
        # the existing linked branch so completed work is never replayed or
        # silently rebased under a different source commit.
        if mode == "execution" and context.get("baseRef") != FACTORY_BRANCH:
            raise ContractError(
                "execution_base_mismatch",
                f"worktree execution baseRef must equal {FACTORY_BRANCH}",
            )
        if context.get("targetBranch") != FACTORY_BRANCH:
            raise ContractError(
                "execution_target_mismatch",
                f"worktree execution targetBranch must equal {FACTORY_BRANCH}",
            )
        worktree = repository / ".agent-factory" / "worktree" / work_unit_id
        if Path(context.get("worktreePath", "")).resolve(strict=False) != worktree:
            raise ContractError(
                "execution_worktree_mismatch",
                "execution context worktreePath is not canonical",
            )
        if worktree.exists():
            worktree_result = subprocess.run(
                ["git", "-C", str(worktree), "rev-parse", "--show-toplevel"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="strict",
                check=False,
                shell=False,
            )
            reported_worktree = Path(
                worktree_result.stdout.strip()
            ).resolve(strict=False)
            if worktree_result.returncode != 0 or reported_worktree != worktree:
                raise ContractError(
                    "execution_worktree_mismatch",
                    "canonical execution worktree is not the registered Git worktree",
                )
            branch_result = subprocess.run(
                ["git", "-C", str(worktree), "branch", "--show-current"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="strict",
                check=False,
                shell=False,
            )
            expected_branch = f"work-unit/{work_unit_id}"
            if (
                branch_result.returncode != 0
                or branch_result.stdout.strip() != expected_branch
            ):
                raise ContractError(
                    "execution_branch_mismatch",
                    "canonical execution worktree has the wrong branch",
                    {
                        "actual": branch_result.stdout.strip(),
                        "expected": expected_branch,
                    },
                )
    authorized_tests = (
        context.get("authorizedTests", [])
        if isinstance(context.get("authorizedTests", []), list)
        and all(
            isinstance(command, str) and command.strip()
            for command in context.get("authorizedTests", [])
        )
        else []
    )
    run_documentation = "targetDocumentationRole" in context
    run_review = "targetReviewRole" in context
    return {
        "mode": mode,
        "executionRoute": execution_route,
        "instruction": (
            rework_instruction(context_section) if mode == "rework" else None
        ),
        "objective": work_unit_id,
        "package": str(package),
        "authorizedTests": authorized_tests,
        "runDocumentation": run_documentation,
        "runReview": run_review,
        "orchestrateRoles": bool(
            authorized_tests or run_documentation or run_review
        ),
    }


def launch_mode(
    validation: dict[str, Any],
    execution_context: dict[str, Any],
    work_unit_id: str,
) -> str:
    if (
        validation.get("valid") is not True
        or validation.get("id") != work_unit_id
    ):
        raise ContractError(
            "work_unit_validation_failed",
            "Work Unit manager did not return a valid matching package",
            {"validation": validation},
        )
    if validation.get("status") == "ready":
        return "execution"
    states = [
        item.get("content")
        for item in execution_context.get("content", [])
        if isinstance(item, dict) and item.get("kind") == "execution-state"
    ]
    if validation.get("status") in {"working", "blocked"} and len(states) == 1:
        state = states[0]
        if (
            isinstance(state, dict)
            and state.get("state") == "planned"
            and isinstance(state.get("currentRevision"), int)
            and state["currentRevision"] >= 2
            and state.get("currentAttempt") is None
            and isinstance(state.get("history"), list)
            and len(state["history"]) > 0
        ):
            instruction = state.get("reworkInstruction")
            if not isinstance(instruction, str) or not instruction.strip():
                raise ContractError(
                    "rework_instruction_missing",
                    "planned rework requires an instruction",
                )
            return "rework"
        if (
            isinstance(state, dict)
            and state.get("state") in {"running", "blocked"}
            and isinstance(state.get("currentRevision"), int)
            and state["currentRevision"] >= 1
            and isinstance(state.get("currentAttempt"), int)
            and state["currentAttempt"] >= 1
            and isinstance(state.get("invocationId"), str)
            and state["invocationId"]
            and isinstance(state.get("history"), list)
        ):
            return "resume"
    raise ContractError(
        "work_unit_not_launchable",
        "Work Unit must be ready for initial execution or in planned rework",
        {"status": validation.get("status")},
    )


def rework_instruction(execution_context: dict[str, Any]) -> str | None:
    states = [
        item.get("content")
        for item in execution_context.get("content", [])
        if isinstance(item, dict) and item.get("kind") == "execution-state"
    ]
    if len(states) != 1 or not isinstance(states[0], dict):
        return None
    instruction = states[0].get("reworkInstruction")
    return instruction.strip() if isinstance(instruction, str) else None


def execution_prompt(
    work_unit_id: str,
    mode: str,
    instruction: str | None,
    execution_route: str = "worktree",
) -> str:
    if mode == "execution":
        action = f"execute Agent Factory Work Unit {work_unit_id}"
        instruction_text = ""
    elif mode == "rework":
        if not isinstance(instruction, str) or not instruction.strip():
            raise ContractError(
                "rework_instruction_missing",
                "rework requires a canonical instruction",
            )
        action = (
            "perform rework for Agent Factory Work Unit "
            f"{work_unit_id}"
        )
        instruction_text = (
            f" Rework instruction: {instruction.strip()}"
        )
    elif mode == "resume":
        action = f"resume Agent Factory Work Unit {work_unit_id}"
        instruction_text = (
            " Continue the manager-owned current revision and attempt. "
            "Bind this Goal thread with attempt-resume or blocker-resolve as "
            "applicable, preserve completed work, and do not repeat decisions "
            "already recorded in the canonical package."
        )
    else:
        raise ContractError(
            "invalid_execution_mode",
            "execution mode must be execution, rework, or resume",
            {"mode": mode},
        )
    if execution_route == "workspace-direct":
        route_instruction = (
            "For a workspace-direct Work Unit, edit scoped files in the primary "
            "Git workspace, preserve unrelated changes, and do not create a "
            "branch or linked worktree."
        )
    elif execution_route == "specification-direct":
        route_instruction = (
            "For a Specification-only Work Unit, update the primary root canonical "
            "Specification only through specification.py and do not create a "
            "worktree."
        )
    elif execution_route == "worktree":
        route_instruction = (
            "Create or reuse the dedicated linked worktree before execution-init "
            "or attempt-start; .agent-factory is excluded from that worktree, and "
            "all scoped non-canonical changes belong there."
        )
    else:
        raise ContractError(
            "invalid_execution_route",
            "Workflow Agent execution route is unsupported",
            {"executionRoute": execution_route},
        )
    return (
        "You are the Workflow Agent. You must execute the named Work Unit "
        "without asking for another approval, checkpoint, or readiness "
        f"decision. Use $agents to {action}. The primary agent already "
        "completed the one-time readiness admission and the launcher confirmed "
        "the active Goal. Do not reassess readiness after execution starts. "
        "Read the canonical package and execute only its implementation Work "
        "step. Do not run tests, perform AI Review, update documentation, or "
        "write the final Report. Do not execute lint, typecheck, build, smoke, "
        "runtime verification, git diff --check, or any other verification "
        f"command. {route_instruction}"
        f"{instruction_text}"
    )


def recovery_prompt(
    work_unit_id: str,
    reason: str,
    execution_route: str = "worktree",
) -> str:
    if execution_route == "workspace-direct":
        route_instruction = (
            "Continue in the primary Git workspace, preserve unrelated changes, "
            "and do not create a branch or linked worktree. "
        )
    elif execution_route == "specification-direct":
        route_instruction = (
            "Write only the primary canonical Specification through "
            "specification.py. "
        )
    elif execution_route == "worktree":
        route_instruction = (
            "Continue in the dedicated linked worktree. If it is missing, prepare "
            "it before blocker-resolve or attempt-resume. "
        )
    else:
        raise ContractError(
            "invalid_execution_route",
            "Workflow Agent recovery route is unsupported",
            {"executionRoute": execution_route},
        )
    return (
        "You are the Workflow Agent. You must continue $agents "
        f"execution of Agent Factory Work Unit {work_unit_id}. The prior turn "
        f"ended as {reason}; resume the same manager-owned revision and attempt, "
        "preserve completed work, and do not repeat canonical decisions. Do not "
        "reassess readiness or ask for approval/checkpoint decisions. Continue "
        "the implementation Work step only. Do not run tests, perform AI "
        "Review, update documentation, or write the final Report. Do not execute "
        "lint, typecheck, build, smoke, runtime verification, git diff --check, "
        "or any other verification command. "
        f"{route_instruction}"
        "Removed checkpoint or approval procedures must not block execution."
    )


def test_agent_prompt(
    work_unit_id: str,
    commands: list[str],
    execution_route: str,
    repository: Path,
) -> str:
    rendered = json.dumps(commands, ensure_ascii=False)
    if execution_route == "worktree":
        location = (
            "Run them in the prepared implementation worktree at "
            f"{repository / '.agent-factory' / 'worktree' / work_unit_id}."
        )
    elif execution_route in {"workspace-direct", "specification-direct"}:
        location = (
            f"Run them in the primary repository at {repository}; this "
            "execution mode has no implementation worktree."
        )
    else:
        raise ContractError(
            "invalid_execution_route",
            "Test Agent execution route is unsupported",
            {"executionRoute": execution_route},
        )
    return (
        "You are the Test Agent. Use $agents to execute only the exact "
        f"Human-authorized test commands for Agent Factory Work Unit {work_unit_id}: "
        f"{rendered}. {location} Inspect the implementation there, do "
        "not modify product code, tests, configuration, canonical artifacts, or "
        "any implementation output. Do not run any test, lint, typecheck, build, "
        "smoke, runtime verification, git diff --check, or other verification "
        "command beyond the exact commands listed above, and return a test-only "
        "terminal result."
    )


def documentation_agent_prompt(
    work_unit_id: str, tests_result: str, execution_route: str = "worktree"
) -> str:
    if execution_route == "worktree":
        location = "Non-canonical affected documents belong in the dedicated worktree."
    elif execution_route == "workspace-direct":
        location = (
            "Non-canonical affected documents belong in the primary Git workspace; "
            "preserve unrelated changes."
        )
    elif execution_route == "specification-direct":
        location = "Only canonical Specification documents are in scope."
    else:
        raise ContractError(
            "invalid_execution_route",
            "Documentation Agent execution route is unsupported",
            {"executionRoute": execution_route},
        )
    return (
        "You are the Documentation Agent. Use $agents to update only documents "
        f"directly affected by Agent Factory Work Unit {work_unit_id} after "
        f"implementation. Test handoff: {tests_result}. Inspect the Work Unit and "
        "implementation diff before deciding impact. Do not modify product code, "
        "test code, configuration, or unrelated documents. "
        f"{location} Update canonical documents "
        "only through their owning manager in the primary repository. Complete "
        "the documentation Goal by returning only one JSON object with "
        "affectedPaths, canonicalManagerCommands, and unchangedImpactFindings "
        "string arrays plus roleFailure as a string or null. Do not execute tests, "
        "lint, type checks, builds, smoke checks, runtime verification, "
        "git diff --check, or any other verification command."
    )


def review_agent_prompt(work_unit_id: str, stages: dict[str, Any]) -> str:
    inputs = json.dumps(stages, ensure_ascii=False, sort_keys=True)
    return (
        "You are the Review Agent. Use $agents to perform an independent, "
        f"static review of Agent Factory Work Unit {work_unit_id}. Review the "
        "canonical Work Unit, the implementation diff, the test result or tests "
        "not run evidence, and the Documentation Agent result. Do not modify any "
        "file or canonical artifact. Do not execute tests, lint, build, smoke, or "
        "any other verification command. Return only one JSON object with keys "
        "result ('pass' or 'fail'), checklistResult ('pass' or 'fail'), findings, "
        "blockingFindings, and remainingRisks as arrays containing strings only, "
        "plus inputs as an array of strings. The inputs array must be exactly "
        '["implementation", "tests", "documentation"] in that order. A blocking '
        "finding must produce result 'fail'; never fix a "
        "finding yourself. Launcher stage evidence follows: "
        f"{inputs}"
    )


def agent_result(turn: dict[str, Any]) -> dict[str, Any]:
    items = turn.get("items")
    if not isinstance(items, list):
        raise ContractError("role_result_missing", "completed turn has no items")
    messages = [
        item.get("text")
        for item in items
        if isinstance(item, dict)
        and item.get("type") == "agentMessage"
        and isinstance(item.get("text"), str)
    ]
    if not messages:
        raise ContractError("role_result_missing", "completed turn has no agent result")
    try:
        result = json.loads(messages[-1])
    except json.JSONDecodeError as error:
        raise ContractError(
            "role_result_invalid", "agent result must be one JSON object"
        ) from error
    if not isinstance(result, dict):
        raise ContractError("role_result_invalid", "agent result must be an object")
    return result


def validate_review_result(result: dict[str, Any]) -> dict[str, Any]:
    required_lists = {"findings", "blockingFindings", "remainingRisks", "inputs"}
    if result.get("result") not in {"pass", "fail"} or result.get(
        "checklistResult"
    ) not in {"pass", "fail"}:
        raise ContractError("review_result_invalid", "review status is invalid")
    if any(
        not isinstance(result.get(key), list)
        or not all(isinstance(value, str) for value in result[key])
        for key in required_lists
    ):
        raise ContractError("review_result_invalid", "review lists are invalid")
    if result["blockingFindings"] and result["result"] != "fail":
        raise ContractError(
            "review_result_invalid", "blocking findings require a failed review"
        )
    if result["checklistResult"] == "fail" and result["result"] != "fail":
        raise ContractError(
            "review_result_invalid", "a failed checklist requires a failed review"
        )
    required_inputs = ["implementation", "tests", "documentation"]
    if result["inputs"] != required_inputs:
        raise ContractError(
            "review_result_invalid",
            "review inputs must identify implementation, tests, and documentation",
        )
    return result


def require_passing_review_result(result: dict[str, Any]) -> None:
    if result["result"] != "pass" or result["checklistResult"] != "pass":
        raise ContractError(
            "ai_review_failed",
            "Review Agent did not pass the Work Unit",
            {
                "result": result["result"],
                "checklistResult": result["checklistResult"],
                "blockingFindings": result["blockingFindings"],
            },
        )


def validate_documentation_result(result: dict[str, Any]) -> dict[str, Any]:
    required_lists = {
        "affectedPaths",
        "canonicalManagerCommands",
        "unchangedImpactFindings",
    }
    if any(
        not isinstance(result.get(key), list)
        or not all(isinstance(value, str) for value in result[key])
        for key in required_lists
    ):
        raise ContractError(
            "documentation_result_invalid",
            "Documentation Agent result must include affected-path evidence",
        )
    if result.get("roleFailure") is not None and not isinstance(
        result.get("roleFailure"), str
    ):
        raise ContractError(
            "documentation_result_invalid",
            "Documentation Agent roleFailure must be a string or null",
        )
    return result


def role_recovery_prompt(role: str, work_unit_id: str, reason: str) -> str:
    review_boundary = (
        " Do not modify files or canonical artifacts and do not execute tests, "
        "lint, build, smoke, or other verification commands. Return the same "
        "structured review result."
        if role == "Review Agent"
        else ""
    )
    return (
        f"You are the {role}. Continue only the {role} responsibility for Agent "
        f"Factory Work Unit {work_unit_id}; the prior turn ended as {reason}. "
        "Preserve completed work, do not reassess admission, and do not cross the "
        "role's write or execution boundary."
        f"{review_boundary}"
    )


def goal_value(
    result: dict[str, Any],
    *,
    required: bool,
) -> dict[str, Any]:
    goal = result.get("goal")
    if goal is None and not required:
        return {}
    if not isinstance(goal, dict):
        raise ContractError("goal_missing", "app-server returned no Goal")
    return goal


def validate_goal(
    goal: dict[str, Any],
    thread_id: str,
    objective: str,
    *,
    required_status: str,
) -> None:
    if goal.get("threadId") != thread_id:
        raise ContractError(
            "goal_thread_mismatch",
            "Goal threadId does not match the created thread",
            {"expected": thread_id, "actual": goal.get("threadId")},
        )
    if goal.get("objective") != objective:
        raise ContractError(
            "goal_objective_mismatch",
            "Goal objective does not match work-unit-id",
            {"expected": objective, "actual": goal.get("objective")},
        )
    if goal.get("status") != required_status:
        raise ContractError(
            "goal_not_active" if required_status == "active" else "goal_not_complete",
            f"Goal status must be {required_status}",
            {"actual": goal.get("status")},
        )


def notification_goal(message: dict[str, Any]) -> dict[str, Any]:
    params = message.get("params")
    if not isinstance(params, dict) or not isinstance(params.get("goal"), dict):
        raise ContractError(
            "invalid_goal_notification",
            "thread/goal/updated did not include a Goal",
        )
    return params["goal"]


def run_protocol(
    client: AppServerClient,
    repository: Path,
    work_unit_id: str,
    mode: str,
    instruction: str | None,
    process_started: float,
    existing_thread_id: str | None = None,
    emit_ack: Callable[[str, str, str, dict[str, int]], Any] | None = None,
    objective_override: str | None = None,
    prompt_override: str | None = None,
    recovery_role: str = "Workflow Agent",
    execution_route: str = "worktree",
) -> dict[str, Any]:
    timing = {"processStart": 0}

    def mark(stage: str) -> None:
        timing[stage] = max(0, int((time.monotonic() - process_started) * 1000))

    client.request(
        "initialize",
        {
            "clientInfo": {
                "name": CLIENT_NAME,
                "title": CLIENT_TITLE,
                "version": CLIENT_VERSION,
            }
        },
    )
    client.notify("initialized")
    mark("appServerReady")
    if existing_thread_id is None:
        thread_result = client.request(
            "thread/start",
            {
                "approvalPolicy": "never",
                "cwd": str(repository),
                "sandbox": "danger-full-access",
            },
        )
        thread = thread_result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise ContractError(
                "invalid_thread_response", "thread/start returned no thread id"
            )
        thread_id = thread["id"]
        thread_disposition = "created"
    else:
        if not existing_thread_id.strip():
            raise ContractError(
                "invalid_thread_id", "thread-id must not be empty"
            )
        thread_id = existing_thread_id
        thread_disposition = "reused"
    mark("threadReady")
    objective = objective_override or work_unit_id

    if thread_disposition == "created":
        # New threads retain the three-way fail-closed Goal preflight.
        set_goal = goal_value(
            client.request(
                "thread/goal/set",
                {
                    "threadId": thread_id,
                    "objective": objective,
                    "status": "active",
                },
            ),
            required=True,
        )
        validate_goal(set_goal, thread_id, objective, required_status="active")
        fetched_goal = goal_value(
            client.request("thread/goal/get", {"threadId": thread_id}),
            required=True,
        )
        validate_goal(fetched_goal, thread_id, objective, required_status="active")
        updated_message = client.wait_notification("thread/goal/updated")
        updated_goal = notification_goal(updated_message)
        validate_goal(updated_goal, thread_id, objective, required_status="active")
    else:
        # Reuse is admitted only when the existing thread already owns the
        # matching active Goal; never overwrite an unrelated thread's Goal.
        fetched_goal = goal_value(
            client.request("thread/goal/get", {"threadId": thread_id}),
            required=True,
        )
        validate_goal(fetched_goal, thread_id, objective, required_status="active")
    mark("goalReady")

    turn_ids: list[str] = []
    recovery_count = 0

    def start_turn(prompt: str) -> str:
        turn_result = client.request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
            },
        )
        turn = turn_result.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
            raise ContractError(
                "invalid_turn_response", "turn/start returned no turn id"
            )
        turn_id = turn["id"]
        if turn_id not in turn_ids:
            turn_ids.append(turn_id)
        return turn_id

    def recover(reason: str) -> None:
        nonlocal recovery_count
        if recovery_count >= MAX_AUTOMATIC_RECOVERIES:
            raise ContractError(
                "goal_recovery_exhausted",
                "automatic Goal continuation limit was reached",
                {"reason": reason, "recoveries": recovery_count},
            )
        recovery_count += 1
        # Continuation keeps the same thread and objective; only the turn is
        # replaced so completed idempotent steps remain available to the agent.
        reactivated = goal_value(
            client.request(
                "thread/goal/set",
                {
                    "threadId": thread_id,
                    "objective": objective,
                    "status": "active",
                },
            ),
            required=True,
        )
        validate_goal(
            reactivated, thread_id, objective, required_status="active"
        )
        fetched = goal_value(
            client.request("thread/goal/get", {"threadId": thread_id}),
            required=True,
        )
        validate_goal(fetched, thread_id, objective, required_status="active")
        continuation = (
            recovery_prompt(work_unit_id, reason, execution_route)
            if recovery_role == "Workflow Agent"
            else role_recovery_prompt(recovery_role, work_unit_id, reason)
        )
        start_turn(continuation)

    initial_turn_id = start_turn(
        prompt_override
        or execution_prompt(work_unit_id, mode, instruction, execution_route)
    )
    mark("turnAccepted")
    mark("ackEmitted")
    if emit_ack is not None:
        emit_ack(thread_id, initial_turn_id, thread_disposition, dict(timing))
    completed_goal: dict[str, Any] | None = None
    completed_goal_turn_id: str | None = None
    completed_turns: set[str] = set()
    completed_turn: dict[str, Any] | None = None
    blocked_goal_turn_id: str | None = None

    while True:
        message = client.next_notification()
        method = message.get("method")
        params = message.get("params")
        if method == "thread/goal/updated":
            candidate = notification_goal(message)
            if candidate.get("threadId") != thread_id:
                raise ContractError(
                    "goal_thread_mismatch",
                    "Goal notification belongs to another thread",
                )
            if candidate.get("objective") != objective:
                raise ContractError(
                    "goal_objective_mismatch",
                    "Goal notification objective changed",
                )
            if candidate.get("status") == "complete":
                # Goal and turn completion are independent notifications. Do not
                # return until both refer to a completed execution boundary.
                completed_goal = candidate
                if isinstance(params, dict) and isinstance(params.get("turnId"), str):
                    completed_goal_turn_id = params["turnId"]
                if completed_turns and (
                    completed_goal_turn_id is None
                    or completed_goal_turn_id in completed_turns
                ):
                    return {
                        "goal": completed_goal,
                        "completedTurn": completed_turn,
                        "recoveryCount": recovery_count,
                        "threadId": thread_id,
                        "threadDisposition": thread_disposition,
                        "initializationTimingMs": timing,
                        "turnIds": turn_ids,
                    }
            elif candidate.get("status") == "blocked":
                blocked_goal_turn_id = (
                    params.get("turnId") if isinstance(params, dict) else None
                )
                if (
                    blocked_goal_turn_id is None
                    or blocked_goal_turn_id in completed_turns
                ):
                    recover("blocked")
                    blocked_goal_turn_id = None
        elif method == "turn/started" and isinstance(params, dict):
            candidate = params.get("turn")
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
                if candidate["id"] not in turn_ids:
                    turn_ids.append(candidate["id"])
        elif method == "turn/completed" and isinstance(params, dict):
            if params.get("threadId") != thread_id:
                raise ContractError(
                    "turn_thread_mismatch",
                    "turn/completed belongs to another thread",
                )
            completed = params.get("turn")
            if not isinstance(completed, dict):
                raise ContractError(
                    "invalid_turn_notification",
                    "turn/completed did not include a turn",
                )
            turn_id = completed.get("id")
            status = completed.get("status")
            if not isinstance(turn_id, str):
                raise ContractError(
                    "invalid_turn_notification",
                    "turn/completed did not include a turn id",
                )
            if status == "interrupted":
                completed_turns.add(turn_id)
                recover("interrupted")
                continue
            if status != "completed":
                raise ContractError(
                    "turn_failed",
                    "Work Unit execution turn did not complete",
                    {
                        "threadId": thread_id,
                        "threadDisposition": thread_disposition,
                        "turnIds": list(turn_ids),
                        "terminalTurn": completed,
                        "goal": completed_goal or fetched_goal,
                        "recoveryCount": recovery_count,
                        "initializationTimingMs": dict(timing),
                    },
                )
            completed_turns.add(turn_id)
            completed_turn = completed
            if (
                blocked_goal_turn_id is None
                and completed_goal is None
            ):
                continue
            if (
                blocked_goal_turn_id is None
                or blocked_goal_turn_id == turn_id
            ) and completed_goal is None:
                recover("blocked")
                blocked_goal_turn_id = None
                continue
            if completed_goal is not None and (
                completed_goal_turn_id is None
                or completed_goal_turn_id in completed_turns
            ):
                return {
                    "goal": completed_goal,
                    "completedTurn": completed_turn,
                    "recoveryCount": recovery_count,
                    "threadId": thread_id,
                    "threadDisposition": thread_disposition,
                    "initializationTimingMs": timing,
                    "turnIds": turn_ids,
                }


def success_payload(
    repository: Path,
    work_unit_id: str,
    package: dict[str, Any],
    protocol: dict[str, Any],
    operations: list[dict[str, Any]],
    process: dict[str, Any],
    stages: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "command": "execute",
        "context": {
            "executionMode": package["mode"],
            "executionRoute": package["executionRoute"],
            "goal": protocol["goal"],
            "package": package["package"],
            "repository": str(repository),
            "threadId": protocol["threadId"],
            "threadDisposition": protocol["threadDisposition"],
            "initializationTimingMs": protocol["initializationTimingMs"],
            "turnIds": protocol["turnIds"],
            "recoveryCount": protocol["recoveryCount"],
            "workUnitId": work_unit_id,
            "stages": stages or {"implementation": protocol},
        },
        "error": None,
        "ok": True,
        "operations": operations,
        "process": process,
        "schemaVersion": SCHEMA_VERSION,
        "state": "complete",
    }


def error_payload(
    error: ContractError,
    operations: list[dict[str, Any]],
    process: dict[str, Any] | None,
    stages: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "command": "execute",
        "context": None if stages is None else {"stages": stages},
        "error": {
            "code": error.code,
            "details": error.details,
            "message": error.message,
        },
        "ok": False,
        "operations": operations,
        "process": process,
        "schemaVersion": SCHEMA_VERSION,
        "state": "refused",
    }


def ack_payload(
    repository: Path,
    work_unit_id: str,
    package: dict[str, Any],
    thread_id: str,
    turn_id: str,
    thread_disposition: str,
    initialization_timing_ms: dict[str, int],
) -> dict[str, Any]:
    return {
        "executionMode": package["mode"],
        "executionRoute": package["executionRoute"],
        "package": package["package"],
        "repository": str(repository),
        "schemaVersion": SCHEMA_VERSION,
        "threadId": thread_id,
        "threadDisposition": thread_disposition,
        "turnId": turn_id,
        "initializationTimingMs": initialization_timing_ms,
        "type": "ack",
        "workUnitId": work_unit_id,
    }


def stage_ack_evidence(role: str, protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "stage-ack",
        "role": role,
        "threadId": protocol["threadId"],
        "threadDisposition": protocol["threadDisposition"],
        "turnId": protocol["turnIds"][0],
        "initializationTimingMs": protocol["initializationTimingMs"],
    }


def record_terminal_failure(
    package: str,
    role: str,
    error: ContractError,
    stages: dict[str, Any],
) -> dict[str, Any]:
    stage_name = {
        "Test Agent": "tests",
        "Documentation Agent": "documentation",
        "Review Agent": "review",
    }.get(role, "implementation")
    role_stage = stages.get(stage_name, {})
    turn_ids = role_stage.get("turnIds", []) if isinstance(role_stage, dict) else []
    detail_turn_ids = error.details.get("turnIds", [])
    terminal_id = (
        turn_ids[-1]
        if turn_ids
        else detail_turn_ids[-1]
        if isinstance(detail_turn_ids, list) and detail_turn_ids
        else "unknown"
    )
    evidence = json.dumps(
        {
            "role": role,
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    command = [
        sys.executable,
        str(WORK_UNIT_MANAGER),
        "execution-failure",
        package,
        "--step-id",
        "launcher-terminal-handoff",
        "--classification",
        "permanent",
        "--max-retries",
        str(MAX_LAUNCHER_FAILURE_RETRIES),
        "--evidence",
        evidence,
        "--idempotency-key",
        f"launcher-terminal:{role}:{error.code}:{terminal_id}",
        "--blocker-id",
        "EXECUTION-BLOCKER-LAUNCHER-001",
    ]
    recorded = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        shell=False,
    )
    if recorded.returncode != 0:
        raise ContractError(
            "manager_recovery_failed",
            "launcher could not establish manager-owned recovery state",
            {
                "role": role,
                "originalCode": error.code,
                "returnCode": recorded.returncode,
                "stderr": recorded.stderr.strip(),
            },
        )
    return {
        "recorded": True,
        "returnCode": recorded.returncode,
        "stderr": recorded.stderr.strip(),
    }


def execute(
    *,
    repository: Path,
    work_unit_id: str,
    codex_executable: str,
    timeout_seconds: float,
    validator: Validator = validate_work_unit,
    emit_ack: AckEmitter | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    process_started = time.monotonic()
    operations: list[dict[str, Any]] = []
    client: AppServerClient | None = None
    process_evidence: dict[str, Any] | None = None
    stages: dict[str, Any] | None = None
    active_role = "Workflow Agent"
    try:
        if timeout_seconds <= 0:
            raise ContractError(
                "invalid_timeout", "timeout-seconds must be greater than zero"
            )
        resolved_repository = absolute_repository(repository)
        package = validator(resolved_repository, work_unit_id)
        deadline = time.monotonic() + timeout_seconds
        client = AppServerClient(codex_executable, deadline, operations)
        protocol = run_protocol(
            client,
            resolved_repository,
            work_unit_id,
            package["mode"],
            package.get("instruction"),
            process_started,
            thread_id,
            (
                None
                if emit_ack is None
                else lambda active_thread_id, turn_id, disposition, timing: emit_ack(
                    ack_payload(
                        resolved_repository,
                        work_unit_id,
                        package,
                        active_thread_id,
                        turn_id,
                        disposition,
                        timing,
                    )
                )
            ),
            execution_route=package["executionRoute"],
        )
        implementation_process = client.close()
        client = None
        if not package.get("orchestrateRoles", False):
            process_evidence = implementation_process
            return success_payload(
                resolved_repository,
                work_unit_id,
                package,
                protocol,
                operations,
                process_evidence,
            )
        stages = {
            "implementation": {
                **protocol,
                "ack": stage_ack_evidence("Workflow Agent", protocol),
            },
            "tests": {
                "state": "tests-not-run",
                "reason": "no Human-authorized test commands",
            },
        }
        process_evidence = {"implementation": implementation_process}
        authorized_tests = package.get("authorizedTests", [])
        test_failure: ContractError | None = None
        if authorized_tests:
            active_role = "Test Agent"
            try:
                client = AppServerClient(codex_executable, deadline, operations)
                stages["tests"] = run_protocol(
                    client,
                    resolved_repository,
                    work_unit_id,
                    package["mode"],
                    package.get("instruction"),
                    process_started,
                    objective_override=f"{work_unit_id}:tests",
                    prompt_override=test_agent_prompt(
                        work_unit_id,
                        authorized_tests,
                        package["executionRoute"],
                        resolved_repository,
                    ),
                    recovery_role="Test Agent",
                    execution_route=package["executionRoute"],
                )
                stages["tests"]["ack"] = stage_ack_evidence(
                    "Test Agent", stages["tests"]
                )
            except ContractError as error:
                error.details = {**error.details, "role": "Test Agent"}
                test_failure = error
                stages["tests"] = {
                    "state": "failed",
                    "receipt": error.details,
                    "failure": {
                        "role": "Test Agent",
                        "code": error.code,
                        "message": error.message,
                        "details": error.details,
                    },
                }
                if all(
                    key in error.details
                    for key in (
                        "threadId",
                        "threadDisposition",
                        "turnIds",
                        "initializationTimingMs",
                    )
                ):
                    stages["tests"]["ack"] = {
                        "type": "stage-ack",
                        "role": "Test Agent",
                        "threadId": error.details["threadId"],
                        "threadDisposition": error.details["threadDisposition"],
                        "turnId": error.details["turnIds"][0],
                        "initializationTimingMs": error.details[
                            "initializationTimingMs"
                        ],
                    }
            finally:
                test_process = client.close() if client is not None else None
                stages["tests"]["process"] = test_process
                process_evidence["tests"] = test_process
                client = None
        tests_result = (
            "tests not run"
            if not authorized_tests
            else (
                "Human-authorized tests failed; preserve the terminal test "
                "evidence and inspect the test Goal receipt"
                if test_failure is not None
                else "Human-authorized tests completed; inspect the test Goal receipt"
            )
        )
        documentation_completed_turn = None
        documentation_result = None
        documentation_process = None
        if package.get("runDocumentation", False):
            active_role = "Documentation Agent"
            client = AppServerClient(codex_executable, deadline, operations)
            stages["documentation"] = run_protocol(
                client,
                resolved_repository,
                work_unit_id,
                package["mode"],
                package.get("instruction"),
                process_started,
                objective_override=f"{work_unit_id}:documentation",
                prompt_override=documentation_agent_prompt(
                    work_unit_id, tests_result, package["executionRoute"]
                ),
                recovery_role="Documentation Agent",
                execution_route=package["executionRoute"],
            )
            stages["documentation"]["ack"] = stage_ack_evidence(
                "Documentation Agent", stages["documentation"]
            )
            documentation_completed_turn = stages["documentation"].get("completedTurn")
            if not isinstance(documentation_completed_turn, dict):
                raise ContractError(
                    "documentation_result_missing",
                    "Documentation Agent completed without a result",
                )
            documentation_result = validate_documentation_result(
                agent_result(documentation_completed_turn)
            )
            stages["documentation"]["documentationResult"] = documentation_result
            documentation_process = client.close()
            stages["documentation"]["process"] = documentation_process
            process_evidence["documentation"] = documentation_process
            client = None
        else:
            stages["documentation"] = {"state": "not-requested"}
        review_inputs = {
            "implementation": {
                "ack": stages["implementation"]["ack"],
                "goal": stages["implementation"]["goal"],
                "process": implementation_process,
            },
            "tests": stages["tests"],
            "documentation": stages["documentation"],
        }
        if package.get("runReview", False):
            active_role = "Review Agent"
            client = AppServerClient(codex_executable, deadline, operations)
            stages["review"] = run_protocol(
                client,
                resolved_repository,
                work_unit_id,
                package["mode"],
                package.get("instruction"),
                process_started,
                objective_override=f"{work_unit_id}:review",
                prompt_override=review_agent_prompt(work_unit_id, review_inputs),
                recovery_role="Review Agent",
                execution_route=package["executionRoute"],
            )
            stages["review"]["ack"] = stage_ack_evidence(
                "Review Agent", stages["review"]
            )
            review_process = client.close()
            stages["review"]["process"] = review_process
            process_evidence["review"] = review_process
            client = None
            completed_turn = stages["review"].get("completedTurn")
            if not isinstance(completed_turn, dict):
                raise ContractError(
                    "review_result_missing", "Review Agent completed without a result"
                )
            stages["review"]["aiReviewResult"] = validate_review_result(
                agent_result(completed_turn)
            )
            require_passing_review_result(stages["review"]["aiReviewResult"])
        else:
            stages["review"] = {"state": "not-requested"}
        stages["reportMaterial"] = {
            "implementation": stages["implementation"],
            "tests": stages["tests"],
            "documentation": stages["documentation"],
            "review": stages["review"],
        }
        if test_failure is not None:
            stages["managerRecovery"] = record_terminal_failure(
                package["package"], "Test Agent", test_failure, stages
            )
            return error_payload(
                test_failure,
                operations,
                process_evidence,
                stages,
            )
        return success_payload(
            resolved_repository,
            work_unit_id,
            package,
            protocol,
            operations,
            process_evidence,
            stages,
        )
    except ContractError as error:
        if client is not None:
            failed_process = client.close()
            process_evidence = (
                failed_process
                if process_evidence is None
                else {
                    **process_evidence,
                    "failedRole": {
                        "role": active_role,
                        "process": failed_process,
                    },
                }
            )
        error.details = {**error.details, "role": active_role}
        if stages is not None:
            stages["failure"] = {
                "role": active_role,
                "code": error.code,
                "message": error.message,
            }
            stages["managerRecovery"] = record_terminal_failure(
                package["package"], active_role, error, stages
            )
        return error_payload(error, operations, process_evidence, stages)
    except (OSError, UnicodeError) as error:
        if client is not None:
            failed_process = client.close()
            process_evidence = (
                failed_process
                if process_evidence is None
                else {
                    **process_evidence,
                    "failedRole": {
                        "role": active_role,
                        "process": failed_process,
                    },
                }
            )
        if stages is not None:
            stages["failure"] = {
                "role": active_role,
                "code": "unexpected_io_error",
                "message": "unable to execute Work Unit",
            }
        terminal_error = ContractError(
            "unexpected_io_error",
            "unable to execute Work Unit",
            {"type": type(error).__name__, "role": active_role},
        )
        if stages is not None:
            stages["managerRecovery"] = record_terminal_failure(
                package["package"], active_role, terminal_error, stages
            )
        return error_payload(
            terminal_error,
            operations,
            process_evidence,
            stages,
        )


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="app_server_goal.py")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--work-unit-id", required=True)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--thread-id")
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    return parser


def emit_json(value: dict[str, Any]) -> None:
    sys.stdout.write(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(
            list(sys.argv[1:] if argv is None else argv)
        )
        payload = execute(
            repository=Path(args.repository),
            work_unit_id=args.work_unit_id,
            codex_executable=args.codex,
            timeout_seconds=args.timeout_seconds,
            emit_ack=emit_json,
            thread_id=args.thread_id,
        )
    except ContractError as error:
        payload = error_payload(error, [], None)
    emit_json(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
