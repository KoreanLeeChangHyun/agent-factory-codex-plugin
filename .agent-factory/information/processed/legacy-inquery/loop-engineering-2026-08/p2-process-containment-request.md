# P2: process-tree containment, PID identity, and bounded runtime logs

Harden the Agent Factory managed runtime against orphaned subprocesses, PID
reuse, and unbounded event/stderr growth. This is a Linux-first runtime but its
documented behavior must fail safely on unsupported platforms.

## Required behavior

1. Give each Codex attempt an isolated process group/session. Every normal
   cancellation, timeout, event/protocol error, and forced shutdown must signal
   the entire attempt group (TERM, bounded wait, then KILL), not only the direct
   Codex PID. Never target the invoking shell or a broad/unverified group.
2. Persist enough immutable Linux process identity for the worker and active
   Codex leader to distinguish the intended process from a reused PID (for
   example boot ID plus `/proc/<pid>/stat` start ticks). Before an out-of-process
   cancel or stale-reconcile liveness conclusion, verify the exact identity.
   Identity mismatch must fail closed and must never signal the unrelated PID.
3. Clear active Codex identity atomically when an attempt becomes terminal.
   Preserve crash diagnosability and current no-replay semantics.
4. Bound aggregate `events.jsonl` and `stderr.log` bytes per run. Enforce limits
   while streaming, before disk growth can exceed the documented bound. A limit
   breach must terminate the whole attempt group and produce a stable protocol
   failure. Preserve per-line validation and fsync/durable state expectations.
5. Document the containment, identity, caps, and portability behavior in
   `skills/agent/references/loop.md` and/or `skills/agent/SKILL.md`.
6. Add focused deterministic tests for nested-child termination, PID identity
   match/mismatch, stale reconcile under PID reuse, aggregate event overflow,
   stderr overflow, and identity cleanup. Do not weaken existing tests.

## Constraints

- Work and Review Agents must not run tests; Main owns all execution.
- Keep changes scoped to `skills/agent/scripts/agent_exec.py`, its Agent docs,
  and `tests/test_agent_exec.py` unless a directly required contract adjustment
  is identified and reported.
- Preserve dispatch idempotency, initial reservation, receipt validation,
  sandbox/role boundaries, and fail-closed replay rules.
- Do not infer Human authorization or acceptance decisions.
