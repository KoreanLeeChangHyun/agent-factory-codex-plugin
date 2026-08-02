#!/usr/bin/env python3
"""Execute a canonical Work Package through a deterministic durable DAG scheduler."""

from __future__ import annotations

import argparse
import concurrent.futures
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
    """Run ready nodes concurrently while committing results in stable graph order."""

    def __init__(
        self,
        *,
        package_id: str,
        revision: int,
        definition: dict[str, Any],
        durable_state: dict[str, Any],
        run_node: Callable[[dict[str, Any], str | None, str], dict[str, Any]],
        merge_node: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        resolve_node: Callable[[dict[str, Any], Exception, str], Any],
        emit: Callable[[dict[str, Any]], Any],
        persist: Callable[[dict[str, Any]], Any] | None = None,
        heartbeat_seconds: float = 10.0,
        max_recovery_attempts: int | None = None,
    ) -> None:
        self.package_id = package_id
        self.revision = revision
        self.definition = definition
        self.graph = package_manager.validate_graph(definition["nodes"])
        self.nodes = {node["id"]: node for node in definition["nodes"]}
        self.state = copy.deepcopy(durable_state)
        self.state.setdefault("nodes", {})
        self.state.setdefault("completedOrder", [])
        self.state.setdefault("mergedOrder", [])
        self.state.setdefault("events", [])
        self.run_node = run_node
        self.merge_node = merge_node
        self.resolve_node = resolve_node
        self.emit_callback = emit
        self.persist_callback = persist
        self.heartbeat_seconds = heartbeat_seconds
        self.max_recovery_attempts = max_recovery_attempts
        self.lock = threading.RLock()
        self.specification_lock = threading.Lock()
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

    def merged(self, node_id: str) -> bool:
        return node_id in self.state["mergedOrder"]

    def ready(self) -> list[str]:
        # A prerequisite is usable only after execution and ordered integration;
        # completion alone does not make its code visible to downstream nodes.
        return [
            node_id
            for node_id in self.graph.order
            if not self.completed(node_id)
            and all(
                self.completed(required) and self.merged(required)
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
                base = self.definition.get("integrationBranch")
                if node.get("executionMode") == "specification-direct":
                    # Canonical Specification mutations share the primary root,
                    # so they must be serialized even when the DAG allows parallelism.
                    with self.specification_lock:
                        result = self.run_node(node, base, key)
                else:
                    result = self.run_node(node, base, key)
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
                self.resolve_node(node, error, key)
                if (
                    self.max_recovery_attempts is not None
                    and record["attempts"] >= self.max_recovery_attempts
                ):
                    raise ExecutionError(
                        f"node {node_id} recovery budget exhausted"
                    ) from error
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
                batch = ready[: self.definition["maxParallel"]]
                results: dict[str, dict[str, Any]] = {}
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.definition["maxParallel"]
                ) as pool:
                    future_by_id = {
                        node_id: (
                            pool.submit(
                                lambda value=self.state["nodes"][node_id]["result"]: value
                            )
                            if self.state["nodes"].get(node_id, {}).get("state")
                            == "executed"
                            and "result" in self.state["nodes"][node_id]
                            else pool.submit(self.invoke, self.nodes[node_id])
                        )
                        for node_id in batch
                    }
                    for node_id in batch:
                        results[node_id] = future_by_id[node_id].result()
                # Parallel execution may finish arbitrarily; integration follows
                # graph order to keep branch history and receipts reproducible.
                for node_id in self.graph.order:
                    if node_id not in results:
                        continue
                    node = self.nodes[node_id]
                    record = self.state["nodes"][node_id]
                    if node.get("executionMode") == "specification-direct":
                        merge_result = {"result": "canonical-validated"}
                    else:
                        try:
                            merge_result = self.merge_node(node, results[node_id])
                        except Exception as error:
                            record["state"] = "recovering"
                            self.state["state"] = "recovering"
                            self.event(
                                "node",
                                nodeId=node_id,
                                state="recovering",
                                idempotencyKey=self.node_key(node_id),
                                error=str(error),
                                operation="merge",
                            )
                            self.resolve_node(node, error, self.node_key(node_id))
                            merge_result = self.merge_node(node, results[node_id])
                    record["mergeResult"] = merge_result
                    record["state"] = "completed"
                    if node_id not in self.state["completedOrder"]:
                        self.state["completedOrder"].append(node_id)
                    if node_id not in self.state["mergedOrder"]:
                        self.state["mergedOrder"].append(node_id)
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
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise ExecutionError(f"{label} returned no JSON")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise ExecutionError(f"{label} returned invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ExecutionError(f"{label} returned a non-object")
    return payload


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


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
        self.integration_branch = definition["integrationBranch"]
        self.target_branch = definition["targetBranch"]
        self.integration_worktree = (
            repository
            / ".agent-factory"
            / "worktree"
            / "work-packages"
            / package_id
        )

    def ensure_integration_branch(self) -> None:
        exists = git(
            self.repository,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{self.integration_branch}",
        )
        listing = git(self.repository, "worktree", "list", "--porcelain")
        registered = (
            f"worktree {self.integration_worktree}" in listing.stdout
            and f"branch refs/heads/{self.integration_branch}" in listing.stdout
        )
        if registered:
            return
        if self.integration_worktree.exists():
            raise ExecutionError("package integration branch/worktree collision")
        self.integration_worktree.parent.mkdir(parents=True, exist_ok=True)
        # Delay checkout until sparse rules exclude .agent-factory, keeping the
        # canonical control plane out of this code-only integration worktree.
        arguments = [
            "worktree",
            "add",
            "--no-checkout",
            "--lock",
            "--reason",
            f"Agent Factory Work Package execution: {self.package_id}",
        ]
        if exists.returncode != 0:
            arguments.extend(["-b", self.integration_branch])
        arguments.extend(
            [
                str(self.integration_worktree),
                self.target_branch
                if exists.returncode != 0
                else self.integration_branch,
            ]
        )
        created = git(self.repository, *arguments)
        if created.returncode != 0:
            raise ExecutionError(
                f"cannot create package integration worktree: {created.stderr.strip()}"
            )
        sparse = git(
            self.integration_worktree,
            "sparse-checkout",
            "set",
            "--no-cone",
            "/*",
            "!/.agent-factory/",
        )
        if sparse.returncode != 0:
            raise ExecutionError(
                f"cannot configure package integration worktree: {sparse.stderr.strip()}"
            )
        checkout = git(
            self.integration_worktree,
            "checkout",
            self.integration_branch,
        )
        if checkout.returncode != 0:
            raise ExecutionError(
                f"cannot checkout package integration branch: {checkout.stderr.strip()}"
            )

    def prepare_member_worktree(self, work_unit_id: str) -> dict[str, Any]:
        branch = f"work-unit/{work_unit_id}"
        worktree = self.repository / ".agent-factory" / "worktree" / work_unit_id
        listing = git(self.repository, "worktree", "list", "--porcelain")
        if listing.returncode != 0:
            raise ExecutionError("cannot inspect registered worktrees")
        registered = f"worktree {worktree}" in listing.stdout
        if registered:
            if f"branch refs/heads/{branch}" not in listing.stdout:
                raise ExecutionError("member worktree is registered to another branch")
            return {
                "baseRef": self.integration_branch,
                "branch": branch,
                "reused": True,
                "worktreePath": str(worktree),
            }
        if worktree.exists():
            raise ExecutionError("member worktree path collision")
        branch_exists = git(
            self.repository,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        )
        if branch_exists.returncode == 0:
            raise ExecutionError("member branch exists without its worktree")
        if branch_exists.returncode != 1:
            raise ExecutionError("cannot inspect member branch")
        base = git(
            self.repository,
            "rev-parse",
            "--verify",
            f"{self.integration_branch}^{{commit}}",
        )
        if base.returncode != 0:
            raise ExecutionError("cannot resolve package integration branch")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        # The package integration branch carries prerequisite results; sparse
        # checkout still keeps canonical control-plane data in the primary root.
        created = git(
            self.repository,
            "worktree",
            "add",
            "--no-checkout",
            "--lock",
            "--reason",
            f"Agent Factory Work Package member: {self.package_id}/{work_unit_id}",
            "-b",
            branch,
            str(worktree),
            base.stdout.strip(),
        )
        if created.returncode != 0:
            raise ExecutionError(
                f"cannot create member worktree: {created.stderr.strip()}"
            )
        sparse = git(
            worktree,
            "sparse-checkout",
            "set",
            "--no-cone",
            "/*",
            "!/.agent-factory/",
        )
        if sparse.returncode != 0:
            raise ExecutionError("cannot configure member sparse checkout")
        checkout = git(worktree, "checkout", branch)
        if checkout.returncode != 0:
            raise ExecutionError("cannot checkout member branch")
        return {
            "baseRef": self.integration_branch,
            "branch": branch,
            "reused": False,
            "worktreePath": str(worktree),
        }

    def run_node(
        self, node: dict[str, Any], base: str | None, _key: str
    ) -> dict[str, Any]:
        work_unit_id = node["workUnitId"]
        if node.get("executionMode") == "worktree":
            if base not in {None, self.integration_branch}:
                raise ExecutionError("member base must equal package integration branch")
            self.prepare_member_worktree(work_unit_id)
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

    def merge_node(
        self, node: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        branch = f"work-unit/{node['workUnitId']}"
        before = git(self.integration_worktree, "rev-parse", self.integration_branch)
        if before.returncode != 0:
            raise ExecutionError("cannot resolve package integration branch")
        operation = git(
            self.integration_worktree,
            "merge",
            "--no-ff",
            "--no-edit",
            branch,
        )
        if operation.returncode != 0:
            git(self.integration_worktree, "merge", "--abort")
            raise ExecutionError(
                f"package merge conflict for {node['id']}: {operation.stderr.strip()}"
            )
        after = git(self.integration_worktree, "rev-parse", "HEAD")
        return {
            "result": "merged",
            "nodeId": node["id"],
            "sourceBranch": branch,
            "targetBranch": self.integration_branch,
            "beforeCommit": before.stdout.strip(),
            "afterCommit": after.stdout.strip(),
            "launcher": result,
        }

    def resolve_node(self, node: dict[str, Any], error: Exception, key: str) -> None:
        target = (
            self.repository
            / ".agent-factory"
            / "worktree"
            / node["workUnitId"]
        )
        if "merge conflict" in str(error).lower():
            target = self.integration_worktree
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
                str(target),
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
    runtime.ensure_integration_branch()
    scheduler = DeterministicScheduler(
        package_id=args.package_id,
        revision=state["revision"],
        definition=definition,
        durable_state=state,
        run_node=runtime.run_node,
        merge_node=runtime.merge_node,
        resolve_node=runtime.resolve_node,
        emit=emit_json,
        persist=lambda value: persist_state(package, invocation_id, value),
        heartbeat_seconds=args.heartbeat_seconds,
    )
    final_state = scheduler.run()
    persist_state(package, invocation_id, final_state)
    descriptor, evidence_name = tempfile.mkstemp(
        prefix="work-package-review-", suffix=".json"
    )
    os.close(descriptor)
    evidence_path = Path(evidence_name)
    try:
        evidence_path.write_text(
            json.dumps(
                {
                    "completedOrder": final_state["completedOrder"],
                    "mergedOrder": final_state["mergedOrder"],
                    "aiChecks": [
                        "dag-complete",
                        "deterministic-merge-order",
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
        "integrationBranch": definition["integrationBranch"],
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
