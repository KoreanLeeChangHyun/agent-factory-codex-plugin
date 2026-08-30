# P1b empty-ledger invariant follow-up review

Statically review the exact bound Work run for `P1B-REV-004`. Do not edit files
or run tests. Focus only on the directly changed `agent_loop.py`, loop contract,
and loop fixtures; concurrent P2 process-runtime changes in `agent_exec.py` and
its tests are outside this finding and are being reviewed separately.

Verify that every legitimate state produced only after applying a Review
receipt binds `latestAppliedReviewRunId` to the exact latest applicable Review,
including empty-ledger approval and required-evidence states. Verify that null
remains allowed for first/follow-up Review failure, cancellation, receipt
rejection, and finding-lifecycle rejection before application. Check null,
stale, Work-role, future, and acceptance-binding mismatch corruption.

Use stable IDs, explicitly resolve `P1B-REV-004` if corrected, and approve only
when no blocking issue remains in this finding boundary.
