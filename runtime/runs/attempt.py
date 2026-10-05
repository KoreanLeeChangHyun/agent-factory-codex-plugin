"""One worker: provider attempts, terminal state and lesson capture."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import queue
import signal
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from adapters.plan_progress import first_line


def cancel_requested(runtime, state_path: Path, cancel_event: threading.Event, reader=None) -> bool:
    if cancel_event.is_set():
        return True
    with contextlib.suppress(runtime.ContractError):
        return bool((reader.read() if reader is not None else runtime.safe_read_json(state_path)).get("cancelRequested"))
    return False


def run_codex_attempt(
    runtime,
    *,
    project_root: Path,
    session: dict[str, Any],
    state: dict[str, Any],
    attempt: int,
    heartbeat: Any,  # the host script's Heartbeat
    cancel_event: threading.Event,
    expected_agent_id: str,
    expected_run_id: str,
) -> tuple[str, str]:
    state_path = Path(state["requestPath"]).parent / "state.json"
    request = runtime.safe_read_bytes(Path(state["requestPath"]), runtime.MAX_REQUEST_BYTES)
    if hashlib.sha256(request).hexdigest() != state.get("requestHash"):
        raise runtime.AttemptFailure("request_changed", "managed request content changed", False)
    for image in state.get("imageInputs", []):
        content = runtime.safe_read_bytes(Path(image["path"]), runtime.image_input.MAX_IMAGE_BYTES)
        if len(content) != image.get("size") or hashlib.sha256(content).hexdigest() != image.get("sha256"):
            raise runtime.AttemptFailure("input_image_changed", "managed image input changed", False)
    # Validate the output contract and prepare all prompt files before any child launch.
    try:
        prompt_parts = runtime.build_prompt_parts(
            agent_id=str(state["agentId"]),
            role=str(state["role"]),
            request_path=Path(state["requestPath"]),
            request=request,
            result_path=Path(state["resultPath"]),
            run_id=str(state["runId"]),
            receipt_path=(Path(state["receiptPath"]) if state.get("receiptPath") else None),
            receipt_schema_path=(
                Path(state["receiptSchemaPath"]) if state.get("receiptSchemaPath") else None
            ),
            capability_binding_path=(
                Path(state["capabilityBindingPath"])
                if state.get("capabilityBindingPath") else None
            ),
            human_approval_policy=str(state.get("humanApprovalPolicy", "required")),
            inline_response=runtime.inline_result(state),
            task_mode=state.get("taskMode", state.get("executionOptions", {}).get("taskMode", "work-verification")),
            structured_receipt=runtime.structured_receipt(state),
        )
    except runtime.ContractError as error:
        raise runtime.AttemptFailure(error.code, error.message, False) from error
    except (OSError, UnicodeError) as error:
        raise runtime.AttemptFailure("prompt_invalid", "Managed prompt could not be prepared", False) from error
    execution = state.get("executionOptions", {})
    session = dict(session)
    working_directory = runtime.worktrees.checked_path({"projectRoot": str(project_root), **session})
    if state.get("workingDirectory", str(working_directory)) != str(working_directory):
        raise runtime.AttemptFailure("worktree_binding_changed", "Run working directory no longer matches its conversation", False)
    session["workingDirectory"] = str(working_directory)
    from tasks.orchestrator_guard import profile_instruction
    from execution.prompts import PromptParts
    prompt_parts = PromptParts(prompt_parts.fixed + profile_instruction(state, project_root, working_directory), prompt_parts.dynamic)
    if session.get("worktree") or session.get("taskWorkspace"):
        from execution.prompts import PromptParts
        location_guidance = ("\nConversation working directory: " + str(working_directory)
            + ". Perform source edits, commands and tests in this directory. Original workspace: "
            + str(project_root) + ". This explicit conversation worktree overrides the default shared-checkout rule. "
            + "Use the original workspace only as --project-root for Agent Factory runtime identity; "
            + "child Agents inherit this working directory. Do not edit the original checkout while isolated.\n")
        if session.get("taskWorkspace", {}).get("mode") == "code":
            location_guidance += ("Task Work Units (source changes are excluded): " + json.dumps(session["taskWorkspace"], ensure_ascii=False)
                + "\nReceipt changedPaths remain relative to the ORIGINAL project root, using each repository's relativePath prefix. "
                + "Git commits and integration belong to the runtime; do not commit, reset, rebase or clean up. "
                + "For merge conflicts, edit only justified in-scope conflict files and explicitly git add those resolutions. "
                + "If semantics or authority is unclear, preserve the conflict and return needs-human-decision.\n")
        elif session.get("taskWorkspace", {}).get("mode") == "read-only":
            location_guidance += "This task is classified read-only and acquires no Git mutation or code-change authority.\n"
        prompt_parts = PromptParts(prompt_parts.fixed + location_guidance, prompt_parts.dynamic)
    try:
        if "executionPolicy" not in session:
            raise ValueError("Legacy queued run lacks a verified permission snapshot; resubmit with current parent or explicit policy")
        stored_policy = runtime.execution_policy.session_policy(session)
        policy = runtime.execution_policy.normalize(state["executionPolicy"]) if "executionPolicy" in state else stored_policy
        if policy != stored_policy:
            raise ValueError("Run and session execution policies differ")
    except ValueError as error:
        raise runtime.AttemptFailure("execution_policy_mismatch", str(error), False) from error
    session["executionPolicy"] = policy
    for key in ("model", "reasoningEffort", "fast", "goalMode"):
        if key in execution:
            session[key] = execution[key]
    try:
        checked = runtime.adapters.for_session(session).check(session, policy, working_directory, state_path.parent, Path(state["requestPath"]))
    except Exception as error:
        checked = {"passed": False, "error": str(error)}
    if not isinstance(checked, dict):
        checked = {"passed": False, "error": "Invalid execution preflight response"}
    state["executionPolicy"] = policy
    state["executionPreflight"] = checked
    runtime.update_json(state_path, state_path.parent / ".state.lock", lambda value: value.update({"executionPreflight": checked, "executionPolicy": policy}))
    if checked.get("passed") is not True:
        raise runtime.AttemptFailure("execution_preflight_failed", str(checked.get("error") or checked.get("diagnostic") or "Execution policy preflight failed"), False)
    provider_adapter = runtime.adapters.for_session(session)
    provider_adapter.prepare(session, state, request)
    existing_session = session.get("sessionId")
    native_prompt = provider_adapter.uses_prompt_parts(session)
    prompt = prompt_parts.encode() if native_prompt else prompt_parts.full
    command = runtime.adapters.for_session(session).build_command(session, state, existing_session, prompt_parts=native_prompt)
    stderr_path = state_path.parent / "stderr.log"
    runtime.reject_symlink(stderr_path)
    runtime.update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"status": "starting", "attempt": attempt, "startDisposition": "launching"}
        ),
    )
    try:
        process, codex_identity, release_fd = runtime.spawn_contained_process(
            command,
            env={**os.environ, "AGENT_FACTORY_EXECUTION_POLICY": json.dumps(policy, sort_keys=True),
                 "AGENT_FACTORY_PARENT_STATE": str(state_path)},
            cwd=working_directory,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
        )
    except runtime.ContractError as error:
        raise runtime.AttemptFailure(error.code, error.message, False) from error
    except OSError as error:
        raise runtime.AttemptFailure(
            "codex_start_failed", "codex exec could not start", False
        ) from error
    attempt_stopped = False
    def stop_attempt():
        nonlocal attempt_stopped
        if attempt_stopped:
            return
        provider_adapter.before_stop(state_path, session)
        runtime.terminate_attempt_group(process, codex_identity)
        attempt_stopped = True

    release_attempted = False
    try:
        runtime.update_json(
            state_path,
            state_path.parent / ".state.lock",
            lambda value: value.update(
                {
                    "status": "starting",
                    "attempt": attempt,
                    "codexPid": process.pid,
                    "codexIdentity": codex_identity,
                    "lastCodexIdentity": codex_identity,
                }
            ),
        )
        heartbeat.update(
            status="starting",
            attempt=attempt,
            codex_pid=process.pid,
            codex_identity=codex_identity,
        )
        release_attempted = True
        runtime.release_contained_process(process, codex_identity, release_fd)
    except (runtime.ContractError, OSError) as error:
        runtime.abort_contained_process(
            process,
            codex_identity,
            None if release_attempted else release_fd,
        )
        code = error.code if isinstance(error, runtime.ContractError) else "codex_start_failed"
        message = (
            error.message
            if isinstance(error, runtime.ContractError)
            else "codex exec could not start"
        )
        raise runtime.AttemptFailure(code, message, False, False) from error
    if process.stdin is None or process.stdout is None or process.stderr is None:
        stop_attempt()
        raise runtime.AttemptFailure(
            "codex_start_failed", "codex exec pipes are unavailable", False, True
        )
    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except (BrokenPipeError, OSError, UnicodeError) as error:
        stop_attempt()
        raise runtime.AttemptFailure(
            "codex_write_failed", "codex exec rejected the prompt", False, True
        ) from error
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=64)
    readers_stopped = threading.Event()
    threading.Thread(
        target=runtime.read_process_lines, args=(process.stdout, lines, readers_stopped), daemon=True
    ).start()
    threading.Thread(
        target=runtime.stream_stderr, args=(process.stderr, stderr_path, lines, readers_stopped), daemon=True
    ).start()
    started = False
    active_session: str | None = None
    final_messages: list[str] = []
    publication_failed = False
    time.monotonic()  # result unused, but the clock read stays: tests sequence time.monotonic calls
    # Legacy session timeout fields must not terminate valid ongoing work.
    start_deadline = float("inf")
    turn_deadline = float("inf")
    stdout_eof = False
    stderr_eof = False
    control_reader = runtime.runtime_storage.ChangedJsonReader(state_path, runtime.safe_read_json)
    event_writer = runtime.EventLogWriter(Path(state["eventsPath"]))
    usage = runtime.UsageAccumulator()
    runtime.update_json(state_path, state_path.parent / ".state.lock",
                lambda value: runtime.record_attempt(value, attempt, usage.snapshot()))
    try:
        leader_exit_observed = False
        while True:
            # EOF belongs to pipes; it does not establish leader liveness. An
            # inherited pipe must not prevent cleanup of our exited containment.
            if process.poll() is not None and not leader_exit_observed:
                leader_exit_observed = True
                stop_attempt()
            if runtime.cancel_requested(state_path, cancel_event, control_reader):
                stop_attempt()
                raise runtime.AttemptFailure("cancelled", "run was cancelled", started, True)
            current = time.monotonic()
            if not started and current >= start_deadline:
                stop_attempt()
                raise runtime.AttemptFailure(
                    "start_timeout", "codex exec sent no start ACK", False, True
                )
            if current >= turn_deadline:
                stop_attempt()
                raise runtime.AttemptFailure(
                    "turn_timeout", "codex exec exceeded its turn timeout", started, True
                )
            try:
                kind, line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "error":
                stop_attempt()
                raise runtime.AttemptFailure(
                    "event_read_failed", "codex event stream failed", started, True
                )
            if kind == "stderr_error":
                stop_attempt()
                raise runtime.AttemptFailure(
                    "stderr_log_failed", "Codex stderr log could not be persisted", started, True
                )
            if kind == "stderr_overflow":
                stop_attempt()
                raise runtime.AttemptFailure(
                    "stderr_log_limit_exceeded",
                    "Codex stderr exceeded the per-run byte limit",
                    started,
                    True,
                )
            if kind == "stdout_eof":
                stdout_eof = True
                if stderr_eof:
                    break
                continue
            if kind == "stderr_eof":
                stderr_eof = True
                if stdout_eof:
                    break
                continue
            if line is None or (runtime.MAX_EVENT_BYTES is not None and len(line.encode()) > runtime.MAX_EVENT_BYTES):
                stop_attempt()
                raise runtime.AttemptFailure(
                    "event_invalid", "codex emitted an invalid event", started, True
                )
            # Live text previews are superseded by later events; avoid one fsync per streamed fragment.
            if not event_writer.append(line, durable=not line.startswith('{"type": "native.delta"')):
                stop_attempt()
                raise runtime.AttemptFailure(
                    "event_log_limit_exceeded",
                    "Codex events exceeded the per-run byte limit",
                    started,
                    True,
                )
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                stop_attempt()
                raise runtime.AttemptFailure(
                    "event_invalid", "codex emitted malformed JSONL", started, True
                ) from error
            if not isinstance(event, dict):
                stop_attempt()
                raise runtime.AttemptFailure(
                    "event_invalid", "codex emitted an invalid event", started, True
                )
            runtime.capture_lesson(project_root, state, event, attempt)
            if event.get("type") == "error" and provider_adapter.fatal_error_events(session):
                stop_attempt()
                message = str(event.get("message", "Native Codex error"))
                diagnostic = runtime.sandbox_diagnostics.sandbox_failure(message)
                code = event.get("code")
                if code not in {"result_invalid", "result_missing", "authentication_required", "rate_limit_exceeded", "rpc_disconnected"}:
                    code = "native_backend_error"
                details = {key: event[key] for key in ("code", "stage", "turnId", "requestId", "acceptance") if key in event}
                runtime.update_json(state_path, state_path.parent / ".state.lock",
                                    lambda value: value.update(adapterError=details))
                raise runtime.AttemptFailure("sandbox_unavailable" if diagnostic else code, diagnostic or message, started, True)
            if event.get("type") == "rpc.waiting":
                runtime.update_json(state_path, state_path.parent / ".state.lock",
                                    lambda value: value.update(pendingRpc={**event, "observedAt": runtime.now()}))
            if usage.observe(event):
                runtime.update_json(state_path, state_path.parent / ".state.lock",
                            lambda value: runtime.record_attempt(value, attempt, usage.snapshot()))
            if (event.get("type") == "provider.context" and type(event.get("usedTokens")) is int
                    and type(event.get("contextWindowTokens")) is int):
                context_usage = {"usedTokens": event["usedTokens"], "contextWindowTokens": event["contextWindowTokens"]}
                runtime.update_json(state_path, state_path.parent / ".state.lock",
                            lambda value: value.update({"contextUsage": {**(value.get("contextUsage") or {}), **context_usage}}))  # noqa: B023 - update_json calls the lambda before the next iteration
            if event.get("type") == "provider.rate_limits":
                limits = {key: event[key] for key in ("fiveHourUsedPercent", "weeklyUsedPercent",
                                                        "fiveHourResetsAt", "weeklyResetsAt")
                          if type(event.get(key)) in (int, float)}
                if limits:
                    runtime.update_json(state_path, state_path.parent / ".state.lock",
                                lambda value: value.update({"contextUsage": {**(value.get("contextUsage") or {}), **limits}}))  # noqa: B023 - update_json calls the lambda before the next iteration
            if (event.get("type") == "plan.progress" and type(event.get("total")) is int and type(event.get("completed")) is int
                    and 0 < event["total"] <= 200 and 0 <= event["completed"] <= event["total"]):
                progress = {"completed": event["completed"], "total": event["total"]}
                runtime.update_json(state_path, state_path.parent / ".state.lock",
                            lambda value: value.update({"planProgress": progress}))  # noqa: B023 - update_json calls the lambda before the next iteration
            if event.get("type") == "native.commentary":
                # The agent's latest own words, one line, so a status list can say what it is doing.
                line = first_line(event.get("text"))
                if line:
                    runtime.update_json(state_path, state_path.parent / ".state.lock",
                                lambda value: value.update({"activity": line}))  # noqa: B023 - update_json calls the lambda before the next iteration
            if event.get("type") == "goal.error":
                runtime.record_goal_uncertainty(state_path, str(event.get("message", "Native Goal state unconfirmed")))
            if event.get("type") == "thread.started":
                observed = event.get("thread_id")
                if not isinstance(observed, str) or not runtime.SESSION_ID.fullmatch(observed):
                    stop_attempt()
                    raise runtime.AttemptFailure(
                        "session_invalid", "codex returned an invalid session", started, True
                    )
                if existing_session is not None and observed != existing_session:
                    stop_attempt()
                    raise runtime.AttemptFailure(
                        "session_mismatch", "codex resumed a different session", started, True
                    )
                active_session = observed
                started = True
                heartbeat.update(
                    status="running",
                    attempt=attempt,
                    codex_pid=process.pid,
                    codex_identity=codex_identity,
                )
                runtime.update_json(
                    state_path,
                    state_path.parent / ".state.lock",
                    lambda value: value.update(
                        {
                            "status": "running", "sessionId": observed,  # noqa: B023 - update_json calls the lambda before the next iteration
                            "startedAt": runtime.now(), "startDisposition": "started",
                        }
                    ),
                )
                session_path = runtime.session_file(project_root, str(state["agentId"]))
                saved = {key: session[key] for key in ("model", "reasoningEffort", "fast", "goalMode") if key in session}
                saved.update(runtime.adapters.for_session(session).persisted_fields(session))
                saved["sessionId"] = observed
                runtime.update_json(session_path, session_path.parent / ".session-state.lock", lambda value: value.update(saved))  # noqa: B023 - update_json calls the lambda before the next iteration
            publication_status = runtime.result_publication_failure(event, state["resultPath"])
            if publication_status is not None:
                publication_failed = publication_status
            item = event.get("item") if event.get("type") == "item.completed" else None
            if isinstance(item, dict) and item.get("type") in (None, "agent_message"):
                text = item.get("text")
                if isinstance(text, str):
                    final_messages.append(text)
        return_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired as error:
        stop_attempt()
        raise runtime.AttemptFailure(
            "codex_exit_timeout", "codex exec did not exit", started, True
        ) from error
    finally:
        readers_stopped.set()
        event_writer.close()
    # The leader may exit while descendants keep its isolated process group.
    # Contain that group before validating or returning any post-exit outcome.
    stop_attempt()
    if return_code != 0:
        raise runtime.process_exit_failure(return_code, stderr_path, started)
    if not started or active_session is None:
        raise runtime.AttemptFailure(
            "start_ack_missing", "codex exec returned no start ACK", False, True
        )
    if not final_messages:
        raise runtime.AttemptFailure("result_missing", "codex exec returned no terminal result", True)
    try:
        terminal = json.loads(final_messages[-1])
    except json.JSONDecodeError as error:
        raise runtime.AttemptFailure("result_invalid", "codex returned invalid terminal JSON", True) from error
    if isinstance(terminal, dict) and terminal.get("status") == "failed":
        runtime.capture_lesson(project_root, state, {"type": "runtime.failure", "code": "agent_reported_failure"}, attempt)
    try:
        runtime.lesson_capture.replay(project_root, state)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass  # Unsaved captures stay pending in the run and never gate its completion.
    # Persist the answer before any bookkeeping gate: a run failed for a receipt defect
    # keeps its result as evidence instead of losing the work.
    try:
        runtime.publish_terminal_result(terminal, state)
        runtime.update_json(Path(state["statePath"]), Path(state["statePath"]).parent / ".state.lock",
                    lambda value: value.update({"decisionKind": terminal.get("decisionKind"), "decisionScope": terminal.get("decisionScope")}))
    except runtime.ContractError as error:
        raise runtime.AttemptFailure(error.code, error.message, True) from error
    except OSError as error:
        raise runtime.AttemptFailure("result_file_write_failed", "Runtime could not persist the terminal response", True) from error
    result_path = Path(state["resultPath"])
    try:
        result_info = os.lstat(result_path)
    except FileNotFoundError as error:
        raise runtime.missing_result_failure(stderr_path, publication_failed) from error
    if (
        stat.S_ISLNK(result_info.st_mode)
        or not stat.S_ISREG(result_info.st_mode)
        or result_info.st_size == 0
    ):
        raise runtime.AttemptFailure("result_file_invalid", "Agent result path is unsafe", True)
    if terminal["status"] == "completed" and state.get("role") in {"work", "verification"}:
        if state.get("goalObjective") or state.get("executionOptions", {}).get("goalObjective"):
            observation = runtime.safe_read_json(state_path)
            if observation.get("goalError") or (observation.get("goal") or {}).get("status") != "complete":
                raise runtime.AttemptFailure("goal_completion_unconfirmed", "The same run has no confirmed completed Goal; stored result preserved", True)
        try:
            if runtime.structured_receipt(state):
                # Contract 2: the runtime writes the receipt from the Agent's own judgment fields.
                runtime.publish_structured_receipt(
                    project_root, state, terminal, agent_id=expected_agent_id, run_id=expected_run_id)
            runtime.validate_receipt(
                project_root, state, agent_id=expected_agent_id, run_id=expected_run_id)
        except runtime.ContractError as error:
            raise runtime.AttemptFailure(error.code, error.message, True) from error
    return str(terminal["status"]), active_session


def capture_lesson(runtime, project_root, state, event, attempt):
    try:
        result = runtime.lesson_capture.observe(project_root, state, event, attempt)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result = {"saved": False, "error": type(error).__name__}
        pending = runtime.lesson_capture.audit(state)
        if pending:
            result["pending"] = pending[0]
    if result is not None and not result.get("saved"):
        state_path = Path(state["statePath"])
        runtime.update_json(state_path, state_path.parent / ".state.lock",
                    lambda value: value.setdefault("lessonRecording", []).append(result))
    return result


def mark_terminal(
    runtime,
    state_path: Path,
    status: str,
    error: dict[str, str] | None = None,
    *,
    attempt: int | None = None,
    start_disposition: str | None = None,
    active_only: bool = False,
) -> bool:
    """Write a terminal status; with active_only, a run that already ended keeps its own."""
    def change(value: dict[str, Any]) -> None:
        if active_only and value.get("status") not in runtime.ACTIVE_STATES:
            raise runtime.ContractError("run_terminal", "run is already terminal")
        value.update(
            {
                "status": status,
                "codexPid": None,
                "codexIdentity": None,
                "finishedAt": runtime.now(),
                "unread": True,
                "error": error,
            }
        )
        if attempt is not None:
            value["attempt"] = attempt
        if start_disposition is not None:
            value["startDisposition"] = start_disposition

    try:
        runtime.update_json(state_path, state_path.parent / ".state.lock", change)
    except runtime.ContractError as error:
        if not active_only or error.code != "run_terminal":
            raise
        return False
    return True


def worker(runtime, args: argparse.Namespace) -> int:
    project_root = runtime.resolve_project_root(args.project_root)
    state_path = runtime.state_file(project_root, args.agent, args.run_id)
    state = runtime.find_run(project_root, args.agent, args.run_id)
    worker_identity = runtime.process_identity(os.getpid())
    runtime.update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"workerPid": os.getpid(), "workerIdentity": worker_identity}
        ),
    )
    session = runtime.load_session(project_root, args.agent)
    heartbeat = runtime.Heartbeat(
        Path(state["heartbeatPath"]), state_path, float(session["heartbeatInterval"])
    )
    cancel_event = threading.Event()

    def request_cancel(_signum: int, _frame: object) -> None:
        cancel_event.set()

    signal.signal(signal.SIGTERM, request_cancel)
    signal.signal(signal.SIGINT, request_cancel)
    heartbeat.start()
    lock_path = runtime.agent_directory(project_root, args.agent) / ".session.lock"
    try:
        with runtime.file_lock(lock_path):
            state = runtime.safe_read_json(state_path)
            if state.get("status") in runtime.TERMINAL_STATES:
                return 0
            if state.get("cancelRequested") is True:
                runtime.mark_terminal(state_path, "cancelled")
                heartbeat.update(status="cancelled", attempt=0, codex_pid=None)
                return 1
            max_attempts = int(state["maxAttempts"])
            while int(state.get("attempt", 0)) < max_attempts:
                attempt = int(state.get("attempt", 0)) + 1
                try:
                    attempt_state = runtime.safe_read_json(state_path)
                    terminal_status, _session_id = runtime.run_codex_attempt(
                        project_root=project_root,
                        session=runtime.load_session(project_root, args.agent),
                        state=attempt_state,
                        attempt=attempt,
                        heartbeat=heartbeat,
                        cancel_event=cancel_event,
                        expected_agent_id=args.agent,
                        expected_run_id=args.run_id,
                    )
                    runtime.mark_terminal(state_path, terminal_status)
                    heartbeat.update(
                        status=terminal_status, attempt=attempt, codex_pid=None
                    )
                    return 0 if terminal_status != "failed" else 1
                except runtime.AttemptFailure as failure:
                    if failure.code != "cancelled":
                        runtime.capture_lesson(project_root, state, {"type": "runtime.failure", "code": failure.code}, attempt)
                    disposition = (
                        "started"
                        if failure.started
                        else "launching"
                        if failure.launched
                        else "not-started"
                    )
                    if failure.code == "cancelled":
                        runtime.mark_terminal(
                            state_path,
                            "cancelled",
                            attempt=attempt,
                            start_disposition=disposition,
                        )
                        heartbeat.update(status="cancelled", attempt=attempt, codex_pid=None)
                        return 1
                    if failure.started or failure.launched or attempt >= max_attempts or failure.code in {"execution_preflight_failed", "execution_policy_mismatch"}:
                        runtime.mark_terminal(
                            state_path,
                            "failed",
                            {"code": failure.code, "message": failure.message},
                            attempt=attempt,
                            start_disposition=disposition,
                        )
                        heartbeat.update(
                            status="failed", attempt=attempt, codex_pid=None
                        )
                        return 1
                    state = runtime.update_json(
                        state_path,
                        state_path.parent / ".state.lock",
                        lambda value: value.update(
                            {
                                "attempt": attempt,  # noqa: B023 - update_json calls the lambda before the next iteration
                                "codexPid": None,
                                "codexIdentity": None,
                                "status": "queued",
                                "startDisposition": disposition,  # noqa: B023 - update_json calls the lambda before the next iteration
                            }
                        ),
                    )
                    heartbeat.update(status="queued", attempt=attempt, codex_pid=None)
            failure = runtime.AttemptFailure(
                "attempts_exhausted", "no execution attempt remained", False
            )
            runtime.mark_terminal(
                state_path,
                "failed",
                {"code": failure.code, "message": failure.message},
            )
            heartbeat.update(
                status="failed", attempt=int(state.get("attempt", 0)), codex_pid=None
            )
            return 1
    except runtime.ContractError as error:
        with contextlib.suppress(Exception):
            runtime.mark_terminal(
                state_path, "failed", {"code": error.code, "message": error.message}
            )
        heartbeat.update(status="failed", attempt=0, codex_pid=None)
        return 1
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        with contextlib.suppress(Exception):
            runtime.mark_terminal(
                state_path,
                "failed",
                {"code": "worker_failure", "message": str(error)},
            )
        heartbeat.update(status="failed", attempt=0, codex_pid=None)
        return 1
    finally:
        # The run's outcome is stored; now record what earlier runs could not write. Best effort:
        # it never changes this run's status and whatever fails stays pending.
        with contextlib.suppress(Exception):
            runtime.lesson_capture.replay(project_root, state)
            runtime.lesson_capture.apply_pending(project_root, state)
            runtime.update_json(state_path, state_path.parent / ".state.lock",
                                lambda value: value.update(pendingLessons=len(runtime.lesson_capture.audit(state))))
        heartbeat.close()
