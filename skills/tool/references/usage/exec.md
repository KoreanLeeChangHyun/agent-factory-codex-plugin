# `exec.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `init`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `location`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `projects`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `rebind`
Required: `--from-root FROM_ROOT`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `map-path`
Required: `--path PATH`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `doctor`: Inspect host sandbox prerequisites; use doctor --help for options
No options.

## `announce-tasks`: Prepare one Main-owned task list for presentation and dispatch
Required: `--task-list-file TASK_LIST_FILE`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `submit`
Required: `--agent AGENT`, `--role ROLE`
One of: `--request-file` | `--message` | `--input-file`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--task-workspace-file TASK_WORKSPACE_FILE`: Runtime-owned task Work Unit binding captured by loop.py
- `--task-list-file TASK_LIST_FILE`
- `--task-id TASK_ID`
- `--document-context-file DOCUMENT_CONTEXT_FILE`: Explicit per-request document query, scope, required sources and selections JSON; does not grant authority
- `--request-file REQUEST_FILE`
- `--message MESSAGE`
- `--input-file INPUT_FILE`: versioned agent-input JSON with sibling, file-backed images
- `--actor {main,human}`
- `--human-approval-policy {required,bypass}`: Main delegation approval policy; omitted sends preserve the session policy
- `--task-mode {orchestrate,direct,work,plan,verification,plan-work,work-verification,plan-work-verification}`: Captured execution route; new Main requests default to orchestrate
- `--work-profile {work,workLight,explore,scribe}`: Work profile Main chose (work = Expert, workLight = Worker, explore = Explorer, scribe = Scribe); selects no model; explore writes exact task-bound evidence Documents and scribe writes only inside docs/
- `--model MODEL`
- `--provider {codex,claude,antigravity}`
- `--reasoning-effort {none,minimal,low,medium,high,xhigh,max,ultra}`
- `--agent-permissions AGENT_PERMISSIONS`: Captured Human-selected role permission overrides as JSON
- `--work-isolation {on,off}`: Captured Human-selected Work isolation toggle; on requires AI-chosen task Work Units for delegated Work
- `--fast | --no-fast`
- `--goal-mode | --no-goal-mode`
- `--goal-objective GOAL_OBJECTIVE`: Native persisted nonempty objective; omitted on send preserves the existing objective
- `--receipt-request-hash RECEIPT_REQUEST_HASH`: SHA-256 identity the role receipt must bind (defaults to this run request)
- `--response-contract {1,2}`: Work response contract: 1 = the Agent writes receipt.json, 2 = receipt fields in the structured final output (default where the provider attaches the schema to the final turn)
- `--verified-work-run-id VERIFIED_WORK_RUN_ID`: exact Work run checked by a Verification Agent (required for Verification runs)
- `--dispatch-id DISPATCH_ID`: optional idempotency key: dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}; generated when omitted; reuse the same key only for recovery of the same request
- `--capability-binding-file CAPABILITY_BINDING_FILE`: strict Agent capability/authority/effects binding to preserve in this run
- `--codex CODEX`
- `--claude CLAUDE`
- `--agy AGY`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`
- `--heartbeat-interval HEARTBEAT_INTERVAL`
- `--heartbeat-timeout HEARTBEAT_TIMEOUT`
- `--start-timeout START_TIMEOUT`
- `--turn-timeout TURN_TIMEOUT`
- `--max-attempts MAX_ATTEMPTS`

## `send`
Required: `--agent AGENT`
One of: `--request-file` | `--message` | `--input-file`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--task-workspace-file TASK_WORKSPACE_FILE`: Runtime-owned task Work Unit binding captured by loop.py
- `--task-list-file TASK_LIST_FILE`
- `--task-id TASK_ID`
- `--document-context-file DOCUMENT_CONTEXT_FILE`: Explicit per-request document query, scope, required sources and selections JSON; does not grant authority
- `--request-file REQUEST_FILE`
- `--message MESSAGE`
- `--input-file INPUT_FILE`: versioned agent-input JSON with sibling, file-backed images
- `--actor {main,human}`
- `--human-approval-policy {required,bypass}`: Main delegation approval policy; omitted sends preserve the session policy
- `--task-mode {orchestrate,direct,work,plan,verification,plan-work,work-verification,plan-work-verification}`: Captured execution route; new Main requests default to orchestrate
- `--work-profile {work,workLight,explore,scribe}`: Work profile Main chose (work = Expert, workLight = Worker, explore = Explorer, scribe = Scribe); selects no model; explore writes exact task-bound evidence Documents and scribe writes only inside docs/
- `--model MODEL`
- `--provider {codex,claude,antigravity}`
- `--reasoning-effort {none,minimal,low,medium,high,xhigh,max,ultra}`
- `--agent-permissions AGENT_PERMISSIONS`: Captured Human-selected role permission overrides as JSON
- `--work-isolation {on,off}`: Captured Human-selected Work isolation toggle; on requires AI-chosen task Work Units for delegated Work
- `--fast | --no-fast`
- `--goal-mode | --no-goal-mode`
- `--goal-objective GOAL_OBJECTIVE`: Native persisted nonempty objective; omitted on send preserves the existing objective
- `--receipt-request-hash RECEIPT_REQUEST_HASH`: SHA-256 identity the role receipt must bind (defaults to this run request)
- `--response-contract {1,2}`: Work response contract: 1 = the Agent writes receipt.json, 2 = receipt fields in the structured final output (default where the provider attaches the schema to the final turn)
- `--verified-work-run-id VERIFIED_WORK_RUN_ID`: exact Work run checked by a Verification Agent (required for Verification runs)
- `--dispatch-id DISPATCH_ID`: optional idempotency key: dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}; generated when omitted; reuse the same key only for recovery of the same request
- `--capability-binding-file CAPABILITY_BINDING_FILE`: strict Agent capability/authority/effects binding to preserve in this run
- `--codex CODEX`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`

## `status`
Required: `--agent AGENT`
One of: `--run-id` | `--dispatch-id`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--run-id RUN_ID`
- `--dispatch-id DISPATCH_ID`
- `--document {state,request,result,receipt,capability,loop}`: Read a document as lossless Unicode text pages (default page: 4000 characters)
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed

## `result`
Required: `--agent AGENT`, `--run-id RUN_ID`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--ack`

## `cancel`
Required: `--agent AGENT`, `--run-id RUN_ID`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `capabilities`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--codex CODEX`
- `--claude CLAUDE`
- `--agy AGY`
- `--provider {codex,claude,antigravity}`
- `--model MODEL`
- `--agent AGENT`

## `measure`: Compare same-input orchestration observations without launching models
Required: `--input INPUT`

## `goal`
Required: `--agent AGENT`, `action {get,refresh,pause,cancel,clear,disable,resume,reopen}`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `worktree`: Manage a conversation's isolated Git worktree
Required: `--agent AGENT`, `action {status,create,merge,repositories}`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--changes {reject,keep,copy}`
- `--path PATH`
- `--repository REPOSITORY`
- `--name NAME`
- `--branch BRANCH`
- `--base BASE`
- `--target TARGET`
- `--codex CODEX`
- `--claude CLAUDE`
- `--agy AGY`
- `--model MODEL`
- `--human-approval-policy {required,bypass}`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`

## `list`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed

## `reset-conversation`: Start a fresh provider conversation while preserving the Agent and run history
Required: `--agent AGENT`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `delete-task`: Physically delete one ended task's private runtime history
Required: `--main-agent MAIN_AGENT`, `--workflow-id WORKFLOW_ID`, `--task-id TASK_ID`, `--actor {human}`, `--authorization-reference AUTHORIZATION_REFERENCE`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `delete-agent`: Permanently delete one inactive Main agent's private runtime records
Required: `--agent AGENT`, `--actor {human}`, `--authorization-reference AUTHORIZATION_REFERENCE`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `inbox`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--agent AGENT`
- `--ack`

## `reconcile`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--agent AGENT`
