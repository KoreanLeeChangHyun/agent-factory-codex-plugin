# Adopt bounded loop engineering in Agent Factory

Implement one coherent bounded change that introduces a durable Work -> Review -> bounded Work revision -> Review loop on top of the existing managed Agent runtime.

Read first:

- `AGENTS.md`
- `skills/agent/SKILL.md`
- `skills/agent/references/work.md`
- `skills/agent/references/review.md`
- `skills/convention/references/annotation.md`
- `.agent-factory/agent/loop-engineering-inquiry-20260828/runs/run-20260827T150946495376Z-82749d6f/result.md`
- `.agent-factory/agent/codex-exec-options-inquiry-20260826/runs/run-20260826T135022955541Z-a1f3463a/result.md`

Preserve all existing uncommitted changes. In particular, do not undo the current `build_codex_command` parent-option placement, sandbox failure classification, tests, or Inquiry request wording.

Required behavior:

1. Add role-specific, machine-readable `receipt.json` files for Work and Review runs alongside `result.md`. Generate their schema/contract in the run state and tell the Agent the exact path and obligations. Keep the existing compact terminal JSON (`status`, `resultPath`) compatible.
2. Strictly validate receipt paths and contents before a Work/Review run may become `completed`: regular non-symlink bounded JSON, exact known fields, exact run/request binding, unique finding IDs, consistent Review decisions (`approved` has zero blocking findings; `changes_requested` has at least one), and explicit proof that Work/Review did not run tests. Preserve ordinary Main/Inquiry behavior without receipts.
3. Add `skills/agent/scripts/agent_loop.py` as a thin standard-library-only orchestration layer over `agent_exec.py`. Public commands: `start`, `status`, `cancel`, `reconcile`; private worker commands are allowed only if needed. Store atomic loop state at `.agent-factory/agent/<work-agent-id>/loops/<loop-id>/state.json`, with a lock and no central index.
4. `start` accepts a request file, distinct new Work and Review Agent IDs, and finite budgets. Defaults: max work turns 3, max review turns 3, max revisions 2, max elapsed seconds 7200, max unchanged finding rounds 1. Reject unlimited/nonpositive/contradictory values. Return an asynchronous ACK and start only the initial Work turn.
5. `reconcile` deterministically advances at most one semantic phase using exact managed sessions and the current child run state/receipts: initial Work -> new Review; changes requested -> `send` bounded findings to the same Work session; revised Work -> `send` follow-up to the same Review session; approval with no blocking findings -> completed. Never use `resume --last`, never construct `codex exec` directly, never run Agents concurrently on the same change, and never replay a started turn.
6. Terminate visibly as `needs-human-decision`, `failed`, `cancelled`, or `completed`. Stop for child/protocol failure, Human decision, expired budgets, absent required Human test evidence, or unchanged blocking finding fingerprints. Advisory findings never cause revision. Cancellation must be idempotent and propagate to an active child through the existing runtime.
7. Do not let the loop grant tests or external/destructive authority. Work and Review remain prohibited from testing. The loop may only consume explicitly supplied orchestration-owned test evidence; if the original request makes tests an acceptance condition and no such evidence is supplied, stop for Human evidence rather than asking an Agent to test.
8. Keep original request identity, child run IDs, exact Agent/Codex session identity, counters, finding fingerprints, deadlines, terminal reason, and monotonic version inspectable in state. Use atomic writes and prevent symlink/path traversal.
9. Add focused unit tests in `tests/test_agent_exec.py` and a new `tests/test_agent_loop.py` as appropriate. Cover receipt validation/invariants, finite budget validation, phase transitions, approval completion, blocking revision, unchanged-finding circuit, idempotent cancellation/reconcile, and preservation of the current sandbox command/failure behavior. Tests must use fakes and must not invoke a real Codex Agent.
10. Update `skills/agent/SKILL.md` routing and add a focused `skills/agent/references/loop.md` containing only non-obvious loop policy, lifecycle, stop conditions, and command usage. Do not copy generic web tutorials or a complete Codex manual into the distributed Skill. Keep the exhaustive installed `codex exec` option matrix in the existing Inquiry result; document only the runtime-relevant option invariants in the Agent Skill.

Compatibility and boundaries:

- Do not add platform sub-agents, fresh replacement sessions, pause/resume, dynamic scope expansion, parallel reviews, token/cost estimates, automatic test commands, commits, pushes, deployment, restart, or destructive recovery.
- Do not modify files outside `skills/agent/`, `tests/test_agent_exec.py`, and `tests/test_agent_loop.py`.
- Do not run tests, builds, linters, type checks, or other verification commands. Work Agent is prohibited from testing.
- Write a detailed implementation receipt to the runtime-declared result path, including changed paths, behavior, limitations, unresolved decisions, and the mandatory test status.
