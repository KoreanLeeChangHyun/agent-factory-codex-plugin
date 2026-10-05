# `loop.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `start`
Required: `--request-file REQUEST_FILE`, `--work-agent WORK_AGENT`
- `--task-list-file TASK_LIST_FILE`: Announced task list; omitted for an orchestrator brief, which becomes a single runtime-derived task
- `--task-id TASK_ID`: Selected task in --task-list-file
- `--workspace-file WORKSPACE_FILE`: Captured code/shared/read-only plan with exact repositories, target branches and integration check argv arrays
- `--work-isolation | --no-work-isolation`: Work isolation toggle; inherited from the managed Main run when captured there. On requires --workspace-file (code or read-only), defaults targets to each repository's current branch and preserves unmergeable branches without a Human wait
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
- `--work-reasoning-effort {none,low,medium,high,xhigh,max}`
- `--work-fast | --no-work-fast`
- `--work-execution-mode {cli-default,workspace-write,danger-full-access,bypass}`
- `--verification-model VERIFICATION_MODEL`
- `--verification-reasoning-effort {none,low,medium,high,xhigh,max}`
- `--verification-fast | --no-verification-fast`
- `--verification-execution-mode {cli-default,workspace-write,danger-full-access,bypass}`
- `--work-profile {work,workLight}`: Work profile label Main chose (work = Expert, workLight = Worker); recorded for display only, selects no model or authority
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
