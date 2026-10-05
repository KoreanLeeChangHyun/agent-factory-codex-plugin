"""Run and session records: creation, lookup and parent binding."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from typing import Iterator


def create_run(
    runtime,
    *,
    project_root: Path,
    agent_id: str,
    actor: str,
    request: bytes,
    session: dict[str, Any],
    receipt_request_hash: str | None = None,
    verified_work_run_id: str | None = None,
    dispatch_id: str | None = None,
    dispatch_operation: str | None = None,
    requested_codex: str | None = None,
    capability_bindings: bytes | None = None,
    execution_options: dict[str, Any] | None = None,
    work_profile: str | None = None,
    goal_action: str | None = None,
    images: list[dict[str, Any]] | None = None,
    parent_agent_id: str | None = None,
    parent_run_id: str | None = None,
    task_binding: dict[str, Any] | None = None,
    task_workspace_id: str | None = None,
    response_contract: int | None = None,
) -> dict[str, Any]:
    run_id = runtime.new_run_id()
    directory = runtime.run_directory(project_root, agent_id, run_id, create=True)
    request_path = directory / "request.md"
    result_path = directory / "result.md"
    events_path = directory / "events.jsonl"
    heartbeat_path = directory / "heartbeat.json"
    response_schema = directory / "response.schema.json"
    receipt_path = directory / "receipt.json"
    receipt_schema = directory / "receipt.schema.json"
    capability_binding_path = directory / "capability-bindings.json"
    request_hash = hashlib.sha256(request).hexdigest()
    runtime.atomic_write(request_path, request)
    image_inputs = []
    for index, image in enumerate(images or []):
        image_path = directory / "images" / f"{index:02d}{image['suffix']}"
        runtime.atomic_write(image_path, image["content"])
        image_inputs.append({
            "path": str(image_path), "mediaType": image["mediaType"],
            "size": len(image["content"]),
            "sha256": hashlib.sha256(image["content"]).hexdigest(),
        })
    capability_binding_hash = None
    capability_binding_document = None
    if capability_bindings is not None:
        capability_binding_document = runtime.validate_capability_bindings(json.loads(capability_bindings))
        runtime.atomic_write(capability_binding_path, capability_bindings)
        capability_binding_hash = hashlib.sha256(capability_bindings).hexdigest()
    role = str(session["role"])
    structured_receipt = structured_receipt_run(
        runtime, session, execution_options, goal_action,
        bound=capability_bindings is not None, requested=response_contract)
    runtime.atomic_write_json(
        response_schema, runtime.response_schema_document(str(result_path), receipt=structured_receipt))
    if role in {"work", "verification"}:
        runtime.atomic_write_json(
            receipt_schema,
            runtime.receipt_schema_document(
                role=role,
                run_id=run_id,
                request_hash=receipt_request_hash or request_hash,
                verified_work_run_id=verified_work_run_id,
                capability_bindings=capability_binding_document,
                standalone=(execution_options or {}).get("taskMode") == "verification",
            ),
        )
    accepted_at = runtime.now()
    state = {
        "provider": session.get("provider", "codex"),
        "runtimeBinding": runtime.runtime_paths.resolve(project_root, create=True),
        "workingDirectory": str(runtime.worktrees.checked_path(session)) if "projectRoot" in session else str(project_root),
        "schemaVersion": runtime.SCHEMA_VERSION,
        "runId": run_id,
        "agentId": agent_id,
        "role": session["role"],
        "actor": actor,
        "status": "accepted",
        "attempt": 0,
        "startDisposition": "not-started",
        "maxAttempts": session["maxAttempts"],
        "requestPath": str(request_path),
        "requestHash": request_hash,
        "statePath": str(directory / "state.json"),
        "resultPath": str(result_path),
        "eventsPath": str(events_path),
        "heartbeatPath": str(heartbeat_path),
        "responseSchemaPath": str(response_schema),
        "acceptedAt": accepted_at,
        "updatedAt": accepted_at,
        "workerPid": None,
        "workerIdentity": None,
        "containmentAttempt": 0,
        "containment": None,
        "containmentLaunchDisposition": "not-launched",
        "codexPid": None,
        "codexIdentity": None,
        "lastCodexIdentity": None,
        "cancelRequested": False,
        "unread": False,
        "error": None,
    }
    if isinstance(session.get("conversationId"), str):
        state["conversationId"] = session["conversationId"]
    if session.get("taskWorkspace"):
        state["taskWorkspace"] = session["taskWorkspace"]
    if role == "main":
        state["taskAnnouncementContract"] = 1
    if structured_receipt:
        # Captured once: this run finishes under the contract it started with.
        state["responseContract"] = runtime.receipt_contracts.STRUCTURED_RESPONSE_CONTRACT
    if parent_agent_id is not None and parent_run_id is not None:
        state["parentAgentId"] = parent_agent_id
        state["parentRunId"] = parent_run_id
    if task_binding is not None:
        state["taskBinding"] = task_binding
    state["taskMode"] = (execution_options or {}).get("taskMode", "direct" if role == "main" else "work-verification")
    if image_inputs:
        state["imageInputs"] = image_inputs
    if execution_options:
        state["executionOptions"] = execution_options
    if work_profile is not None:
        state["workProfile"] = work_profile
    state["humanApprovalPolicy"] = session.get("humanApprovalPolicy", "required")
    if "executionPolicy" in session:
        state["executionPolicy"] = session["executionPolicy"]
    if goal_action:
        state["goalAction"] = goal_action
    if dispatch_id is not None:
        state["dispatchId"] = dispatch_id
        state["dispatchTuple"] = {
            "agentId": agent_id,
            "role": role,
            "actor": actor,
            "requestHash": request_hash,
            "receiptRequestHash": receipt_request_hash or request_hash,
            "verifiedWorkRunId": verified_work_run_id,
            "operation": dispatch_operation,
        }
        if requested_codex is not None:
            state["dispatchTuple"]["requestedCodex"] = requested_codex
        if task_binding is not None:
            state["dispatchTuple"]["taskBinding"] = task_binding
        if task_workspace_id is not None:
            # Part of the immutable dispatch identity exec deduplicates and loop reconciles against.
            state["dispatchTuple"]["taskWorkspaceId"] = task_workspace_id
        if parent_agent_id is not None and parent_run_id is not None:
            state["dispatchTuple"].update({
                "parentAgentId": parent_agent_id,
                "parentRunId": parent_run_id,
            })
        if "executionPolicy" in session:
            state["dispatchTuple"]["executionPolicy"] = session["executionPolicy"]
        state["dispatchTuple"]["humanApprovalPolicy"] = state["humanApprovalPolicy"]
        if execution_options:
            state["dispatchTuple"]["executionOptions"] = execution_options
        if work_profile is not None:
            state["dispatchTuple"]["workProfile"] = work_profile
        if goal_action:
            state["dispatchTuple"]["goalAction"] = goal_action
        if capability_binding_hash is not None:
            state["dispatchTuple"]["capabilityBindingHash"] = capability_binding_hash
    if role in {"work", "verification"}:
        state.update(
            {
                "receiptPath": str(receipt_path),
                "receiptSchemaPath": str(receipt_schema),
                "receiptRequestHash": receipt_request_hash or request_hash,
            }
        )
    if role == "verification":
        state["verifiedWorkRunId"] = verified_work_run_id
    if capability_binding_hash is not None:
        state.update({
            "capabilityBindingPath": str(capability_binding_path),
            "capabilityBindingHash": capability_binding_hash,
        })
    runtime.atomic_write_json(directory / "state.json", state)
    runtime.atomic_write_json(
        heartbeat_path,
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "runId": run_id,
            "attempt": 0,
            "sequence": 0,
            "status": "accepted",
            "workerPid": None,
            "codexPid": None,
            "observedAt": accepted_at,
        },
    )
    if parent_agent_id is not None and parent_run_id is not None:
        # One atomic projection per child avoids rewriting a growing parent index.
        reference_path = runtime.run_directory(project_root, parent_agent_id, parent_run_id) / "children" / f"{agent_id}.json"
        runtime.atomic_write_json(reference_path, {"agentId": agent_id, "runId": run_id,
            "parentAgentId": parent_agent_id, "parentRunId": parent_run_id, "role": role})
    return state


def structured_receipt_run(runtime, session, execution_options, goal_action, *, bound, requested) -> bool:
    """Whether a new run returns its Work receipt in the structured final output (response contract 2).

    The file contract stays for a caller that captured it (`requested`), for plan-only Work
    (the host records that receipt), for capability-bound runs (their outcomes carry fixed
    bindings) and where the provider cannot attach the response schema to the final turn."""
    contracts = runtime.receipt_contracts
    if requested is not None and requested not in contracts.RESPONSE_CONTRACTS:
        raise runtime.ContractError("response_contract_invalid", "Response contract version is unsupported")
    options = execution_options or {}
    if (session.get("role") != "work" or requested == contracts.FILE_RESPONSE_CONTRACT or bound
            or options.get("taskMode") == "plan"):
        return False
    effective = {**session, **{key: options[key] for key in ("goalMode",) if key in options}}
    return runtime.adapters.for_session(session).final_output_schema(effective, goal_action) is True


def create_session(runtime, args: argparse.Namespace, project_root: Path) -> dict[str, Any]:
    directory = runtime.agent_directory(project_root, args.agent, create=True)
    path = directory / "session.json"
    if path.exists():
        raise runtime.ContractError("agent_exists", "Agent already exists; use send")
    role = runtime.validate_id(args.role, runtime.ROLE_ID, "role")
    runtime.role_path(role)
    if not hasattr(args, "resolved_execution_policy"):
        args.resolved_execution_policy = runtime.resolve_execution_policy(args, project_root)
    provider = runtime.adapters.provider_for(args.model, getattr(args, "provider", None) or getattr(args, "inherited_provider", None))
    provider_adapter = runtime.adapters.adapter(provider)
    codex = provider_adapter.executable(args)
    if os.sep not in codex:
        from shutil import which

        resolved = which(codex) or runtime.portable.find_cli(codex)
        if resolved is None:
            raise runtime.ContractError(f"{provider}_not_found", f"{provider} executable was not found")
        codex = resolved
    else:
        codex = str(Path(codex).resolve(strict=True))
    codex = runtime.portable.native_executable(codex, provider)
    options = runtime.requested_execution(args)
    capabilities = runtime.adapters.adapter(provider).inspect_capabilities(codex, refresh=True, runtime_home=runtime.runtime_paths.resolve(project_root, create=True)["home"])
    # Claude and Antigravity have no Fast tier; the option is a no-op there. Goal must be supported by every provider.
    checked = (("goalMode", "goal"),) if provider in ("claude", "antigravity") else (("fast", "fast"), ("goalMode", "goal"))
    for key, field in checked:
        if options.get(key) is True and not capabilities["submit"][field]:
            raise runtime.ContractError("native_unsupported", capabilities["diagnostic"] or f"Native {field} unsupported")
    created_at = runtime.now()
    session = {
        **provider_adapter.session_fields(codex, capabilities),
        "provider": provider,
        "schemaVersion": runtime.SCHEMA_VERSION,
        "agentId": args.agent,
        "role": role,
        "sessionId": None,
        "projectRoot": str(project_root),
        "runtimeBinding": runtime.runtime_paths.resolve(project_root, create=True),
        # Retain the historical executable field for persisted-session compatibility.
        "codex": provider_adapter.session_fields(codex, capabilities).get("codex", args.codex),
        "sandbox": args.resolved_execution_policy["sandboxPolicy"]["type"],
        "executionPolicy": args.resolved_execution_policy,
        "humanApprovalPolicy": getattr(args, "resolved_human_approval_policy", "required"),
        "model": args.model,
        "reasoningEffort": getattr(args, "reasoning_effort", None),
        "heartbeatInterval": args.heartbeat_interval,
        "heartbeatTimeout": args.heartbeat_timeout,
        "startTimeout": args.start_timeout,
        "turnTimeout": args.turn_timeout,
        "maxAttempts": args.max_attempts,
        "createdAt": created_at,
        "updatedAt": created_at,
    }
    runtime.atomic_write_json(path, session)
    return session


def load_session(runtime, project_root: Path, agent_id: str) -> dict[str, Any]:
    path = runtime.session_file(project_root, agent_id)
    session = runtime.safe_read_json(path)
    if session.get("agentId") != agent_id or session.get("projectRoot") != str(project_root):
        raise runtime.ContractError("session_invalid", "Agent session binding is invalid")
    session_id = session.get("sessionId")
    if session_id is not None and (
        not isinstance(session_id, str) or not runtime.SESSION_ID.fullmatch(session_id)
    ):
        raise runtime.ContractError("session_invalid", "Codex session identifier is invalid")
    runtime.role_path(str(session.get("role", "")))
    return session


def managed_parent_identity(runtime, project_root: Path) -> dict[str, str] | None:
    locator = os.environ.get("AGENT_FACTORY_PARENT_STATE")
    if not locator:
        return None
    state_path = Path(locator)
    try:
        state = runtime.safe_read_json(state_path)
    except ValueError as error:
        # Storage validates persisted bindings before the parent fields are available.
        raise runtime.ContractError("parent_session_invalid", f"Managed parent run binding could not be validated: {error}") from error
    binding = state.get("runtimeBinding")
    agent_id, run_id = state.get("agentId"), state.get("runId")
    if (not isinstance(binding, dict) or binding.get("projectRoot") != str(project_root)
            or not isinstance(agent_id, str) or not runtime.AGENT_ID.fullmatch(agent_id)
            or not isinstance(run_id, str) or not runtime.AGENT_ID.fullmatch(run_id)
            or state_path != runtime.agent_directory(project_root, agent_id) / "runs" / run_id / "state.json"):
        raise runtime.ContractError("parent_session_invalid", "Managed parent run binding is invalid")
    return {"agentId": agent_id, "runId": run_id}


def require_current_parent_conversation(runtime, project_root: Path, parent: dict[str, str]) -> None:
    state = runtime.safe_read_json(runtime.state_file(project_root, parent["agentId"], parent["runId"]))
    session = runtime.load_session(project_root, parent["agentId"])
    if state.get("conversationId") != session.get("conversationId"):
        raise runtime.ContractError("parent_conversation_reset", "The parent conversation was reset before the child run was accepted")


def validate_state_containment_fields(runtime, state: dict[str, Any]) -> None:
    fields = {"containmentAttempt", "containment", "containmentLaunchDisposition"}
    present = fields.intersection(state)
    if not present:
        return
    if present != fields:
        raise runtime.ContractError("containment_state_invalid", "containment state fields are incomplete")
    attempt = state.get("containmentAttempt")
    disposition = state.get("containmentLaunchDisposition")
    if not isinstance(attempt, int) or attempt < 0 or disposition not in {
        "not-launched", "launching", "launched"
    }:
        raise runtime.ContractError("containment_state_invalid", "containment state fields are invalid")
    containment = state.get("containment")
    if containment is None:
        if attempt != 0 or disposition != "not-launched":
            raise runtime.ContractError("containment_identity_unbound", "launched containment identity is not bound")
        return
    runtime.validate_containment(containment)
    if attempt < 1 or disposition == "not-launched":
        raise runtime.ContractError("containment_state_invalid", "containment launch state is invalid")


def _validate_state_containment(runtime, state: dict[str, Any]) -> dict[str, Any]:
    runtime.validate_state_containment_fields(state)
    containment = runtime.validate_containment(state.get("containment"))
    if containment["kind"] == "systemd-user-service":
        attempt = state.get("containmentAttempt")
        if not isinstance(attempt, int) or attempt < 1 or containment["unitName"] != runtime.systemd_unit_name(
            str(state.get("agentId")), str(state.get("runId")), attempt
        ):
            raise runtime.ContractError("containment_identity_mismatch", "systemd unit is not bound to this run attempt")
    elif containment["identity"] != state.get("workerIdentity"):
        raise runtime.ContractError("containment_identity_mismatch", "fallback containment is not bound to this worker")
    return containment


def find_run(runtime, project_root: Path, agent_id: str, run_id: str) -> dict[str, Any]:
    path = runtime.state_file(project_root, agent_id, run_id)
    state = runtime.safe_read_json(path)
    if state.get("agentId") != agent_id or state.get("runId") != run_id:
        raise runtime.ContractError("state_invalid", "run identity does not match its managed directory")
    for field, name in {"statePath": "state.json", "requestPath": "request.md", "resultPath": "result.md",
                        "eventsPath": "events.jsonl", "heartbeatPath": "heartbeat.json",
                        "responseSchemaPath": "response.schema.json", "receiptPath": "receipt.json",
                        "receiptSchemaPath": "receipt.schema.json", "capabilityBindingPath": "capability-bindings.json"}.items():
        if state.get(field) is not None and state[field] != str(path.parent / name):
            raise runtime.ContractError("state_invalid", "run file path escaped its managed binding")
    return state


def iter_agent_directories(runtime, root: Path) -> Iterator[Path]:
    if not runtime.runtime_paths.resolve(root)["registered"]:
        return
    agents = runtime.agent_root(root, create=False)
    if not agents.exists():
        return
    runtime.reject_symlink(agents)
    for item in sorted(agents.iterdir(), key=lambda path: path.name):
        if runtime.AGENT_ID.fullmatch(item.name) and item.is_dir() and not item.is_symlink():
            yield item


def iter_run_states(runtime, root: Path, selected_agent: str | None = None) -> Iterator[dict[str, Any]]:
    for directory in runtime.iter_agent_directories(root):
        if selected_agent is not None and directory.name != selected_agent:
            continue
        runs = directory / "runs"
        if not runs.exists() or runs.is_symlink():
            continue
        for item in sorted(runs.iterdir(), key=lambda path: path.name):
            if item.is_dir() and not item.is_symlink():
                with contextlib.suppress(runtime.ContractError):
                    yield runtime.safe_read_json(item / "state.json")
