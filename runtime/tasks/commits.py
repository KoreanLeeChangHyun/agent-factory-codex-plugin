"""Main's receipt-bound ordinary local commit; no arbitrary Git argv or hook bypass."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

from contracts.receipts import validate_receipt
from storage.errors import ContractError
from storage.files import file_lock, safe_read_json
from storage import paths as runtime_paths
from storage.lessons import operational_path
from tasks.orchestrator_guard import has_symlink


def fail(message):
    raise ContractError("commit_scope_invalid", message)


def git(repository, *arguments):
    # Inherited index/config overrides must not select another index, hook policy or repository.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_LITERAL_PATHSPECS"] = "1"
    result = subprocess.run(["git", "-C", str(repository), *arguments], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    if result.returncode:
        raise ContractError("commit_git_failed", result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def lesson_removals(repository):
    """Already staged index-only removals are the migration, never record content."""
    names = git(repository, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=D", "-z")
    return {os.fsdecode(name) for name in names.split(b"\0") if name and operational_path(os.fsdecode(name))}


def evidence(root, main_state, proposal):
    """Completion belongs to the selected route, not a newly invented Verification gate."""
    work_path = Path(proposal["workStatePath"])
    if has_symlink(work_path):
        fail("Unsafe Work evidence path")
    work = safe_read_json(work_path)
    if work.get("statePath") != str(work_path) or work.get("role") != "work" or work.get("status") != "completed":
        fail("Use a completed Work result")
    if work.get("parentAgentId") != main_state["agentId"]:
        fail("Work evidence belongs to another Main")
    if work.get("taskWorkspace", {}).get("mode") == "code":
        fail("Code Work Unit integration remains runtime-owned")
    receipt = validate_receipt(root, work, agent_id=work["agentId"], run_id=work["runId"])
    if receipt["outcome"] != "completed":
        fail("Work receipt is incomplete")
    loop = None
    if proposal.get("loopStatePath"):
        loop_path = Path(proposal["loopStatePath"])
        if has_symlink(loop_path):
            fail("Unsafe loop evidence path")
        loop = safe_read_json(loop_path)
        expected = Path(runtime_paths.resolve(root)["agentsRoot"]) / work["agentId"] / "loops" / loop.get("loopId", "") / "state.json"
        if (loop_path != expected or loop.get("statePath") != str(expected) or loop.get("status") != "completed"
                or loop.get("workAgentId") != work["agentId"] or loop.get("latestWorkRunId") != work["runId"]):
            fail("Loop evidence must complete this exact Work run")
    mode = work.get("taskMode", "work-verification")
    if mode in {"work-verification", "plan-work-verification"}:
        verification_path = proposal.get("verificationStatePath")
        skip = (loop or {}).get("humanSkip") or {}
        if verification_path:
            if has_symlink(verification_path):
                fail("Unsafe Verification evidence path")
            verification = safe_read_json(Path(verification_path))
            if (verification.get("statePath") != verification_path or verification.get("status") != "completed"
                    or verification.get("role") != "verification"):
                fail("Verification did not complete")
            verified = validate_receipt(root, verification, agent_id=verification["agentId"], run_id=verification["runId"])
            if verified.get("verifiedWorkRunId") != work["runId"] or verified.get("decision") != "pass":
                fail("Verification does not pass this exact Work run")
        elif not (skip.get("actor") == "human" and skip.get("authorizationReference")
                  and skip.get("decisionEvidence") and skip.get("recordedAt")):
            fail("This route requires its bound Verification evidence or recorded Human skip")
    if work.get("workProfile") == "scribe":
        review = (loop or {}).get("draftReview") or {}
        if (review.get("status") != "accepted" or review.get("workRunId") != work["runId"]
                or not review.get("authorizationReference") or not review.get("decisionEvidence")):
            fail("Scribe draft requires the recorded Human acceptance")
    return receipt


def validate(root, main_state, proposal):
    if main_state.get("role") != "main" or main_state.get("roleBoundaryPolicy") != 1:
        fail("Only Main owns ordinary commits")
    required = {"repository", "branch", "head", "paths", "contentHashes", "diffHash", "message",
                "workStatePath", "authority"}
    if not isinstance(proposal, dict) or not required.issubset(proposal) or set(proposal) - required - {
            "verificationStatePath", "loopStatePath"}:
        fail("Provide the exact commit manifest; arbitrary Git options are forbidden")
    authority = proposal["authority"]
    if (not isinstance(authority, dict) or authority.get("decision") != "approved"
            or any(not isinstance(authority.get(key), str) or not authority[key].strip()
                   for key in ("source", "time", "scope"))):
        fail("Record actual Human commit authority, time and scope; a proposal is not approval")
    repository = Path(proposal["repository"])
    if (not repository.is_absolute() or has_symlink(repository) or repository.resolve() != repository
            or not repository.is_relative_to(root)):
        fail("Select a canonical repository inside the project")
    if Path(git(repository, "rev-parse", "--show-toplevel").decode().strip()) != repository:
        fail("Select the exact repository root")
    sandbox = main_state.get("executionPolicy", {}).get("sandboxPolicy", {})
    if sandbox.get("type") == "read-only" or (sandbox.get("type") == "workspace-write" and not any(
            repository.is_relative_to(Path(value)) for value in sandbox.get("writable_roots", []))):
        fail("Commit cannot widen the captured execution permissions")
    receipt = evidence(root, main_state, proposal)
    paths = proposal["paths"]
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
        fail("Select exact receipt-bound files")
    removals = lesson_removals(repository) if any(operational_path(p) for p in paths) else set()
    for value in paths:
        if (not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts
                or str(Path(value)) != value or "\\" in value or ".git" in Path(value).parts
                or has_symlink(repository / value) or (repository / value).is_dir()):
            fail("Unsafe commit file path")
        if operational_path(value) and value not in removals:
            fail("Operational lesson records are local data; only staged index removals may be committed")
        project_path = str((repository / value).relative_to(root))
        if project_path not in receipt["changedPaths"]:
            fail("Commit path is not in the completed Work receipt")
    if not isinstance(proposal["message"], str) or not proposal["message"].strip():
        fail("Provide a commit message")
    if set(proposal["contentHashes"]) != set(paths):
        fail("Capture every approved file hash (null for an authorized removed file)")
    return repository


def check_changes(repository, proposal, *, staged=False):
    if git(repository, "symbolic-ref", "--short", "HEAD").decode().strip() != proposal["branch"]:
        fail("Branch changed")
    if git(repository, "rev-parse", "HEAD").decode().strip() != proposal["head"]:
        fail("HEAD changed")
    # Any pending merge/rebase/cherry-pick is outside ordinary commit authority.
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        target = Path(git(repository, "rev-parse", "--git-path", name).decode().strip())
        if (target if target.is_absolute() else repository / target).exists():
            fail("History operation or conflict is pending")
    if git(repository, "ls-files", "-u", "-z"):
        fail("Resolve code conflicts through assigned Work")
    removals = lesson_removals(repository) if any(operational_path(p) for p in proposal["paths"]) else set()
    for value, expected in proposal["contentHashes"].items():
        path = repository / value
        if has_symlink(path) or path.is_dir():
            fail("File type changed")
        # An authorized untracking keeps the local body. Its commit contains only a
        # deletion, so later recording must not invalidate the migration manifest.
        actual = None if value in removals else hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual != expected:
            fail("Approved file content changed")
    # Untracked additions appear in `git diff HEAD` only after staging. Keep the approved
    # diff stable across that transition; every added file is already bound by contentHashes.
    tracked = set(git(repository, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", *proposal["paths"])
                  .decode().rstrip("\0").split("\0")) - {""}
    existing = [path for path in proposal["paths"] if path in tracked]
    diff = git(repository, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--", *existing) if existing else b""
    if hashlib.sha256(diff).hexdigest() != proposal["diffHash"]:
        fail("Approved diff changed")
    index = set(git(repository, "diff", "--cached", "--name-only", "-z").decode().rstrip("\0").split("\0")) - {""}
    if index - set(proposal["paths"]):
        fail("Unrelated staged changes must remain untouched")
    if staged:
        if index != set(proposal["paths"]):
            fail("Index does not match the exact approved set")
        if git(repository, "diff", "--name-only", "--", *proposal["paths"]):
            fail("Approved files changed after staging")
    elif index and git(repository, "diff", "--name-only", "--", *sorted(index)):
        fail("Existing staged content differs from the exact approved working files")


def execute(root, main_state, proposal, *, apply=False):
    repository = validate(root, main_state, proposal)
    common = Path(git(repository, "rev-parse", "--git-common-dir").decode().strip())
    common = common if common.is_absolute() else repository / common
    # Same lock as managed integration/cleanup; no new directory or separate coordination system.
    with file_lock(common / ".agent-factory-integration.lock", blocking=False):
        check_changes(repository, proposal)
        if not apply:
            return {"status": "ready", "repository": str(repository), "paths": proposal["paths"]}
        additions = [path for path in proposal["paths"] if not operational_path(path)]
        if additions:
            git(repository, "add", "--", *additions)
        check_changes(repository, proposal, staged=True)
        # Hooks run normally. A failure leaves the exact staged set for Main to report; never reset it.
        git(repository, "commit", "-m", proposal["message"])
        return {"status": "committed", "repository": str(repository),
                "commit": git(repository, "rev-parse", "HEAD").decode().strip(), "paths": proposal["paths"]}


def bound_main(config):
    path = config.get("captureStatePath")
    if not path or has_symlink(path):
        fail("Use this tool from a bound Main run")
    state = safe_read_json(Path(path))
    if state.get("role") != "main" or state.get("statePath") != path:
        fail("Main run binding is invalid")
    runtime_paths.bind(state["runtimeBinding"])
    return Path(state["runtimeBinding"]["projectRoot"]), state
