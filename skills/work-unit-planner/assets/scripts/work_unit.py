#!/usr/bin/env python3
"""Manage sectioned Agent Factory Work Unit packages."""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent.parent
COMMON_MANAGER = SKILL_ROOT.parent / "lifecycle" / "assets" / "scripts" / "sectioned_document.py"
COMMON_SCHEMA_ROOT = SKILL_ROOT.parent / "lifecycle" / "assets" / "schema" / "sectioned-document"


def load_base_manager() -> Any:
    spec = importlib.util.spec_from_file_location("agent_factory_sectioned_document", COMMON_MANAGER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sectioned document manager: {COMMON_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_base_manager()
ManagerError = base.ManagerError

# Configure the lifecycle-owned package engine with the Work Unit contracts,
# then replace artifact-specific semantic hooks.
base.configure_contract(
    skill_root=SKILL_ROOT,
    profile_path=SKILL_ROOT / "assets" / "profiles" / "work-unit.profile.json",
    metadata_schema_path=SKILL_ROOT / "assets" / "schema" / "metadata.schema.json",
    structural_schema_root=COMMON_SCHEMA_ROOT,
    artifact_type="work-unit",
    artifact_label="Work Unit",
    package_collection="work-units",
    lock_collection="work-units",
    lifecycle_phase="work-unit",
    initial_status="backlog",
    initial_readiness={
        "contractValid": True,
        "intakeTraceabilityValid": False,
        "definitionComplete": False,
        "executionContextComplete": False,
        "verificationPlanComplete": False,
        "reviewedAt": None,
        "findings": [],
    },
    generated_by="Agent Factory work-unit manager",
)


def profile() -> dict[str, Any]:
    raw = base.load_object(base.PROFILE_PATH, "Work Unit profile")
    normalized = dict(raw)
    normalized["requiredSections"] = [
        *raw.get("commonRequiredSections", []),
        *raw.get("profileRequiredSections", []),
    ]
    return normalized


def validate_schemas() -> dict[str, dict[str, Any]]:
    contracts = base.schemas()
    for contract in contracts.values():
        base.Draft202012Validator.check_schema(contract)
    current = profile()
    if current.get("artifactType") != "work-unit":
        raise ManagerError("Work Unit profile artifactType must be work-unit")
    if current.get("maximumSectionDepth") != 2:
        raise ManagerError("Work Unit profile maximumSectionDepth must be 2")
    version = contracts["metadata"]["properties"]["schemaVersion"]["const"]
    if current.get("version") != version:
        raise ManagerError("Work Unit profile version must match metadata schemaVersion")
    required = [entry["id"] for entry in current["requiredSections"]]
    optional = [entry["id"] for entry in current.get("optionalSections", [])]
    if not required or len(required) != len(set(required)):
        raise ManagerError("Work Unit required section ids must be non-empty and unique")
    if set(required) & set(optional) or len(optional) != len(set(optional)):
        raise ManagerError("Work Unit optional section ids must be unique and disjoint")
    return contracts


def package_project_root(package: Path) -> Path:
    if package.parent.name != "work-units" or package.parent.parent.name != ".agent-factory":
        raise ManagerError("package must be <project-root>/.agent-factory/work-units/<work-unit-id>")
    return package.parent.parent.parent.resolve()


def resolve_package(value: str | Path, *, must_exist: bool = True) -> Path:
    requested = Path(value)
    if requested.is_symlink():
        raise ManagerError(f"canonical package must not be a symlink: {requested}")
    package = Path(os.path.abspath(requested))
    package_project_root(package)
    if must_exist:
        base.assert_plain_path(package, "directory")
    return package


@contextmanager
def package_lock(package: Path, timeout: float = 10.0) -> Iterable[None]:
    lock_root = package_project_root(package) / ".agent-factory" / "runtime" / "locks" / "work-units"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_path = lock_root / f"{package.name}.lock"
    with lock_path.open("a+b") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ManagerError(f"timed out waiting for Work Unit package lock: {package.name}")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def iter_items(section: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield from section["content"]
    for subsection in section["subsections"]:
        yield from subsection["content"]


def validate_anchor(project_root: Path, reference: dict[str, Any], target: Path) -> None:
    if not target.is_dir() or not (target / "data" / "metadata.json").is_file():
        raise ManagerError("typed reference anchor path must target a sectioned package root")
    metadata = base.load_object(target / "data" / "metadata.json", "referenced metadata")
    if metadata.get("artifactType") != reference["artifactType"] or metadata.get("id") != reference["id"]:
        raise ManagerError("typed reference identity does not match referenced package metadata")
    toc = base.load_object(target / "data" / "table-of-contents.json", "referenced table of contents")
    if toc.get("sha256") != base.toc_digest(toc.get("sections", [])):
        raise ManagerError("typed reference target table of contents integrity check failed")
    anchor = reference["anchor"]
    entry = next((item for item in toc["sections"] if item.get("id") == anchor["sectionId"]), None)
    if entry is None:
        raise ManagerError("typed reference anchor section does not exist")
    expected = f"data/sections/{anchor['sectionId']}.json"
    if entry.get("path") != expected:
        raise ManagerError("typed reference anchor section path is not canonical")
    section_path = target / expected
    base.assert_plain_path(section_path, "file")
    section = base.load_object(section_path, "referenced section")
    if section.get("id") != anchor["sectionId"] or base.toc_entry(section) != entry:
        raise ManagerError("typed reference anchor section does not match table of contents")
    if not any(item.get("id") == anchor["itemId"] for item in iter_items(section)):
        raise ManagerError("typed reference anchor item does not exist")


def validate_typed_paths(package: Path, metadata: dict[str, Any], summaries: list[dict[str, Any]]) -> None:
    project_root = package_project_root(package)
    references: list[dict[str, Any]] = list(metadata["provenance"]["sourceRefs"])
    references.extend(relation["target"] for relation in metadata["relations"])
    for summary in summaries:
        references.extend(summary["typedRefs"])
    for reference in references:
        relative = base.safe_relative_path(reference["path"], "typed reference path")
        target = project_root / relative
        try:
            target.resolve(strict=False).relative_to(project_root)
        except ValueError as error:
            raise ManagerError(f"typed reference escapes project root: {relative}") from error
        if not target.exists():
            raise ManagerError(f"typed reference does not exist: {relative}")
        if "anchor" in reference:
            validate_anchor(project_root, reference, target)


def validate_profile(metadata: dict[str, Any], summaries: list[dict[str, Any]]) -> None:
    ids = [summary["id"] for summary in summaries]
    required = [entry["id"] for entry in profile()["requiredSections"]]
    if len(ids) != len(set(ids)):
        raise ManagerError("section ids must be unique")
    positions = [ids.index(section_id) for section_id in required if section_id in ids]
    if len(positions) != len(required) or positions != sorted(positions):
        raise ManagerError("required sections must exist exactly once in profile order")
    allowed = set(required) | {entry["id"] for entry in profile().get("optionalSections", [])}
    unknown = [section_id for section_id in ids if section_id not in allowed]
    if unknown:
        raise ManagerError(f"sections are not declared by the Work Unit profile: {', '.join(unknown)}")
    hierarchy_ids = [item_id for summary in summaries for item_id in summary["hierarchyIds"]]
    if len(hierarchy_ids) != len(set(hierarchy_ids)):
        raise ManagerError("section and subsection ids must be unique across the Work Unit")
    blockers = base.unresolved_blockers(summaries)
    status = metadata["lifecycle"]["status"]
    if status == "blocked" and not blockers:
        raise ManagerError("blocked Work Unit requires an unresolved blocking open item")
    if status != "ready":
        return
    readiness = metadata["readiness"]
    keys = (
        "contractValid",
        "intakeTraceabilityValid",
        "definitionComplete",
        "executionContextComplete",
        "verificationPlanComplete",
    )
    failed = [key for key in keys if not readiness[key]]
    if failed:
        raise ManagerError(f"ready Work Unit has failed readiness flags: {', '.join(failed)}")
    if readiness["reviewedAt"] is None:
        raise ManagerError("ready Work Unit requires readiness.reviewedAt")
    if blockers:
        raise ManagerError(f"ready Work Unit has unresolved blocking open items: {', '.join(blockers)}")
    by_id = {summary["id"]: summary for summary in summaries}
    for rule in profile()["requiredSections"]:
        missing = [kind for kind in rule.get("requiredKinds", []) if kind not in by_id[rule["id"]]["kinds"]]
        if missing:
            raise ManagerError(
                f"ready Work Unit section {rule['id']} is missing required content kinds: {', '.join(missing)}"
            )


def find_kind(package: Path, kind: str) -> dict[str, Any] | None:
    for section in base.load_sections(package):
        for item in iter_items(section):
            if item["kind"] == kind:
                return item
    return None


def registered_blocks(package: Path) -> set[str]:
    index = base.load_object(package / base.BLOCK_INDEX_PATH, "block index")
    return {entry["path"] for entry in index["blocks"]}


def require_evidence(package: Path, item: dict[str, Any], label: str) -> None:
    evidence = item.get("attributes", {}).get("evidence", [])
    if not evidence:
        raise ManagerError(f"review transition requires {label} evidence")
    missing = [reference for reference in evidence if reference not in registered_blocks(package)]
    if missing:
        raise ManagerError(f"review transition references unregistered evidence: {', '.join(missing)}")


def validate_ready_semantics(package: Path) -> None:
    context = find_kind(package, "execution-context")
    if context is None or not isinstance(context.get("content"), dict):
        raise ManagerError("ready Work Unit requires an execution context object")
    required = {
        "goalId", "objective", "execInvocation", "executionAgent", "repository",
        "baseRef", "branch", "worktreePath",
    }
    missing = sorted(required - set(context["content"]))
    if missing:
        raise ManagerError(f"execution context is missing fields: {', '.join(missing)}")
    expected_branch = f"work-unit/{package.name}"
    if context["content"]["branch"] != expected_branch:
        raise ManagerError(f"execution context branch must equal {expected_branch}")
    invocation = context["content"]["execInvocation"]
    if not isinstance(invocation, str) or not invocation.strip():
        raise ManagerError("execution context execInvocation must be a non-empty string")
    try:
        invocation_parts = shlex.split(invocation)
    except ValueError as error:
        raise ManagerError(f"execution context execInvocation is not valid shell syntax: {error}") from error
    if invocation_parts[:1] == ["codex"] and "exec" in invocation_parts:
        exec_index = invocation_parts.index("exec")
        approval_options = {
            index
            for index, part in enumerate(invocation_parts)
            if part == "--ask-for-approval" or part.startswith("--ask-for-approval=")
        }
        if any(index > exec_index for index in approval_options):
            raise ManagerError(
                "Codex global option --ask-for-approval must appear before the exec subcommand"
            )
    basis = find_kind(package, "intake-basis-ref")
    references = [] if basis is None else basis.get("sourceRefs", [])
    valid = [
        reference for reference in references
        if reference.get("artifactType") == "intake"
        and reference.get("anchor", {}).get("sectionId") == "work-unit-basis"
    ]
    if not valid:
        raise ManagerError("ready Work Unit requires an anchored Intake work-unit-basis reference")
    project_root = package_project_root(package)
    for reference in valid:
        target = project_root / base.safe_relative_path(reference["path"], "Intake basis path")
        source_metadata = base.load_object(target / "data" / "metadata.json", "Intake metadata")
        if source_metadata.get("lifecycle", {}).get("status") != "ready":
            raise ManagerError("ready Work Unit basis must reference a ready Intake")


def validate_review_semantics(package: Path) -> None:
    execution = find_kind(package, "execution-result")
    attributes = {} if execution is None else execution.get("attributes", {})
    if attributes.get("status") != "complete" or attributes.get("verificationResult") != "pass":
        raise ManagerError("review transition requires passing execution and verification results")
    quality = find_kind(package, "quality-check")
    if quality is None or quality.get("attributes", {}).get("status") != "pass":
        raise ManagerError("review transition requires passing quality checks")
    require_evidence(package, quality, "quality-check")
    ai_review = find_kind(package, "ai-review-result")
    ai = {} if ai_review is None else ai_review.get("attributes", {})
    if ai.get("result") != "pass" or ai.get("checklistResult") != "pass":
        raise ManagerError("review transition requires a passing AI review and checklist")
    report = find_kind(package, "report-result")
    if report is None or report.get("attributes", {}).get("verificationResult") != "pass":
        raise ManagerError("review transition requires a passing report verification result")
    require_evidence(package, report, "report")


base_validate_package = base.validate_package


def validate_package(package_value: str | Path, *, full: bool = False) -> dict[str, Any]:
    result = base_validate_package(package_value, full=full)
    package = resolve_package(package_value)
    metadata = base.load_metadata(package)
    status = metadata["lifecycle"]["status"]
    if status == "ready":
        validate_ready_semantics(package)
    if status in {"review", "done"}:
        validate_review_semantics(package)
    return result


def command_create(args: argparse.Namespace) -> None:
    package = resolve_package(args.package, must_exist=False)
    if package.name != args.id:
        raise ManagerError("--id must match the package directory name")
    if package.exists():
        raise ManagerError(f"package already exists: {package}")
    package.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{args.id}.", dir=package.parent))
    staging_package = staging_root / ".agent-factory" / "work-units" / args.id
    timestamp = base.now()
    sections = [
        {"id": entry["id"], "title": entry["title"], "content": [], "subsections": []}
        for entry in profile()["requiredSections"]
    ]
    metadata = {
        "schemaVersion": profile()["version"],
        "documentVersion": "1.0.0",
        "id": args.id,
        "artifactType": "work-unit",
        "projectId": args.project_id,
        "lifecycle": {"phase": "work-unit", "status": "backlog"},
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "language": args.language,
        "theme": args.theme,
        "provenance": {
            "createdBy": "Human",
            "generatedBy": "Agent Factory work-unit manager",
            "sourceRefs": [],
        },
        "relations": [],
        "readiness": {
            "contractValid": True,
            "intakeTraceabilityValid": False,
            "definitionComplete": False,
            "executionContextComplete": False,
            "verificationPlanComplete": False,
            "reviewedAt": None,
            "findings": [],
        },
    }
    try:
        (staging_package / base.SECTIONS_PATH).mkdir(parents=True)
        (staging_package / "blocks").mkdir()
        base.write_json_atomically(staging_package / base.METADATA_PATH, metadata)
        base.write_json_atomically(staging_package / base.TITLE_PATH, {"title": args.title})
        for section in sections:
            base.write_json_atomically(base.section_path(staging_package, section["id"]), section)
        base.write_json_atomically(staging_package / base.TOC_PATH, base.new_toc(sections))
        base.write_json_atomically(staging_package / base.BLOCK_INDEX_PATH, {"blocks": []})
        validate_package(staging_package)
        os.rename(staging_package, package)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_transition(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    metadata = base.load_metadata(package)
    current = metadata["lifecycle"]["status"]
    allowed = validate_schemas()["metadata"]["x-statusTransitions"][current]
    if args.status not in allowed:
        raise ManagerError(f"invalid Work Unit transition: {current} -> {args.status}")
    if args.status == "done" and args.human_review != "approved":
        raise ManagerError("transition to done requires --human-review approved")
    if args.status != "done" and args.human_review is not None:
        raise ManagerError("--human-review is only allowed for a transition to done")
    metadata["lifecycle"]["status"] = args.status
    metadata["documentVersion"] = base.next_document_version(metadata["documentVersion"])
    metadata["updatedAt"] = base.now()
    metadata["readiness"]["contractValid"] = True
    writes: dict[Path, Any] = {package / base.METADATA_PATH: metadata}
    if args.status == "done":
        section_path = base.section_path(package, "human-review")
        section = base.load_object(section_path, "human-review section")
        result = next((item for item in iter_items(section) if item["kind"] == "human-review-result"), None)
        if result is None:
            raise ManagerError("done Work Unit requires a human-review-result")
        result.setdefault("attributes", {})["status"] = "approved"
        result["attributes"]["approvedAt"] = base.now()
        writes[section_path] = section
    base.validate_instance("metadata", metadata)
    base.validate_profile(metadata, base.summarize_sections(package, base.load_toc(package)))
    if args.status == "ready":
        validate_ready_semantics(package)
    if args.status == "review":
        validate_review_semantics(package)
    base.commit_transaction(package, json_writes=writes, full_validation=args.status in {"ready", "review", "done"})
    print(json.dumps(validate_package(package, full=args.status in {"ready", "review", "done"}), ensure_ascii=False))


# Install Work Unit-specific globals into the shared implementation.
base.profile = profile
base.validate_schemas = validate_schemas
base.package_project_root = package_project_root
base.resolve_package = resolve_package
base.package_lock = package_lock
base.validate_typed_paths = validate_typed_paths
base.validate_profile = validate_profile
base.validate_package = validate_package


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Manage sectioned Agent Factory Work Unit packages")
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
    create.set_defaults(handler=command_create)
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
    metadata.add_argument("value", nargs="?")
    metadata.add_argument("--value-file")
    metadata.set_defaults(handler=base.command_metadata_set)
    section_put = commands.add_parser("section-put")
    section_put.add_argument("package")
    section_put.add_argument("value", nargs="?")
    section_put.add_argument("--value-file")
    section_put.set_defaults(handler=base.command_section_put)
    item_put = commands.add_parser("section-item-put")
    item_put.add_argument("package")
    item_put.add_argument("section_id")
    item_put.add_argument("value", nargs="?")
    item_put.add_argument("--value-file")
    item_put.add_argument("--subsection")
    item_put.set_defaults(handler=base.command_section_item_put)
    items_put = commands.add_parser("section-items-put")
    items_put.add_argument("package")
    items_put.add_argument("section_id")
    items_put.add_argument("value", nargs="?")
    items_put.add_argument("--value-file")
    items_put.add_argument("--subsection")
    items_put.set_defaults(handler=base.command_section_items_put)
    section_add = commands.add_parser("section-add")
    section_add.add_argument("package")
    section_add.add_argument("value", nargs="?")
    section_add.add_argument("--value-file")
    add_position = section_add.add_mutually_exclusive_group()
    add_position.add_argument("--before")
    add_position.add_argument("--after")
    section_add.set_defaults(handler=base.command_section_add)
    section_move = commands.add_parser("section-move")
    section_move.add_argument("package")
    section_move.add_argument("section_id")
    move_position = section_move.add_mutually_exclusive_group(required=True)
    move_position.add_argument("--before")
    move_position.add_argument("--after")
    section_move.set_defaults(handler=base.command_section_move)
    section_remove = commands.add_parser("section-remove")
    section_remove.add_argument("package")
    section_remove.add_argument("section_id")
    section_remove.set_defaults(handler=base.command_section_remove)
    validate = commands.add_parser("validate")
    validate.add_argument("package")
    validate.add_argument("--full", action="store_true")
    validate.set_defaults(handler=base.command_validate)
    transition = commands.add_parser("transition")
    transition.add_argument("package")
    transition.add_argument("status", choices=["backlog", "ready", "working", "review", "done", "blocked"])
    transition.add_argument("--human-review", choices=["approved"])
    transition.set_defaults(handler=command_transition)
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
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if not hasattr(args, "package"):
            args.handler(args)
            return 0
        package = resolve_package(args.package, must_exist=args.command != "create")
        with package_lock(package):
            if package.exists():
                base.recover_transaction(package)
            args.handler(args)
        return 0
    except ManagerError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
