---
name: workflow-agent
description: Execute a named Agent Factory Work Unit or Human-approved Rework in a Goal-bound app-server thread. Use only for the scoped Plan, Work, AI Review, and Report phases after the launcher or Human explicitly starts the matching Work Unit execution.
---

# Workflow Agent

Execute only the named Work Unit matched by the active Goal. Apply `fact-only`,
`agent-rule`, `lifecycle`, `work-unit-planner`, `work-unit-execution`, and
`human-review` as required by the canonical package.

## Admission

1. Run the mandatory Goal preflight before planning, worktree preparation,
   editing, or verification.
2. Resolve and fully validate the canonical Work Unit package.
3. Read its complete basis, scope, exclusions, execution context, acceptance
   criteria, tests, AI checklist, Human checklist, review method, and blocks.
4. For initial execution, reconstruct the exact Work Unit checkpoint and
   prepare or reuse the dedicated branch and linked worktree.
5. For Human-approved Rework, require the manager-owned planned rework state
   and exact Human instruction, execute that instruction without expanding it,
   and reuse the registered branch and worktree.
6. Initialize or continue the manager-owned execution attempt before scoped
   mutation.

Fail closed when the Goal, package, checkpoint, execution state, repository,
branch, or worktree does not match.

## Execution

Run exactly:

```text
Plan -> Work -> AI Review -> Report
```

Use TDD for code Work Units. Record durable progress, exact verification
commands, registered evidence, AI checklist results, Human review material,
and the final worktree inspection through the owning managers.

## Exclusions

Do not own or change Intake decisions, Work Unit definition, Human approval,
merge, cleanup, push, deployment, or PR promotion. Do not expand scope, create
fallback Goal evidence, reimplement app-server Goal RPC, or bypass canonical
artifact managers.
