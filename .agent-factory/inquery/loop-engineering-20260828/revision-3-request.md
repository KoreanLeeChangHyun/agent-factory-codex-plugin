# Revision 3: fully resolve MAIN-E2E-001 terminal branches

Resolve the remaining portion of blocking finding `MAIN-E2E-001` from Review run `run-20260827T154642929797Z-42660cd9`. Preserve all earlier resolved behavior and make only the smallest correction.

Review evidence identifies two terminal branches in `reconcile_loop` that call `_terminal`, persist `currentChild = None`, then return `loop_status_document(state, run)`. Because the explicit `run` argument wins, cancellation terminal and child failure/needs-human-decision responses expose the consumed child and contradict persisted state.

Required correction:

- Route every terminal reconcile return through the same post-transition response behavior or return the terminal state without passing the consumed child.
- Ensure cancellation, failed child, and `needs-human-decision` child terminal responses each return `currentChild: null` and match persisted state.
- Add focused fake-runtime tests for all three branches. Retain the existing Work-to-Review and approval completion regression assertions.
- Keep one-transition semantics and all prior receipt, cancellation recovery, test evidence, budget, exact-session, and sandbox behavior unchanged.

Main verification before this revision: focused tests passed 17/17, compilation and Skill validation passed. Do not run tests, lint, builds, type checks, scripts, servers, or verification commands. Work Agent remains prohibited from testing. Do not commit. Write the detailed result and required receipt with `MAIN-E2E-001` in `addressedFindingIds`.
