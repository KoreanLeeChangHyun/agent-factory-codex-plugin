# `loop.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `start`
Required: `--request-file REQUEST_FILE`, `--work-agent WORK_AGENT`
- `--task-list-file TASK_LIST_FILE`: Announced task list; omitted for an orchestrator brief, which becomes a single runtime-derived task
- `--task-id TASK_ID`: Selected task in --task-list-file
- `--allocation-file ALLOCATION_FILE`: Optional schemaVersion 1 allocation evidence for a single brief; stored in its taskBinding, selects no model or authority
- `--model-catalog-file MODEL_CATALOG_FILE`: Host-supplied modelCatalog JSON; with allocation taskType the runtime records a detected-model recommendation and applies it only when no Work model is specified
- `--acceptance-id ACCEPTANCE_ID`: Explicit idempotency key for the same initial acceptance; distinct keys or new brief starts are distinct tasks even for identical text
- `--workspace-file WORKSPACE_FILE`: Captured code/shared/read-only plan with exact repositories, target branches and integration check argv arrays
- `--work-isolation | --no-work-isolation`: Work isolation toggle; inherited from the managed Main run when captured there. On requires --workspace-file (code or read-only), defaults targets to each repository's current branch and preserves unmergeable branches without a Human wait
- `--requested-by {human}`: Recorded sender when the Human sent this request directly (control center); omitted for Main dispatch
- `--task-mode {work,plan-work,work-verification,plan-work-verification}`
- `--verification-agent VERIFICATION_AGENT`
- `--codex CODEX`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`
- `--model MODEL`
- `--work-model WORK_MODEL`
- `--work-provider {codex,claude,antigravity}`
- `--work-execution-policy-file WORK_EXECUTION_POLICY_FILE`: Exact captured role policy; preserves sandbox independently from Human approval
- `--work-human-approval-policy {bypass,required}`
- `--work-reasoning-effort {none,low,medium,high,xhigh,max}`
- `--work-fast | --no-work-fast`
- `--work-execution-mode {cli-default,workspace-write,danger-full-access,bypass}`
- `--verification-model VERIFICATION_MODEL`
- `--verification-provider {codex,claude,antigravity}`
- `--verification-execution-policy-file VERIFICATION_EXECUTION_POLICY_FILE`: Exact captured role policy; preserves sandbox independently from Human approval
- `--verification-human-approval-policy {bypass,required}`
- `--verification-reasoning-effort {none,low,medium,high,xhigh,max}`
- `--verification-fast | --no-verification-fast`
- `--verification-execution-mode {cli-default,workspace-write,danger-full-access,bypass}`
- `--work-profile {work,workLight,explore,scribe}`: Work profile Main chose (work = Expert, workLight = Worker, explore = Explorer, scribe = Scribe); selects no model; explore writes exact task-bound evidence Documents and scribe writes only inside docs/
- `--work-capability-binding-file WORK_CAPABILITY_BINDING_FILE`
- `--verification-capability-binding-file VERIFICATION_CAPABILITY_BINDING_FILE`
- `--max-revisions MAX_REVISIONS`: Work revisions per task after failed Verification before the loop stops for a Human decision; 0 is unlimited
- `--receipt-recovery {auto,manual}`: auto gives Work one repair turn for an allowlisted receipt failure; manual stops for recover-receipt

## `status`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`

## `reconcile`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`

## `recover-receipt`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`

## `skip`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`

## `drive`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`

## `close`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`

## `stop-task`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`, `--workflow-id WORKFLOW_ID`, `--task-id TASK_ID`

## `refresh-progress`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`

## `extend-revisions`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`
- `--additional ADDITIONAL`: Further Work revisions the Human authorizes after the limit stopped the loop

## `answer`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`
One of: `--response-file` | `--response-json`
- `--response-file RESPONSE_FILE`: Exact decision identity and Human answer JSON
- `--response-json RESPONSE_JSON`: Inline exact decision identity and Human answer JSON

## `steer`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`, `--task-id TASK_ID`, `--run-id RUN_ID`, `--message MESSAGE`

## `revise`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`, `--workflow-id WORKFLOW_ID`, `--task-id TASK_ID`, `--run-id RUN_ID`, `--message MESSAGE`

## `retry-preparation`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`, `--task-id TASK_ID`

## `review`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`, `--decision {accepted,changes-requested,discarded}`
- `--note NOTE`: The Human's requested changes or reason

## `handoff`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`, `--actor {main,human}`, `--authorization-reference AUTHORIZATION_REFERENCE`, `--decision-evidence DECISION_EVIDENCE`, `--to-agent TO_AGENT`, `--to-model TO_MODEL`
- `--to-reasoning-effort {none,low,medium,high,xhigh,max}`
- `--to-fast | --no-to-fast`
- `--reason REASON`: Why the task moves, recorded in the handoff bundle

## `team-roster`: Workers by domain with availability, current, queued, waiting and failed tasks
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed

## `team-candidates`: Existing workers that fit a new task and every exclusion reason; Main still decides
Required: `--role {work,verification}`
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed
- `--provider PROVIDER`
- `--model MODEL`: Exact model; workers are compared one by one, never merged by model name
- `--reasoning-effort {none,low,medium,high,xhigh,max}`
- `--fast | --no-fast`
- `--work-profile {work,workLight,explore,scribe}`
- `--human-approval-policy {required,bypass}`
- `--sandbox SANDBOX`
- `--domain DOMAIN`: Allocation domain name; same-domain workers are listed first, others stay eligible

## `team-history`: One worker's tasks with every run's exact request, result and receipt
Required: `--agent AGENT`
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed
- `--parent-agent PARENT_AGENT`: Owning Main agent of the selected task
- `--workflow-id WORKFLOW_ID`
- `--task-id TASK_ID`
