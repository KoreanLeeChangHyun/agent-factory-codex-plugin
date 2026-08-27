# Revision 2: fix live reconcile response stale child

Resolve one blocking defect found by Main during the authorized live end-to-end experiment. Preserve all previously resolved findings and current scope.

## MAIN-E2E-001 — blocking

- Path: `skills/agent/scripts/agent_loop.py`
- Problem: When `reconcile` consumes a completed Work child and dispatches the Review child, the durable loop state is correctly updated to `phase = review-running` and `currentChild = <review run>`, but the JSON returned by that same `reconcile` invocation still contains the prior completed Work public state as `currentChild`.
- Reproduction: In isolated temp Git repo `/tmp/agent-factory-loop-e2e-AZ3Qu8`, loop `loop-20260827T154221729493Z-d32e784d`, Work run `run-20260827T154221767146Z-c697a2de` completed. The first reconcile returned phase `review-running`, counters reviewTurns=1, but `currentChild.agentId=e2e-work`. The persisted state immediately had `currentChild.agentId=e2e-review`, run `run-20260827T154259011870Z-ac1f1e1c`, and a separate `status` call correctly returned that Review child.
- Impact: A host using the reconcile response as the next polling target can poll the wrong terminal child even though the transition itself succeeded.
- Required correction: After any semantic transition, make the returned loop document consistent with the newly persisted state. When a new child was dispatched, return that child's current public state (or at minimum the new exact child identity, consistently with the public contract), never the pre-transition child. Preserve the rule that one reconcile advances at most one semantic phase; a read-only child status query is not another transition. Ensure terminal reconcile responses do not expose a stale active child.
- Tests: Add a focused fake-runtime regression test asserting the reconcile response and persisted state name the same newly dispatched Review child, and that terminal completion does not retain a stale child.

Live E2E evidence beyond the defect: the Review child completed with `approved`, the next reconcile made the loop `completed` with terminal reason `approved`, the following `status` returned `currentChild: null`, and `proof.txt` contained exactly `loop-ok`. This experiment did not modify the plugin worktree.

Do not run tests, lint, builds, type checks, scripts, servers, or other verification commands. Work Agent remains prohibited from testing. Do not commit. Write the detailed revision result and required machine receipt with `MAIN-E2E-001` in `addressedFindingIds`.
