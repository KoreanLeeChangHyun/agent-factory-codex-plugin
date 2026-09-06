Revise the P1b implementation for the independent Review findings and Main-observed test failures below.

Original request SHA-256: 4d2527d12e74f04ec8e7164b243ad241ef63f332b5100637f17a4ca68ff05b4d
Prior Work run: run-20260827T171140040740Z-e4e4b076
Review run: run-20260827T171719365461Z-0d68a423

Blocking Review findings:

1. `P1B-REV-001`: once Popen has occurred, a missing `thread.started` observation is ambiguous. Do not rewrite it to `not-started` or retry it. Permit automatic retry only for failures durably proven before process launch. Add a focused fixture proving one attempt only after a post-launch failure.
2. `P1B-REV-002`: make initial submit recoverable across the session.json-created/run-state-missing crash boundary. Durably reserve the exact initial dispatch tuple under the dispatch lock; exact retry completes the missing run, a different tuple collides, and normal submit against an established Agent remains rejected. Add the crash-boundary fixture.

Main-observed failures from `python3 -m unittest tests/test_agent_exec.py tests/test_agent_loop.py -v`:

3. The finding validator wrongly requires a pending entry's last Review to equal the newest dispatched Review. During `review-running`, the ledger legitimately still reflects the preceding completed Review until the current Review receipt is applied. Validate against the latest Review that has actually updated the ledger, while still rejecting stale ledger identities after a receipt is applied. Repair the unchanged-finding circuit and corrupt-ledger fixtures accordingly.
4. Wholly legacy pending-dispatch cancellation becomes `status/phase=cancelling` before reconcile. The narrow legacy validator must accept that exact cancelling state without accepting hybrid/new ambiguous states. Restore both legacy cancellation tests.
5. Keep the fixed explicit emit mocks and initial currentChild dispatch expectation. All focused tests should be able to pass after Main runs them; Work must not run tests.

Preserve P0 behavior, dispatch tuple collision semantics, finding material-identity rejection, non-Git compatibility, and all authorization boundaries. Edit only the six previously declared files and publish a valid Work receipt addressing `P1B-REV-001` and `P1B-REV-002`.
