"""Resolve requested execution options and policies from command arguments."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def resolve_execution_policy(runtime, args: argparse.Namespace, project_root: Path, session: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        if session is not None and session.get("role") in ("work", "verification") and os.environ.get("AGENT_FACTORY_PARENT_STATE"):
            parent_state = runtime.safe_read_json(Path(os.environ["AGENT_FACTORY_PARENT_STATE"]))
            session = runtime.worktrees.inherit(session, {"projectRoot": str(project_root), **runtime.load_session(project_root, parent_state["agentId"])})
        stored = runtime.execution_policy.session_policy(session) if session is not None and "executionPolicy" in session else None
        policy_args = argparse.Namespace(**vars(args))
        policy_args.provider = runtime.adapters.provider_for(getattr(args, "model", None), getattr(args, "provider", None) or getattr(args, "inherited_provider", None), session)
        if session is not None:
            policy_args.execution_working_directory = str(runtime.worktrees.checked_path({"projectRoot": str(project_root), **session}))
        elif getattr(args, "role", None) in ("work", "verification") and os.environ.get("AGENT_FACTORY_PARENT_STATE"):
            parent_state = runtime.safe_read_json(Path(os.environ["AGENT_FACTORY_PARENT_STATE"]))
            policy_args.execution_working_directory = parent_state.get("workingDirectory", str(project_root))
        if session is not None:
            policy_args.role = session.get("role")
        if session is not None and session.get("codex"):
            policy_args.codex = getattr(args, "codex", None) or session["codex"]
        policy = runtime.execution_policy.resolve(policy_args, project_root, fallback_policy=stored, allow_session_change=session is not None)
        if stored is not None and policy != stored and not runtime.execution_policy.has_explicit_policy(args):
            raise runtime.ContractError("execution_policy_mismatch", "Changing an idle session policy requires a complete explicit policy")
        if session is not None and stored is None and session.get("sandbox") != policy["sandboxPolicy"]["type"] and not runtime.execution_policy.has_explicit_policy(args):
            raise runtime.ContractError("execution_policy_mismatch", "Legacy session sandbox differs from current authorized policy")
        return policy
    except (ValueError, OSError) as error:
        raise runtime.ContractError("execution_policy_invalid", str(error)) from error


def resolve_human_approval_policy(runtime, args: argparse.Namespace, session: dict[str, Any] | None = None) -> str:
    requested = getattr(args, "human_approval_policy", None)
    locator = os.environ.get(runtime.execution_policy.PARENT_STATE_ENV)
    role = session.get("role") if session is not None else getattr(args, "role", None)
    if locator and role in ("work", "verification"):
        parent = runtime.safe_read_json(Path(locator))
        snapshot = json.loads(os.environ.get(runtime.execution_policy.SNAPSHOT_ENV, "null"))
        runtime.execution_policy._managed_parent(snapshot, parent.get("runtimeBinding", {}).get("projectRoot"))
        mode = parent.get("executionOptions", {}).get("agentPermissions", {}).get(role)
        if mode is not None and mode != "cli-default":
            expected = "bypass" if mode == "bypass" else "required"
            if requested is not None and requested != expected:
                raise runtime.ContractError("execution_policy_mismatch", "Human approval policy differs from captured role permissions")
            requested = expected
    stored = session.get("humanApprovalPolicy", "required") if session is not None else "required"
    if stored not in runtime.HUMAN_APPROVAL_POLICIES:
        raise runtime.ContractError("human_approval_policy_invalid", "Stored Human approval policy is invalid")
    return requested if requested is not None else stored


def requested_execution(runtime, args: argparse.Namespace) -> dict[str, Any]:
    options = {}
    if getattr(args, "provider", None) is not None:
        options["provider"] = args.provider
    for argument, key in (("task_mode", "taskMode"), ("model", "model"), ("reasoning_effort", "reasoningEffort"), ("fast", "fast"), ("goal_mode", "goalMode"), ("goal_objective", "goalObjective")):
        value = getattr(args, argument, None)
        if value is not None:
            options[key] = value
    captured = getattr(args, "agent_permissions", None)
    if captured is not None:
        try:
            roles = json.loads(captured)
            if not isinstance(roles, dict) or any(role not in ("main", "work", "verification") or mode not in ("cli-default", "workspace-write", "danger-full-access", "bypass") for role, mode in roles.items()):
                raise ValueError("Invalid role permissions")
            # A child cannot mint new permission authority for its descendants.
            if os.environ.get(runtime.execution_policy.PARENT_STATE_ENV):
                raise ValueError("Role permission authority must originate at the Human-facing host")
        except (ValueError, TypeError) as error:
            raise runtime.ContractError("agent_permissions_invalid", str(error)) from error
        options["agentPermissions"] = roles
    objective = options.get("goalObjective")
    if objective is not None:
        if not isinstance(objective, str) or not objective.strip():
            raise runtime.ContractError("goal_objective_invalid", "Goal objective must be nonempty")
        if options.get("goalMode") is False:
            raise runtime.ContractError("goal_objective_invalid", "An objective cannot be combined with --no-goal-mode")
        options["goalMode"] = True
    return options


def inherited_provider(runtime, args: argparse.Namespace) -> str | None:
    """A new delegated Agent without a provider or model runs on its managed parent's provider."""
    locator = os.environ.get(runtime.execution_policy.PARENT_STATE_ENV)
    if not locator or getattr(args, "provider", None) or getattr(args, "model", None):
        return None
    try:
        parent = runtime.safe_read_json(Path(locator))
        binding = parent.get("runtimeBinding", {})
        session = runtime.safe_read_json(Path(binding["agentsRoot"]) / parent["agentId"] / "session.json")
    except (runtime.ContractError, KeyError, TypeError, OSError, ValueError):
        return None
    provider = session.get("provider")
    return provider if isinstance(provider, str) else None
