Repair the remaining P1 stability defects after the prior loop failed closed.

Scope is limited to:

- skills/agent/scripts/agent_exec.py
- skills/agent/scripts/agent_loop.py
- skills/agent/references/loop.md
- skills/agent/SKILL.md only if semantics changed
- tests/test_agent_exec.py
- tests/test_agent_loop.py

Required corrections:

1. Restore normal `start_loop`: the strict validator must accept the legitimate freshly persisted initial `work-pending` + initial pending Work submit intent, while still rejecting illegal pending phases. Add a focused positive initial-state test and retain corrupt-phase rejection.
2. Fix the three Main-observed test fixture failures without weakening production behavior: capture `agent_exec.emit` through an explicit mock rather than `redirect_stdout`, and update the pre-existing current-child expectation to include the new dispatch identity/provenance contract as appropriate.
3. Finish strict finding-ledger validation. After child-history validation, require ledger first/last Review run IDs to exist in validated Review history and be ordered; require pending/resolved lifecycle identities to be compatible with Review order; require `findingFingerprints` to exactly equal the ledger fingerprint projection. Add corrupt-state tests for nonexistent/Work Review IDs, reversed order, stale pending last-review identity, and fingerprint-index mismatch.
4. Preserve the fail-closed `finding_identity_changed` rule. Do not allow a Review to materially redefine an existing finding ID; a materially different problem must use a new stable ID.
5. Make compatibility explicit for pre-P1 active state: only a wholly legacy state without any new dispatch/finding fields may use the narrow legacy recovery path. Hybrid states must fail closed. New states must always carry exact managed-run dispatch provenance.
6. Ensure stale-run reconciliation tests inspect emitted documents correctly and demonstrate: explicit pre-start state can resubmit; `launching`, durable thread-start marker, `startedAt`, or session identity cannot replay.
7. Run no tests or verification as Work Agent. Edit implementation and fixtures, publish a valid Work receipt, and state the exact addressed defects.

Preserve P0 evidence behavior, authorization boundaries, non-Git not-required compatibility, and unrelated files.
