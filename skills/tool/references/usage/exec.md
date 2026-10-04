# `exec.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `init`

## `location`

## `projects`

## `rebind`
Required: `--from-root FROM_ROOT`

## `map-path`
Required: `--path PATH`

## `doctor`: Inspect host sandbox prerequisites; use doctor --help for options
No options.

## `announce-tasks`: Prepare one Main-owned task list for presentation and dispatch
Required: `--task-list-file TASK_LIST_FILE`

## `submit`
Required: `--agent AGENT`, `--role ROLE`
One of: `--request-file` | `--message` | `--input-file`
- `--task-list-file TASK_LIST_FILE`
- `--task-id TASK_ID`
- `--request-file REQUEST_FILE`
- `--message MESSAGE`
- `--input-file INPUT_FILE`: versioned agent-input JSON with sibling, file-backed images
- `--actor {main,human}`
- `--human-approval-policy {required,bypass}`: Main delegation approval policy; omitted sends preserve the session policy
- `--task-mode {orchestrate,direct,work,plan,verification,plan-work,work-verification,plan-work-verification}`: Captured execution route; new Main requests default to orchestrate
- `--work-profile {work,workLight}`: Work profile label Main chose (work = Expert, workLight = Worker); recorded for display only, selects no model or authority
- `--model MODEL`
- `--provider {codex,claude,antigravity}`
- `--reasoning-effort {none,minimal,low,medium,high,xhigh,max,ultra}`
- `--agent-permissions AGENT_PERMISSIONS`: Captured Human-selected role permission overrides as JSON
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
- `--task-list-file TASK_LIST_FILE`
- `--task-id TASK_ID`
- `--request-file REQUEST_FILE`
- `--message MESSAGE`
- `--input-file INPUT_FILE`: versioned agent-input JSON with sibling, file-backed images
- `--actor {main,human}`
- `--human-approval-policy {required,bypass}`: Main delegation approval policy; omitted sends preserve the session policy
- `--task-mode {orchestrate,direct,work,plan,verification,plan-work,work-verification,plan-work-verification}`: Captured execution route; new Main requests default to orchestrate
- `--work-profile {work,workLight}`: Work profile label Main chose (work = Expert, workLight = Worker); recorded for display only, selects no model or authority
- `--model MODEL`
- `--provider {codex,claude,antigravity}`
- `--reasoning-effort {none,minimal,low,medium,high,xhigh,max,ultra}`
- `--agent-permissions AGENT_PERMISSIONS`: Captured Human-selected role permission overrides as JSON
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
- `--run-id RUN_ID`
- `--dispatch-id DISPATCH_ID`

## `result`
Required: `--agent AGENT`, `--run-id RUN_ID`
- `--ack`

## `cancel`
Required: `--agent AGENT`, `--run-id RUN_ID`

## `capabilities`
- `--codex CODEX`
- `--claude CLAUDE`
- `--agy AGY`
- `--provider {codex,claude,antigravity}`
- `--model MODEL`
- `--agent AGENT`

## `goal`
Required: `--agent AGENT`, `action {get,refresh,pause,cancel,clear,disable,resume,reopen}`

## `worktree`: Manage a conversation's isolated Git worktree
Required: `--agent AGENT`, `action {status,create,merge,repositories}`
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

## `reset-conversation`: Start a fresh provider conversation while preserving the Agent and run history
Required: `--agent AGENT`

## `inbox`
- `--agent AGENT`
- `--ack`

## `reconcile`
- `--agent AGENT`
