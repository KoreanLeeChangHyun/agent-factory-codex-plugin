#!/usr/bin/env python3
"""Manage canonical Agent Factory Work Package DAGs and durable execution state."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
COMMON_MANAGER = (
    SKILL_ROOT.parent / "lifecycle" / "scripts" / "sectioned_document.py"
)
COMMON_SCHEMA_ROOT = (
    SKILL_ROOT.parent
    / "lifecycle"
    / "assets"
    / "schema"
    / "sectioned-document"
)
WORK_UNIT_MANAGER = SCRIPT_ROOT / "work_unit.py"
WORK_UNIT_LAUNCHER = (
    SKILL_ROOT.parent / "work-units" / "scripts" / "app_server_goal.py"
)


def load_base_manager() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_factory_work_package_document", COMMON_MANAGER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sectioned document manager: {COMMON_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_base_manager()
ManagerError = base.ManagerError
base.configure_contract(
    skill_root=SKILL_ROOT,
    profile_path=SKILL_ROOT / "assets" / "profiles" / "work-package.profile.json",
    metadata_schema_path=(
        SKILL_ROOT / "assets" / "schema" / "work-package" / "metadata.schema.json"
    ),
    structural_schema_root=COMMON_SCHEMA_ROOT,
    artifact_type="work-package",
    artifact_label="Work Package",
    package_collection="work-packages",
    lifecycle_phase="work-package",
    initial_status="draft",
    initial_readiness={
        "contractValid": True,
        "definitionComplete": False,
        "reviewedAt": None,
        "findings": [],
    },
    generated_by="Agent Factory work-package manager",
)


def profile() -> dict[str, Any]:
    raw = base.load_object(base.PROFILE_PATH, "Work Package profile")
    normalized = dict(raw)
    normalized["requiredSections"] = [
        *raw.get("commonRequiredSections", []),
        *raw.get("profileRequiredSections", []),
    ]
    return normalized


base.profile = profile


@dataclass(frozen=True)
class Graph:
    order: tuple[str, ...]
    initial_ready: tuple[str, ...]
    prerequisites: dict[str, tuple[str, ...]]
    descendants: dict[str, tuple[str, ...]]


def non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManagerError(f"{label} must be a non-empty string")
    return value


def validate_graph(nodes: Any) -> Graph:
    if not isinstance(nodes, list) or not nodes:
        raise ManagerError("Work Package nodes must be a non-empty array")
    by_id: dict[str, dict[str, Any]] = {}
    prerequisites: dict[str, tuple[str, ...]] = {}
    work_units: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ManagerError("Work Package node must be an object")
        node_id = non_empty_string(node.get("id"), "node id")
        work_unit_id = non_empty_string(node.get("workUnitId"), "node workUnitId")
        if node_id in by_id:
            raise ManagerError(f"duplicate Work Package node id: {node_id}")
        if work_unit_id in work_units:
            raise ManagerError(f"duplicate Work Unit member: {work_unit_id}")
        raw_prerequisites = node.get("prerequisites")
        if not isinstance(raw_prerequisites, list) or any(
            not isinstance(item, str) or not item for item in raw_prerequisites
        ):
            raise ManagerError(f"node {node_id} prerequisites must be a string array")
        if len(raw_prerequisites) != len(set(raw_prerequisites)):
            raise ManagerError(f"node {node_id} prerequisites must be unique")
        if node_id in raw_prerequisites:
            raise ManagerError(f"node {node_id} must not depend on itself")
        mode = node.get("executionMode")
        if mode not in {
            "workspace-direct",
            "specification-direct",
        }:
            raise ManagerError(f"node {node_id} has invalid executionMode")
        by_id[node_id] = node
        work_units.add(work_unit_id)
        prerequisites[node_id] = tuple(sorted(raw_prerequisites))
    missing = sorted(
        {
            prerequisite
            for required in prerequisites.values()
            for prerequisite in required
            if prerequisite not in by_id
        }
    )
    if missing:
        raise ManagerError(
            f"Work Package prerequisites reference missing nodes: {', '.join(missing)}"
        )
    # Sorted Kahn traversal makes both scheduling order and persisted evidence
    # deterministic for equivalent package definitions.
    remaining = {node_id: set(required) for node_id, required in prerequisites.items()}
    order: list[str] = []
    while remaining:
        ready = sorted(
            node_id for node_id, required in remaining.items() if not required
        )
        if not ready:
            raise ManagerError("Work Package graph contains a cycle")
        for node_id in ready:
            order.append(node_id)
            remaining.pop(node_id)
        for required in remaining.values():
            required.difference_update(ready)
    descendants: dict[str, tuple[str, ...]] = {}
    for root in by_id:
        selected: set[str] = set()
        pending = [root]
        while pending:
            current = pending.pop()
            children = [
                node_id
                for node_id, required in prerequisites.items()
                if current in required and node_id not in selected
            ]
            selected.update(children)
            pending.extend(children)
        descendants[root] = tuple(node_id for node_id in order if node_id in selected)
    return Graph(
        order=tuple(order),
        initial_ready=tuple(
            node_id for node_id in order if not prerequisites[node_id]
        ),
        prerequisites=prerequisites,
        descendants=descendants,
    )


def validate_definition(definition: Any) -> Graph:
    if not isinstance(definition, dict):
        raise ManagerError("package-definition content must be an object")
    required = {
        "nodes",
        "maxParallel",
        "repository",
        "executionPolicy",
    }
    missing = sorted(required - set(definition))
    if missing:
        raise ManagerError(
            f"package-definition is missing fields: {', '.join(missing)}"
        )
    removed = sorted({"targetBranch", "integrationBranch"} & set(definition))
    if removed:
        raise ManagerError(
            f"package-definition contains removed fields: {', '.join(removed)}"
        )
    parallel = definition["maxParallel"]
    if not isinstance(parallel, int) or isinstance(parallel, bool) or parallel <= 0:
        raise ManagerError("package maxParallel must be a positive integer")
    repository = non_empty_string(definition["repository"], "package repository")
    if not Path(repository).is_absolute():
        raise ManagerError("package repository must be absolute")
    policy = definition["executionPolicy"]
    if not isinstance(policy, dict):
        raise ManagerError("package executionPolicy must be an object")
    lease = policy.get("leaseSeconds")
    if not isinstance(lease, int) or isinstance(lease, bool) or lease <= 0:
        raise ManagerError("executionPolicy leaseSeconds must be positive")
    backoff = policy.get("retryBackoffSeconds")
    if (
        not isinstance(backoff, list)
        or not backoff
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            for value in backoff
        )
    ):
        raise ManagerError(
            "executionPolicy retryBackoffSeconds must contain non-negative numbers"
        )
    for field in ("maxRecoveryAttempts", "maxSupervisorRestarts"):
        value = policy.get(field)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
        ):
            raise ManagerError(f"executionPolicy {field} must be a positive integer")
    return validate_graph(definition["nodes"])


def affected_descendants(nodes: list[dict[str, Any]], affected: set[str]) -> tuple[str, ...]:
    graph = validate_graph(nodes)
    unknown = affected - set(graph.order)
    if unknown:
        raise ManagerError(f"unknown affected nodes: {', '.join(sorted(unknown))}")
    # Rework invalidates every downstream consumer of an affected node, while
    # independent nodes retain their completed evidence.
    selected = set(affected)
    for node_id in affected:
        selected.update(graph.descendants[node_id])
    return tuple(node_id for node_id in graph.order if node_id in selected)


def passing_member_reviews(
    state: dict[str, Any], graph: Graph
) -> dict[str, dict[str, Any]]:
    reviews: dict[str, dict[str, Any]] = {}
    for node_id in graph.order:
        record = state.get("nodes", {}).get(node_id)
        launch = record.get("result") if isinstance(record, dict) else None
        context = launch.get("context") if isinstance(launch, dict) else None
        stages = context.get("stages") if isinstance(context, dict) else None
        review_stage = stages.get("review") if isinstance(stages, dict) else None
        review = (
            review_stage.get("aiReviewResult")
            if isinstance(review_stage, dict)
            else None
        )
        if not isinstance(review, dict):
            raise ManagerError(f"node {node_id} has no AI review result")
        if review.get("result") != "pass" or review.get("checklistResult") != "pass":
            raise ManagerError(f"node {node_id} AI review did not pass")
        reviews[node_id] = review
    return reviews


def resolve_package(value: str | Path, *, must_exist: bool = True) -> Path:
    package = base.resolve_package(value, must_exist=must_exist)
    return package


def items(package: Path, section_id: str) -> Iterable[dict[str, Any]]:
    section = base.load_object(base.section_path(package, section_id), section_id)
    yield from section["content"]
    for subsection in section["subsections"]:
        yield from subsection["content"]


def find_kind(package: Path, section_id: str, kind: str) -> dict[str, Any] | None:
    return next((item for item in items(package, section_id) if item["kind"] == kind), None)


def definition_item(package: Path) -> dict[str, Any]:
    item = find_kind(package, "definition", "package-definition")
    if item is None:
        raise ManagerError("Work Package requires one package-definition")
    return item


def execution_item(package: Path, *, required: bool = False) -> dict[str, Any] | None:
    item = find_kind(package, "execution", "execution-state")
    if item is None and required:
        raise ManagerError("Work Package execution-state is missing")
    return item


base_validate_package = base.validate_package


def validate_package(package_value: str | Path, *, full: bool = False) -> dict[str, Any]:
    result = base_validate_package(package_value, full=full)
    package = resolve_package(package_value)
    metadata = base.load_metadata(package)
    status = metadata["lifecycle"]["status"]
    if status != "draft":
        definition = definition_item(package)["content"]
        graph = validate_definition(definition)
        state_item = execution_item(package, required=True)
        assert state_item is not None
        state = state_item["content"]
        if not isinstance(state, dict):
            raise ManagerError("execution-state content must be an object")
        removed_state = {"mergedOrder", "integrationReceipts"} & set(state)
        if removed_state:
            raise ManagerError(
                "execution-state contains removed integration fields: "
                + ", ".join(sorted(removed_state))
            )
        node_state = state.get("nodes")
        if not isinstance(node_state, dict) or set(node_state) - set(graph.order):
            raise ManagerError("execution-state nodes do not match the package graph")
        if any(
            isinstance(record, dict) and "mergeResult" in record
            for record in node_state.values()
        ):
            raise ManagerError("execution-state node contains removed mergeResult")
        if status in {"review", "done"} and any(
            node_state.get(node_id, {}).get("state") != "completed"
            for node_id in graph.order
        ):
            raise ManagerError(f"{status} Work Package requires every node completed")
    return result


def replace_item(
    package: Path, section_id: str, kind: str, replacement: dict[str, Any]
) -> None:
    path = base.section_path(package, section_id)
    section = base.load_object(path, f"{section_id} section")
    matches = [
        (container, index)
        for container in [section, *section["subsections"]]
        for index, item in enumerate(container["content"])
        if item["kind"] == kind
    ]
    if len(matches) > 1:
        raise ManagerError(f"multiple {kind} items are not allowed")
    if matches:
        container, index = matches[0]
        container["content"][index] = replacement
    else:
        section["content"].append(replacement)
    base.validate_instance("section", section)
    base.commit_transaction(
        package,
        json_writes={
            path: section,
            package / base.METADATA_PATH: base.updated_metadata(package),
        },
    )


def set_status(package: Path, status: str) -> None:
    metadata = base.load_metadata(package)
    current = metadata["lifecycle"]["status"]
    allowed = base.validate_schemas()["metadata"]["x-statusTransitions"][current]
    if status not in allowed:
        raise ManagerError(f"invalid Work Package transition: {current} -> {status}")
    metadata["lifecycle"]["status"] = status
    if status == "ready":
        metadata["readiness"]["definitionComplete"] = True
        metadata["readiness"]["reviewedAt"] = base.now()
        metadata["readiness"]["findings"] = []
    metadata["documentVersion"] = base.next_document_version(
        metadata["documentVersion"]
    )
    metadata["updatedAt"] = base.now()
    base.commit_transaction(
        package, json_writes={package / base.METADATA_PATH: metadata}
    )


def command_transition(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package, full=args.status in {"ready", "review", "done"})
    if args.status == "ready":
        graph = validate_definition(definition_item(package)["content"])
        state = {
            "contractVersion": "1.0.0",
            "revision": 1,
            "state": "ready",
            "invocationId": None,
            "lease": None,
            "nodes": {
                node_id: {"state": "pending", "attempts": 0}
                for node_id in graph.order
            },
            "completedOrder": [],
            "events": [],
            "reviewCount": 0,
        }
        replace_item(
            package,
            "execution",
            "execution-state",
            {"id": "EXECUTION-STATE-001", "kind": "execution-state", "content": state},
        )
    set_status(package, args.status)
    print(json.dumps(validate_package(package, full=True), ensure_ascii=False))


def work_unit_context(work_unit_package: Path) -> dict[str, Any]:
    section_path = work_unit_package / "data" / "sections" / "execution-context.json"
    section = json.loads(section_path.read_text(encoding="utf-8"))
    contexts = [
        item
        for container in [section, *section.get("subsections", [])]
        for item in container["content"]
        if item["kind"] == "execution-context"
    ]
    if len(contexts) != 1 or not isinstance(contexts[0]["content"], dict):
        raise ManagerError(
            f"Work Unit {work_unit_package.name} has invalid execution-context"
        )
    return contexts[0]["content"]


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def preflight(package: Path, repository_arg: str) -> dict[str, Any]:
    validation = validate_package(package, full=True)
    metadata = base.load_metadata(package)
    if metadata["lifecycle"]["status"] not in {"ready", "working", "recovering"}:
        raise ManagerError("Work Package preflight requires ready or active status")
    definition = definition_item(package)["content"]
    graph = validate_definition(definition)
    repository = Path(os.path.abspath(repository_arg))
    if repository != Path(os.path.abspath(definition["repository"])):
        raise ManagerError("Work Package repository mismatch")
    top = git(repository, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != repository.resolve():
        raise ManagerError("Work Package repository is not the primary Git root")
    state = execution_item(package, required=True)["content"]
    initial = metadata["lifecycle"]["status"] == "ready"
    for executable in (WORK_UNIT_MANAGER, WORK_UNIT_LAUNCHER):
        if not executable.is_file():
            raise ManagerError(f"required launcher is unavailable: {executable}")
    members = []
    for node in definition["nodes"]:
        work_unit = (
            repository / ".agent-factory" / "work-units" / node["workUnitId"]
        )
        result = subprocess.run(
            [sys.executable, str(WORK_UNIT_MANAGER), "validate", str(work_unit), "--full"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise ManagerError(
                f"Work Unit {node['workUnitId']} is not full-valid: {result.stderr.strip()}"
            )
        member_validation = json.loads(result.stdout)
        if initial and member_validation["status"] != "ready":
            raise ManagerError(
                f"Work Unit {node['workUnitId']} is not ready"
            )
        context = work_unit_context(work_unit)
        if Path(os.path.abspath(context["repository"])) != repository:
            raise ManagerError(
                f"Work Unit {node['workUnitId']} repository mismatch"
            )
        recorded_mode = context.get("executionMode")
        declared_mode = node.get("executionMode")
        if declared_mode != recorded_mode:
            raise ManagerError(
                f"Work Unit {node['workUnitId']} executionMode mismatch"
            )
        members.append(
            {
                "nodeId": node["id"],
                "workUnitId": node["workUnitId"],
                "executionMode": recorded_mode,
            }
        )
    return {
        "valid": validation["valid"],
        "packageId": package.name,
        "revision": state["revision"],
        "resume": not initial,
        "order": list(graph.order),
        "initialReadyNodes": [
            node_id
            for node_id in graph.initial_ready
            if state["nodes"].get(node_id, {}).get("state") != "completed"
        ],
        "members": members,
    }


def command_preflight(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            preflight(resolve_package(args.package), args.repository),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def command_execution_start(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    result = preflight(package, args.repository)
    state_item = execution_item(package, required=True)
    assert state_item is not None
    state = copy.deepcopy(state_item["content"])
    if (
        state.get("invocationId") is not None
        and state["invocationId"] != args.invocation_id
    ):
        lease_owner = (
            state.get("lease", {}).get("owner")
            if isinstance(state.get("lease"), dict)
            else None
        )
        if args.resume_owner != lease_owner:
            raise ManagerError(
                "execution-start resume owner does not match the durable lease"
            )
        state.setdefault("resumeInvocations", []).append(args.invocation_id)
    else:
        state["invocationId"] = args.invocation_id
    state["state"] = "working"
    state["lease"] = {
        "owner": args.invocation_id,
        "renewedAt": base.now(),
        "leaseSeconds": definition_item(package)["content"]["executionPolicy"][
            "leaseSeconds"
        ],
    }
    state.setdefault("events", []).append(
        {
            "sequence": len(state.get("events", [])) + 1,
            "type": "ack",
            "at": base.now(),
            "invocationId": args.invocation_id,
        }
    )
    state_item["content"] = state
    replace_item(package, "execution", "execution-state", state_item)
    status = base.load_metadata(package)["lifecycle"]["status"]
    if status == "ready":
        set_status(package, "working")
    elif status == "recovering":
        set_status(package, "working")
    result.update(
        {
            "invocationId": args.invocation_id,
            "acceptedAt": base.now(),
            "schedulerState": state["state"],
        }
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


def command_state_put(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    current = execution_item(package, required=True)
    assert current is not None
    state = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ManagerError("durable state file must contain an object")
    if state.get("revision") != current["content"].get("revision"):
        raise ManagerError("durable state revision mismatch")
    lease = state.get("lease")
    if not isinstance(lease, dict) or lease.get("owner") != args.invocation_id:
        raise ManagerError("durable state lease owner mismatch")
    current["content"] = state
    replace_item(package, "execution", "execution-state", current)
    desired = state.get("state")
    status = base.load_metadata(package)["lifecycle"]["status"]
    if desired in {"working", "recovering"} and desired != status:
        set_status(package, desired)
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_review_put(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    status = base.load_metadata(package)["lifecycle"]["status"]
    if status not in {"working", "recovering"}:
        raise ManagerError("review-put requires an active Work Package")
    state_item = execution_item(package, required=True)
    assert state_item is not None
    state = copy.deepcopy(state_item["content"])
    graph = validate_definition(definition_item(package)["content"])
    if any(
        state["nodes"].get(node_id, {}).get("state") != "completed"
        for node_id in graph.order
    ):
        raise ManagerError("review-put requires every package node completed")
    if state.get("reviewCount", 0) != 0:
        raise ManagerError("Work Package review may be recorded only once per revision")
    evidence = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise ManagerError("review evidence must be a JSON object")
    review_result = evidence.get("result")
    checklist_result = evidence.get("checklistResult")
    if review_result != "pass" or checklist_result != "pass":
        raise ManagerError(
            "review-put requires passing result and checklistResult evidence"
        )
    member_reviews = passing_member_reviews(state, graph)
    if evidence.get("memberReviews") != member_reviews:
        raise ManagerError(
            "review-put memberReviews must match passing canonical node results"
        )
    state["state"] = "review"
    state["reviewCount"] = 1
    state["reviewEvidence"] = evidence
    state_item["content"] = state
    replace_item(package, "execution", "execution-state", state_item)
    replace_item(
        package,
        "ai-review",
        "ai-review-result",
        {
            "id": "AI-REVIEW-STATUS",
            "kind": "ai-review-result",
            "content": {
                "result": review_result,
                "reviewedAt": base.now(),
                "checks": evidence.get("aiChecks", []),
            },
            "attributes": {
                "result": review_result,
                "checklistResult": checklist_result,
            },
        },
    )
    replace_item(
        package,
        "report",
        "report-result",
        {
            "id": "REPORT-STATUS",
            "kind": "report-result",
            "content": {
                "verificationResult": checklist_result,
                "memberTraceability": [
                    {
                        "nodeId": node_id,
                        "workUnitId": next(
                            node["workUnitId"]
                            for node in definition_item(package)["content"]["nodes"]
                            if node["id"] == node_id
                        ),
                        "idempotencyKey": state["nodes"][node_id].get(
                            "idempotencyKey"
                        ),
                        "result": state["nodes"][node_id].get("result"),
                    }
                    for node_id in graph.order
                ],
                "evidence": evidence,
            },
            "attributes": {"verificationResult": checklist_result},
        },
    )
    set_status(package, "review")
    print(json.dumps(validate_package(package, full=True), ensure_ascii=False))


def command_complete(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    if base.load_metadata(package)["lifecycle"]["status"] != "review":
        raise ManagerError("complete requires a Work Package in review")
    ai_review = find_kind(package, "ai-review", "ai-review-result")
    review_attributes = (
        ai_review.get("attributes") if isinstance(ai_review, dict) else None
    )
    if not isinstance(review_attributes, dict) or (
        review_attributes.get("result") != "pass"
        or review_attributes.get("checklistResult") != "pass"
    ):
        raise ManagerError("complete requires a passing Work Package AI review")
    if args.review_decision != "complete":
        raise ManagerError("complete requires Human review decision complete")
    state_item = execution_item(package, required=True)
    assert state_item is not None
    state = copy.deepcopy(state_item["content"])
    state["state"] = "done"
    state_item["content"] = state
    replace_item(package, "execution", "execution-state", state_item)
    replace_item(
        package,
        "human-review",
        "human-review-result",
        {
            "id": "HUMAN-REVIEW-STATUS",
            "kind": "human-review-result",
            "content": {
                "decision": "complete",
                "decidedAt": base.now(),
            },
            "attributes": {"status": "complete"},
        },
    )
    set_status(package, "done")
    print(json.dumps(validate_package(package, full=True), ensure_ascii=False))


def command_rework_start(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    if base.load_metadata(package)["lifecycle"]["status"] != "review":
        raise ManagerError("rework-start requires a Work Package in review")
    definition = definition_item(package)["content"]
    selected = affected_descendants(
        definition["nodes"], set(args.affected_node)
    )
    project_root = package.parent.parent.parent
    selected_nodes = [
        node for node in definition["nodes"] if node["id"] in selected
    ]
    member_packages = [
        project_root / ".agent-factory" / "work-units" / node["workUnitId"]
        for node in selected_nodes
    ]
    for member in member_packages:
        validation = subprocess.run(
            [sys.executable, str(WORK_UNIT_MANAGER), "validate", str(member), "--full"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if validation.returncode != 0:
            raise ManagerError(
                f"affected Work Unit {member.name} is invalid: {validation.stderr.strip()}"
            )
        if json.loads(validation.stdout).get("status") != "review":
            raise ManagerError(
                f"affected Work Unit {member.name} must be in review for rework"
            )
    for member in member_packages:
        rework = subprocess.run(
            [
                sys.executable,
                str(WORK_UNIT_MANAGER),
                "rework-start",
                str(member),
                "--instruction",
                (
                    f"Work Package {package.name} affected-node rework: "
                    f"{args.instruction}"
                ),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if rework.returncode != 0:
            raise ManagerError(
                f"cannot start affected Work Unit {member.name} rework: "
                f"{rework.stderr.strip()}"
            )
    state_item = execution_item(package, required=True)
    assert state_item is not None
    state = copy.deepcopy(state_item["content"])
    state["revision"] += 1
    state["state"] = "working"
    state["invocationId"] = None
    state["lease"] = None
    state["affectedNodes"] = list(selected)
    for node_id in selected:
        state["nodes"][node_id] = {"state": "pending", "attempts": 0}
    state["completedOrder"] = [
        node_id for node_id in state.get("completedOrder", []) if node_id not in selected
    ]
    state.setdefault("events", []).append(
        {
            "sequence": len(state.get("events", [])) + 1,
            "type": "rework",
            "at": base.now(),
            "affectedNodes": list(selected),
            "instruction": args.instruction,
        }
    )
    state_item["content"] = state
    replace_item(package, "execution", "execution-state", state_item)
    set_status(package, "working")
    print(json.dumps({"revision": state["revision"], "affectedNodes": list(selected)}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Manage canonical Agent Factory Work Package DAGs"
    )
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-schemas")
    check.set_defaults(handler=base.command_check_schemas)
    create = commands.add_parser("create")
    create.add_argument("package")
    create.add_argument("--id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--project-id", required=True)
    create.add_argument("--language", default="ko")
    create.add_argument("--theme", required=True)
    create.set_defaults(handler=base.command_create)
    show = commands.add_parser("show")
    show.add_argument("package")
    show.add_argument("--section")
    show.set_defaults(handler=base.command_show)
    title = commands.add_parser("title-set")
    title.add_argument("package")
    title.add_argument("title")
    title.set_defaults(handler=base.command_title_set)
    metadata = commands.add_parser("metadata-set")
    metadata.add_argument("package")
    metadata.add_argument("field")
    base.add_data_arguments(metadata)
    metadata.set_defaults(handler=base.command_metadata_set)
    validate = commands.add_parser("validate")
    validate.add_argument("package")
    validate.add_argument("--full", action="store_true")
    validate.set_defaults(handler=base.command_validate)
    for name, handler in (
        ("section-put", base.command_section_put),
        ("section-item-put", base.command_section_item_put),
        ("section-items-put", base.command_section_items_put),
    ):
        command = commands.add_parser(name)
        command.add_argument("package")
        if name != "section-put":
            command.add_argument("section_id")
        base.add_data_arguments(command)
        if name != "section-put":
            command.add_argument("--subsection")
        command.set_defaults(handler=handler)
    block_put = commands.add_parser("block-put")
    block_put.add_argument("package")
    block_put.add_argument("source")
    block_put.add_argument("--path", required=True)
    block_put.add_argument("--media-type", required=True)
    block_put.add_argument("--description", required=True)
    block_put.set_defaults(handler=base.command_block_put)
    block_remove = commands.add_parser("block-remove")
    block_remove.add_argument("package")
    block_remove.add_argument("path")
    block_remove.set_defaults(handler=base.command_block_remove)
    transition = commands.add_parser("transition")
    transition.add_argument(
        "package"
    )
    transition.add_argument("status", choices=["ready", "review", "done"])
    transition.set_defaults(handler=command_transition)
    preflight_command = commands.add_parser("preflight")
    preflight_command.add_argument("package")
    preflight_command.add_argument("--repository", required=True)
    preflight_command.set_defaults(handler=command_preflight)
    start = commands.add_parser("execution-start")
    start.add_argument("package")
    start.add_argument("--repository", required=True)
    start.add_argument("--invocation-id", required=True)
    start.add_argument("--resume-owner")
    start.set_defaults(handler=command_execution_start)
    state_put = commands.add_parser("state-put")
    state_put.add_argument("package")
    state_put.add_argument("--file", required=True)
    state_put.add_argument("--invocation-id", required=True)
    state_put.set_defaults(handler=command_state_put)
    review_put = commands.add_parser("review-put")
    review_put.add_argument("package")
    review_put.add_argument("--evidence-file", required=True)
    review_put.set_defaults(handler=command_review_put)
    complete = commands.add_parser("complete")
    complete.add_argument("package")
    complete.add_argument(
        "--review-decision", required=True, choices=["complete"]
    )
    complete.set_defaults(handler=command_complete)
    rework = commands.add_parser("rework-start")
    rework.add_argument("package")
    rework.add_argument("--affected-node", action="append", required=True)
    rework.add_argument("--instruction", required=True)
    rework.set_defaults(handler=command_rework_start)
    return root


base.validate_package = validate_package


def main() -> int:
    try:
        args = parser().parse_args()
        if hasattr(args, "package"):
            package = resolve_package(
                args.package, must_exist=args.command != "create"
            )
            if package.exists():
                base.recover_transaction(package)
        args.handler(args)
        return 0
    except ManagerError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
