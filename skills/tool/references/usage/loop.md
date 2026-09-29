# `loop.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `start`
Required: `--task-list-file TASK_LIST_FILE`, `--task-id TASK_ID`, `--request-file REQUEST_FILE`, `--work-agent WORK_AGENT`
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
- `--work-execution-mode {cli-default,workspace-write,danger-full-access,bypass}`
- `--verification-model VERIFICATION_MODEL`
- `--verification-reasoning-effort {none,low,medium,high,xhigh,max}`
- `--verification-execution-mode {cli-default,workspace-write,danger-full-access,bypass}`
- `--work-capability-binding-file WORK_CAPABILITY_BINDING_FILE`
- `--verification-capability-binding-file VERIFICATION_CAPABILITY_BINDING_FILE`

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

## `refresh-progress`
Required: `--work-agent WORK_AGENT`, `--loop-id LOOP_ID`
