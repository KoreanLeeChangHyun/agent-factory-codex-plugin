Verification result: PASS

- Python compilation: PASS
- Work Unit planner: 35 tests PASS
- Work Unit execution launcher/worktree: 55 tests PASS
- Intake manager: 32 tests PASS
- Specification manager: 9 tests PASS
- Lifecycle contracts: 19 tests PASS
- Work Unit and Specification schema checks: PASS
- Project Core and durable execution Specification full validation: PASS
- Active linked worktree sparse patterns: `/*`, `!/.agent-factory/`
- Active linked worktree `.agent-factory` presence: ABSENT
- Removed command/reference scan: no active artifact handoff, approval, checkpoint,
  immutable Git subject, or direct `codex exec` launch path remains.

AI review: PASS

- Canonical Intake, Specification, and Work Unit CRUD resolves to the primary
  repository through owning manager scripts.
- Worktree preparation excludes the entire `.agent-factory`.
- Specification-direct execution requires no branch or worktree.
- Work Unit readiness requires `app_server_goal.py`; direct `codex exec` is
  rejected.
- Initial and recovery prompts declare the Workflow Agent and require execution.
- Interrupted and stale blocked Goal states automatically continue; bounded
  exhaustion returns `goal_recovery_exhausted`.
- Result review is `rework` or `complete`; approval/checkpoint gates are absent.
