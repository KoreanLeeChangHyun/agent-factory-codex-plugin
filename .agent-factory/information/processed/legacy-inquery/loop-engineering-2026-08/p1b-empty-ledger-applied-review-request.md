# P1b empty-ledger applied-Review invariant

Continue in the exact P1b Work Agent session and correct `P1B-REV-004` only.

The strict validator currently accepts a new-format approved terminal state
whose `findingLedger` is empty after `latestAppliedReviewRunId` is changed from
the actual applied Review to `null`. This state is impossible through the
legitimate transition but is not rejected.

Required correction:

- Derive and enforce phase/terminal invariants for every state that can exist
  only after a Review receipt has been successfully applied, including at least
  `completed/approved` and `needs-human-decision/test_evidence_required`.
- Such states must bind `latestAppliedReviewRunId` to the exact appropriate
  Review in validated history even when the ledger is empty; reject null,
  stale, Work-role, or future identities.
- Continue allowing null when the first Review failed, was cancelled, or its
  receipt/lifecycle was rejected before application.
- Add focused corrupt-state tests that null and stale the marker on an
  empty-ledger approved/evidence-waiting state, while preserving the unapplied
  failure cases.
- Keep changes within the declared P1b scope. Do not run tests; Main owns them.

Report exact changed files and verification recommendations.
