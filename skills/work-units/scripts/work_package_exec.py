#!/usr/bin/env python3
"""Execute a canonical Work Package through a deterministic durable DAG scheduler."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
WORK_PACKAGE_MANAGER = (
    SKILL_ROOT.parent / "work-units" / "scripts" / "work_package.py"
)
WORK_UNIT_LAUNCHER = SCRIPT_ROOT / "app_server_goal.py"
SPECIFICATION_MANAGER = (
    SKILL_ROOT.parent / "specifications" / "scripts" / "specification.py"
)
RESOLUTION_LAUNCHER = SCRIPT_ROOT / "app_server_resolution_goal.py"
DEFAULT_MAX_RECOVERY_ATTEMPTS = 3


def load_package_manager() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_factory_work_package_manager", WORK_PACKAGE_MANAGER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Work Package manager: {WORK_PACKAGE_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package_manager = load_package_manager()
ManagerError = package_manager.ManagerError


class ExecutionError(RuntimeError):
    pass


class DeterministicScheduler:
    """Run ready nodes in stable order in the shared primary workspace."""

    def __init__(
        self,
        *,
        package_id: str,
        revision: int,
        definition: dict[str, Any],
        durable_state: dict[str, Any],
        run_node: Callable[[dict[str, Any], str | None, str], dict[str, Any]],
        resolve_node: Callable[[dict[str, Any], Exception, str], Any],
        emit: Callable[[dict[str, Any]], Any],
        persist: Callable[[dict[str, Any]], Any] | None = None,
        heartbeat_seconds: float = 10.0,
        max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
    ) -> None:
        self.package_id = package_id
        self.revision = revision
        self.definition = definition
        self.graph = package_manager.validate_graph(definition["nodes"])
        self.nodes = {node["id"]: node for node in definition["nodes"]}
        self.state = copy.deepcopy(durable_state)
        self.state.setdefault("nodes", {})
        self.state.setdefault("completedOrder", [])
        self.state.setdefault("events", [])
        self.run_node = run_node
        self.resolve_node = resolve_node
        self.emit_callback = emit
        self.persist_callback = persist
        self.heartbeat_seconds = heartbeat_seconds
        if (
            not isinstance(max_recovery_attempts, int)
            or isinstance(max_recovery_attempts, bool)
            or max_recovery_attempts <= 0
        ):
            raise ExecutionError("node recovery budget must be positive")
        self.max_recovery_attempts = max_recovery_attempts
        self.lock = threading.RLock()
        self.stop_heartbeat = threading.Event()

    def event(self, event_type: str, **values: Any) -> dict[str, Any]:
        with self.lock:
            event = {
                "type": event_type,
                "packageId": self.package_id,
                "revision": self.revision,
                "at": time.time(),
                **values,
            }
            self.state["events"].append(
                {"sequence": len(self.state["events"]) + 1, **event}
            )
            self.emit_callback(event)
            if self.persist_callback is not None:
                self.persist_callback(copy.deepcopy(self.state))
            return event

    def heartbeat_loop(self) -> None:
        while not self.stop_heartbeat.wait(self.heartbeat_seconds):
            with self.lock:
                lease = self.state.get("lease")
                if isinstance(lease, dict):
                    lease["renewedAtEpoch"] = time.time()
            self.event("heartbeat", state=self.state.get("state", "working"))

    def node_key(self, node_id: str) -> str:
        return f"{self.package_id}:{self.revision}:{node_id}"

    def completed(self, node_id: str) -> bool:
        return self.state["nodes"].get(node_id, {}).get("state") == "completed"

    def ready(self) -> list[str]:
        # Every node edits the primary workspace, so completed prerequisite
        # changes are immediately visible to downstream nodes.
        return [
            node_id
            for node_id in self.graph.order
            if not self.completed(node_id)
            and all(
                self.completed(required)
                for required in self.graph.prerequisites[node_id]
            )
        ]

    def invoke(self, node: dict[str, Any]) -> dict[str, Any]:
        node_id = node["id"]
        key = self.node_key(node_id)
        record = self.state["nodes"].setdefault(
            node_id, {"state": "pending", "attempts": 0}
        )
        while True:
            record["state"] = "running"
            record["idempotencyKey"] = key
            record["attempts"] = record.get("attempts", 0) + 1
            self.event(
                "node",
                nodeId=node_id,
                state="running",
                idempotencyKey=key,
                attempt=record["attempts"],
            )
            try:
                result = self.run_node(node, None, key)
                record["result"] = result
                record["state"] = "executed"
                self.event(
                    "node",
                    nodeId=node_id,
                    state="executed",
                    idempotencyKey=key,
                )
                return result
            except Exception as error:
                record["state"] = "recovering"
                record.setdefault("errors", []).append(
                    {
                        "attempt": record["attempts"],
                        "message": str(error),
                        "type": type(error).__name__,
                    }
                )
                self.state["state"] = "recovering"
                self.event(
                    "node",
                    nodeId=node_id,
                    state="recovering",
                    idempotencyKey=key,
                    error=str(error),
                )
                if record["attempts"] >= self.max_recovery_attempts:
                    raise ExecutionError(
                        f"node {node_id} recovery budget exhausted"
                    ) from error
                self.resolve_node(node, error, key)
                backoff = self.definition.get("executionPolicy", {}).get(
                    "retryBackoffSeconds", [0]
                )
                delay = backoff[min(record["attempts"] - 1, len(backoff) - 1)]
                if delay:
                    time.sleep(delay)
                self.state["state"] = "working"

    def run(self) -> dict[str, Any]:
        self.state["state"] = "working"
        heartbeat = threading.Thread(
            target=self.heartbeat_loop,
            name=f"work-package-heartbeat-{self.package_id}",
            daemon=True,
        )
        heartbeat.start()
        self.event("heartbeat", state="working")
        try:
            while not all(self.completed(node_id) for node_id in self.graph.order):
                ready = self.ready()
                if not ready:
                    raise ExecutionError("scheduler has no ready node before completion")
                # Direct workspace writers are deliberately serialized until a
                # separate directory-scope contract can prove disjoint writes.
                node_id = ready[0]
                record = self.state["nodes"].get(node_id, {})
                if record.get("state") != "executed" or "result" not in record:
                    self.invoke(self.nodes[node_id])
                record = self.state["nodes"][node_id]
                record["state"] = "completed"
                if node_id not in self.state["completedOrder"]:
                    self.state["completedOrder"].append(node_id)
                self.state["state"] = "working"
                self.event(
                    "node",
                    nodeId=node_id,
                    state="completed",
                    idempotencyKey=self.node_key(node_id),
                )
            self.state["state"] = "review"
            self.event("package", state="review")
            return self.state
        finally:
            self.stop_heartbeat.set()
            heartbeat.join(timeout=max(self.heartbeat_seconds, 0.1) + 0.1)


def run_json_command(arguments: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(
        arguments,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ExecutionError(f"{label} failed: {result.stderr.strip()}")
    output = result.stdout.strip()
    if not output:
        raise ExecutionError(f"{label} returned no JSON")
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        lines = [line for line in output.splitlines() if line.strip()]
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            raise ExecutionError(f"{label} returned invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ExecutionError(f"{label} returned a non-object")
    return payload


def member_review_result(launch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(launch, dict):
        raise ExecutionError("Work Unit returned no AI review result")
    context = launch.get("context")
    stages = context.get("stages") if isinstance(context, dict) else None
    review_stage = stages.get("review") if isinstance(stages, dict) else None
    review = (
        review_stage.get("aiReviewResult")
        if isinstance(review_stage, dict)
        else None
    )
    if not isinstance(review, dict):
        raise ExecutionError("Work Unit returned no AI review result")
    if review.get("result") != "pass" or review.get("checklistResult") != "pass":
        raise ExecutionError("Work Unit AI review did not pass")
    return review


def package_review_evidence(state: dict[str, Any]) -> dict[str, Any]:
    member_reviews = {
        node_id: member_review_result(record.get("result", {}))
        for node_id, record in sorted(state.get("nodes", {}).items())
    }
    return {
        "result": (
            "pass"
            if member_reviews
            and all(review["result"] == "pass" for review in member_reviews.values())
            else "fail"
        ),
        "checklistResult": (
            "pass"
            if member_reviews
            and all(
                review["checklistResult"] == "pass"
                for review in member_reviews.values()
            )
            else "fail"
        ),
        "memberReviews": member_reviews,
    }


class PackageRuntime:
    def __init__(
        self,
        *,
        repository: Path,
        package_id: str,
        definition: dict[str, Any],
    ) -> None:
        self.repository = repository
        self.package_id = package_id
        self.definition = definition

    def run_node(
        self, node: dict[str, Any], _base: str | None, _key: str
    ) -> dict[str, Any]:
        work_unit_id = node["workUnitId"]
        launch = run_json_command(
            [
                sys.executable,
                str(WORK_UNIT_LAUNCHER),
                "--repository",
                str(self.repository),
                "--work-unit-id",
                work_unit_id,
            ],
            f"launch Work Unit {work_unit_id}",
        )
        member_review_result(launch)
        if node.get("executionMode") == "specification-direct":
            check = subprocess.run(
                [sys.executable, str(SPECIFICATION_MANAGER), "check-schemas"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if check.returncode != 0:
                raise ExecutionError(
                    f"Specification schema validation failed: {check.stderr.strip()}"
                )
            specifications = (
                self.repository / ".agent-factory" / "specifications"
            )
            for package in sorted(
                path for path in specifications.iterdir() if path.is_dir()
            ):
                validation = subprocess.run(
                    [
                        sys.executable,
                        str(SPECIFICATION_MANAGER),
                        "validate",
                        str(package),
                        "--full",
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if validation.returncode != 0:
                    raise ExecutionError(
                        "Specification full validation failed for "
                        f"{package.name}: {validation.stderr.strip()}"
                    )
        return launch

    def resolve_node(self, node: dict[str, Any], error: Exception, key: str) -> None:
        result = run_json_command(
            [
                sys.executable,
                str(RESOLUTION_LAUNCHER),
                "--repository",
                str(self.repository),
                "--work-package-id",
                self.package_id,
                "--node-id",
                node["id"],
                "--work-unit-id",
                node["workUnitId"],
                "--working-directory",
                str(self.repository),
                "--idempotency-key",
                key,
                "--error",
                str(error),
            ],
            f"resolution Goal for node {node['id']}",
        )
        if result.get("ok") is not True:
            raise ExecutionError(f"resolution Goal did not complete for {node['id']}")


def emit_json(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def manager_call(*arguments: str) -> dict[str, Any]:
    return run_json_command(
        [sys.executable, str(WORK_PACKAGE_MANAGER), *arguments],
        f"work_package.py {arguments[0]}",
    )


def load_section(package: Path, section_id: str) -> dict[str, Any]:
    return manager_call("show", str(package), "--section", section_id)


def content_by_kind(section: dict[str, Any], kind: str) -> dict[str, Any]:
    matches = [
        item
        for container in [section, *section.get("subsections", [])]
        for item in container["content"]
        if item["kind"] == kind
    ]
    if len(matches) != 1:
        raise ExecutionError(f"section requires exactly one {kind}")
    return matches[0]


def persist_state(
    package: Path, invocation_id: str, state: dict[str, Any]
) -> None:
    descriptor, filename = tempfile.mkstemp(prefix="work-package-state-", suffix=".json")
    os.close(descriptor)
    path = Path(filename)
    try:
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        manager_call(
            "state-put",
            str(package),
            "--file",
            str(path),
            "--invocation-id",
            invocation_id,
        )
    finally:
        path.unlink(missing_ok=True)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repository = Path(os.path.abspath(args.repository))
    package = (
        repository / ".agent-factory" / "work-packages" / args.package_id
    )
    invocation_id = args.invocation_id or str(uuid.uuid4())
    start_arguments = [
        "execution-start",
        str(package),
        "--repository",
        str(repository),
        "--invocation-id",
        invocation_id,
    ]
    if args.resume_owner:
        start_arguments.extend(["--resume-owner", args.resume_owner])
    ack = manager_call(*start_arguments)
    emit_json({"type": "ack", **ack})
    definition = content_by_kind(
        load_section(package, "definition"), "package-definition"
    )["content"]
    state = content_by_kind(
        load_section(package, "execution"), "execution-state"
    )["content"]
    runtime = PackageRuntime(
        repository=repository,
        package_id=args.package_id,
        definition=definition,
    )
    scheduler = DeterministicScheduler(
        package_id=args.package_id,
        revision=state["revision"],
        definition=definition,
        durable_state=state,
        run_node=runtime.run_node,
        resolve_node=runtime.resolve_node,
        emit=emit_json,
        persist=lambda value: persist_state(package, invocation_id, value),
        heartbeat_seconds=args.heartbeat_seconds,
        max_recovery_attempts=definition.get("executionPolicy", {}).get(
            "maxRecoveryAttempts", args.max_recovery_attempts
        ),
    )
    final_state = scheduler.run()
    persist_state(package, invocation_id, final_state)
    review_evidence = package_review_evidence(final_state)
    descriptor, evidence_name = tempfile.mkstemp(
        prefix="work-package-review-", suffix=".json"
    )
    os.close(descriptor)
    evidence_path = Path(evidence_name)
    try:
        evidence_path.write_text(
            json.dumps(
                {
                    **review_evidence,
                    "completedOrder": final_state["completedOrder"],
                    "aiChecks": [
                        "dag-complete",
                        "deterministic-execution-order",
                        "member-traceability",
                        "durable-event-log",
                    ],
                    "eventCount": len(final_state["events"]),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manager_call(
            "review-put",
            str(package),
            "--evidence-file",
            str(evidence_path),
        )
    finally:
        evidence_path.unlink(missing_ok=True)
    return {
        "ok": True,
        "packageId": args.package_id,
        "invocationId": invocation_id,
        "state": final_state["state"],
        "completedOrder": final_state["completedOrder"],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Execute an Agent Factory Work Package DAG"
    )
    root.add_argument("--repository", required=True)
    root.add_argument("--package-id", required=True)
    root.add_argument("--invocation-id")
    root.add_argument("--resume-owner")
    root.add_argument("--heartbeat-seconds", type=float, default=10.0)
    root.add_argument(
        "--max-recovery-attempts",
        type=int,
        default=DEFAULT_MAX_RECOVERY_ATTEMPTS,
    )
    return root


def main() -> int:
    try:
        result = execute(parser().parse_args())
        emit_json({"type": "terminal", **result})
        return 0
    except (ExecutionError, ManagerError, OSError, ValueError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
