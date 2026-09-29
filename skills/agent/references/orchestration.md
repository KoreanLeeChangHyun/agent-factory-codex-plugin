# Orchestration

- Main reads this before dispatching managed Work or Verification. Direct mode does not use it.

<a id="chains"></a>

## 1. Chains and shared resources

- Use the current shared checkout without separate Git worktrees. Apply Convention's
  [shared checkout coordination](../../convention/references/development.md#shared-checkout-coordination) when assigning write boundaries, sequencing conflicts and stabilizing
  Verification inputs.
- Assess dependencies across repository paths/writes and shared mutable resources: Git
  index/worktree, Agent/session/loop/run IDs, databases, ports and external systems.
- Sequence uncertain independence or obtain the missing Human decision. Parallelize only
  useful independent chains with distinct Agent/loop/run IDs, bounded inputs, scoped
  authority and capability bindings.
- Each chain stays sequential.
  - In Work-bound verification modes bind separate Verification to exact completed Work unless
    Human skip applies.
  - In work and plan-work modes acknowledge completed Work and its receipt, report
    its own checks, and end without separate Verification. Do not review implementation
    or rerun tests. Acceptance/status/receipt identity checks are not re-verification.
  - Plan alone dispatches Work with `--task-mode plan` and stops at its plan.
  - Plan-work routes use actual collaboration-mode transitions in the same Work session
    through loop.py.
  - Standalone verification dispatches Verification with `--task-mode verification`;
    resolve explicit target first, then prior completed work in this chat, otherwise ask.
    Its standalone receipt never substitutes for a Work-bound loop receipt.
  - Sequence overlapping work and repository-wide integration.
- Track every chain, preserve execution/results and integrate in dependency order.
  Conflict avoidance is your judgment, not a runtime guarantee or parallelism quota.

<a id="verification-and-skip"></a>

## 2. Verification and skip

- **Fail:** send findings to the same Work Agent; send revisions to the same
  Verification Agent.
- **Pass:** integrate and report.
- **Human skip:** record actor, authorization reference and decision evidence before the
  next Verification. Intent alone is no transition. Apply only after current
  initial/revision Work completes; reach END without starting further Verification.
