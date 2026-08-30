# P1b ledger applied-Review correction

Continue the P1b durability hardening in the exact existing Work Agent session.

## Blocking finding to correct

`P1B-REV-003`: `agent_loop.py` currently infers the Review run that owns the
finding ledger from the latest dispatched Review except while a Review child is
actively running/cancelling. If a follow-up Review fails, is cancelled, or its
receipt/lifecycle is rejected before application, terminalization clears
`currentChild`. A later validation then incorrectly requires the unchanged
ledger to belong to that unapplied Review and reports `loop_state_invalid`
instead of preserving the original terminal reason.

## Required result

- Persist an exact latest-applied-Review identity (or an equally unambiguous
  receipt-application marker) in every new-format loop state.
- Advance it atomically only after a Review receipt and finding lifecycle have
  both been successfully applied.
- Validate ledger ownership against this durable applied identity in active and
  terminal phases.
- Keep strict rejection for genuinely corrupt/hybrid state. Document any legacy
  compatibility rule narrowly.
- Add focused tests for a follow-up Review with a nonempty ledger that then:
  1. fails as a child,
  2. is cancelled,
  3. is rejected for `finding_identity_changed` or invalid receipt.
  Repeated `status`/`reconcile` must retain the original terminal reason rather
  than later becoming `loop_state_invalid`.

Do not run tests; Main owns execution. Limit edits to the P1b declared six-file
scope and report exact changed files and verification recommendations.
