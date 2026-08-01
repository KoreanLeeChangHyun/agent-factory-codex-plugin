#!/usr/bin/env python3
"""Launch a script-owned recovery Goal for a Work Package node."""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path
from typing import Any


GOAL_SCRIPT = Path(__file__).resolve().with_name("app_server_goal.py")


def load_goal_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_factory_app_server_goal", GOAL_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Goal launcher: {GOAL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


goal = load_goal_module()
ContractError = goal.ContractError


def resolution_prompt(args: argparse.Namespace) -> str:
    return (
        "You are the Workflow Agent for an Agent Factory Work Package recovery. "
        f"Resolve node {args.node_id} (Work Unit {args.work_unit_id}) in package "
        f"{args.work_package_id}. The deterministic scheduler recorded this error: "
        f"{args.error}. Work only in {args.working_directory}. Preserve unrelated "
        "changes, resolve the recorded execution or merge problem, run focused "
        "verification, and commit the resolution when this is a code worktree. "
        "Do not ask for an approval, checkpoint, or readiness decision. Do not "
        "merge to the Human target branch. Mark this Goal complete only when the "
        f"same idempotency key can be retried safely: {args.idempotency_key}."
    )


def run_protocol(
    client: Any,
    *,
    repository: Path,
    objective: str,
    prompt: str,
) -> dict[str, Any]:
    client.request(
        "initialize",
        {
            "clientInfo": {
                "name": "agent-factory-work-package-resolution",
                "title": "Agent Factory Work Package Resolution",
                "version": "1.0.0",
            }
        },
    )
    client.notify("initialized")
    started = client.request(
        "thread/start",
        {
            "approvalPolicy": "never",
            "cwd": str(repository),
            "sandbox": "danger-full-access",
        },
    )
    thread = started.get("thread")
    if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
        raise ContractError(
            "invalid_thread_response", "thread/start returned no thread id"
        )
    thread_id = thread["id"]
    # Recovery Goals receive the same pre-turn Goal agreement as primary Work
    # Unit Goals; otherwise a resolver could run under stale objective state.
    selected = goal.goal_value(
        client.request(
            "thread/goal/set",
            {"threadId": thread_id, "objective": objective, "status": "active"},
        ),
        required=True,
    )
    goal.validate_goal(selected, thread_id, objective, required_status="active")
    fetched = goal.goal_value(
        client.request("thread/goal/get", {"threadId": thread_id}), required=True
    )
    goal.validate_goal(fetched, thread_id, objective, required_status="active")
    updated = goal.notification_goal(
        client.wait_notification("thread/goal/updated")
    )
    goal.validate_goal(updated, thread_id, objective, required_status="active")

    def start_turn(text: str) -> str:
        result = client.request(
            "turn/start",
            {"threadId": thread_id, "input": [{"type": "text", "text": text}]},
        )
        turn = result.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
            raise ContractError(
                "invalid_turn_response", "turn/start returned no turn id"
            )
        return turn["id"]

    turn_ids = [start_turn(prompt)]
    completed_turns: set[str] = set()
    completed_goal: dict[str, Any] | None = None
    recoveries = 0
    while True:
        message = client.next_notification()
        method = message.get("method")
        params = message.get("params")
        if method == "thread/goal/updated":
            candidate = goal.notification_goal(message)
            if (
                candidate.get("threadId") != thread_id
                or candidate.get("objective") != objective
            ):
                raise ContractError(
                    "resolution_goal_identity_mismatch",
                    "resolution Goal identity changed",
                )
            if candidate.get("status") == "complete":
                completed_goal = candidate
                if completed_turns:
                    return {
                        "goal": candidate,
                        "threadId": thread_id,
                        "turnIds": turn_ids,
                        "recoveryCount": recoveries,
                    }
            elif candidate.get("status") == "blocked":
                # A blocked recovery is retried in the same thread so the retry
                # preserves context and the node's idempotency key.
                if recoveries >= goal.MAX_AUTOMATIC_RECOVERIES:
                    raise ContractError(
                        "resolution_recovery_exhausted",
                        "resolution Goal recovery limit was reached",
                    )
                recoveries += 1
                client.request(
                    "thread/goal/set",
                    {
                        "threadId": thread_id,
                        "objective": objective,
                        "status": "active",
                    },
                )
                turn_ids.append(start_turn(prompt))
        elif method == "turn/completed" and isinstance(params, dict):
            turn = params.get("turn")
            if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
                raise ContractError(
                    "invalid_turn_notification",
                    "resolution turn completion is invalid",
                )
            status = turn.get("status")
            if status == "interrupted":
                if recoveries >= goal.MAX_AUTOMATIC_RECOVERIES:
                    raise ContractError(
                        "resolution_recovery_exhausted",
                        "resolution Goal recovery limit was reached",
                    )
                recoveries += 1
                turn_ids.append(start_turn(prompt))
                continue
            if status != "completed":
                raise ContractError(
                    "resolution_turn_failed",
                    "resolution turn did not complete",
                    {"status": status},
                )
            completed_turns.add(turn["id"])
            if completed_goal is not None:
                return {
                    "goal": completed_goal,
                    "threadId": thread_id,
                    "turnIds": turn_ids,
                    "recoveryCount": recoveries,
                }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repository = Path(args.repository).resolve()
    working_directory = Path(args.working_directory).resolve()
    if not working_directory.is_dir():
        raise ContractError(
            "working_directory_missing",
            "resolution working directory does not exist",
        )
    operations: list[dict[str, Any]] = []
    client = goal.AppServerClient(
        args.codex, time.monotonic() + args.timeout_seconds, operations
    )
    try:
        protocol = run_protocol(
            client,
            repository=working_directory,
            objective=f"{args.work_package_id}:resolve:{args.node_id}",
            prompt=resolution_prompt(args),
        )
        process = client.close()
        return {
            "ok": True,
            "packageId": args.work_package_id,
            "nodeId": args.node_id,
            "protocol": protocol,
            "operations": operations,
            "process": process,
            "repository": str(repository),
            "workingDirectory": str(working_directory),
        }
    except Exception:
        client.close()
        raise


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Launch an Agent Factory Work Package resolution Goal"
    )
    root.add_argument("--repository", required=True)
    root.add_argument("--work-package-id", required=True)
    root.add_argument("--node-id", required=True)
    root.add_argument("--work-unit-id", required=True)
    root.add_argument("--working-directory", required=True)
    root.add_argument("--idempotency-key", required=True)
    root.add_argument("--error", required=True)
    root.add_argument("--codex", default="codex")
    root.add_argument("--timeout-seconds", type=float, default=3600.0)
    return root


def main() -> int:
    try:
        payload = execute(parser().parse_args())
    except ContractError as error:
        payload = {
            "ok": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
        }
    except (OSError, ValueError, RuntimeError) as error:
        payload = {"ok": False, "error": {"message": str(error)}}
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
