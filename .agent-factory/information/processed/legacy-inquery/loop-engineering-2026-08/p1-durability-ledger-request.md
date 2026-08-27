Implement P1 durable dispatch correlation and Review finding lifecycle hardening for the Agent Factory managed runtime and bounded loop.

Scope is limited to:

- skills/agent/scripts/agent_exec.py
- skills/agent/scripts/agent_loop.py
- skills/agent/references/loop.md
- skills/agent/SKILL.md only if public command semantics need clarification
- tests/test_agent_exec.py
- tests/test_agent_loop.py

Required behavior:

1. Add an optional public `--dispatch-id` to `agent_exec.py submit` and `send`. Validate an opaque `dispatch-...` identifier and persist it in run state and ACK/status.
2. Within one managed Agent, make dispatch IDs idempotent under a dedicated lock. First use creates one run. Same ID plus the exact same immutable dispatch tuple returns the original run/ACK with a deduplication marker and never starts another semantic turn. Same ID with a different tuple fails `dispatch_id_collision`.
3. The immutable tuple must include Agent, role, actor, child request SHA-256, receipt/original request SHA-256, reviewed Work run when present, and the submit/send operation needed to distinguish initial versus resumed dispatch.
4. `agent_loop.py` must generate and durably persist a unique dispatch ID before every submit/send, pass it to the runtime, record it on the child, and recover an unknown ACK outcome only by exact Agent + dispatch ID plus full tuple validation. It must not correlate new loop dispatches by request hash and role. Preserve a clearly isolated compatibility recovery path only for old state that has no dispatch ID.
5. If a new dispatch intent has no matching run during reconcile, retry the same runtime call with the same dispatch ID and tuple. The runtime deduplication must make crash-after-create-before-ACK safe. Never create a new dispatch ID during recovery, and never replay a managed run that is proven started.
6. Add fault-injection unit tests for duplicate submit/send; collision; two identical request bodies with different dispatch IDs; crash before runtime call; crash after run creation before ACK; adoption of the exact run; and rejection of a tuple mismatch.
7. Enforce Review finding lifecycle in loop state. For initial Review, `resolvedFindingIds` must be empty. For every follow-up, prior pending blocking IDs must be exactly partitioned into current blocking IDs and `resolvedFindingIds`. Reject omitted, unknown, duplicated, still-current-and-resolved, already-resolved, or reappearing resolved IDs. New blocking IDs remain allowed.
8. Persist a finding ledger with stable material fingerprints, first/last Review run identities, pending IDs, and resolved IDs. Approved Review is valid only when no blocking finding remains and every prior pending ID is explicitly resolved. Existing Work `addressedFindingIds` accounting remains required.
9. Add focused tests for valid resolution, silent drop, unknown resolution, current-and-resolved conflict, material identity change, and resolved-ID reappearance.
10. Add a strict validator for the new dispatch and finding-ledger portions of loop state before any runtime side effect. It must fail closed on type/path/identity/counter inconsistencies introduced by these new fields, without trying to migrate or reinterpret ambiguous active state.
11. Update documentation with idempotency scope, legacy compatibility boundary, and the difference between Work addressing and Review resolving a finding.

Preserve P0 evidence binding behavior, existing terminal envelopes, exact Work/Review sessions, unrelated non-Git behavior, and all authorization boundaries. Work Agent must not run tests or verification commands. Implement and edit test fixtures only, then publish a Work receipt.
