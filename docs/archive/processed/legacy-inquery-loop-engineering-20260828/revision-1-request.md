# Revision 1: resolve blocking loop Review findings

Revise the bounded loop engineering implementation from Work run `run-20260827T151600802583Z-411aa613` to resolve exactly the three blocking findings from Review run `run-20260827T152958383224Z-99b0860b`.

Read the original Work request/result and the full Review result/receipt. Preserve the original scope, all existing uncommitted changes, and all behavior already approved by implication. Do not broaden the feature.

Required corrections:

1. `LOOP-REV-001`: Bind Work/Review receipt validation to the exact canonical managed path derived from the worker's trusted project root plus validated `agentId` and `runId`: `.agent-factory/agent/<agentId>/runs/<runId>/`. Require state, result, receipt schema, and receipt paths to equal their canonical files. Reject symlinks or non-directories in the relevant managed path components. Do not trust path strings in a mutable state document as the root of truth. Update tests to use canonical run layout and add negative coverage for an adjacent out-of-tree receipt and a symlinked component.
2. `LOOP-REV-002`: Make `cancelling` dominant during pending-dispatch recovery. Adopt exactly one matching child without changing back to `active`, cancel it immediately, and finalize cancellation only when the child is terminal. If no dispatch occurred, finalize safely without creating one. Add a crash-window pending-dispatch cancellation test plus an idempotent repeat.
3. `LOOP-REV-003`: Remove free-prose regex inference for test acceptance. Introduce an explicit caller-owned start contract that cannot silently default—prefer one required enum such as `--test-evidence-policy required|not-required`, or an equally unambiguous mutually exclusive interface. Record the selected policy in state. When required, completion must stop without valid supplied evidence; when not required, do not infer from prose. A supplied evidence file must be consistent with the explicit policy. Update command documentation and positive/negative tests.

Main verification evidence after the initial Work turn:

- `python3 -m unittest tests/test_agent_exec.py tests/test_agent_loop.py`: 10 tests passed.
- Python compile and Skill quick validation passed.
- Full repository discovery ran 154 tests and reported 58 failures/52 errors because retained legacy tests reference already absent `skills/work-units`, `skills/intakes`, and other retired paths. Do not restore or modify those unrelated systems.

Do not run tests, lint, builds, type checks, scripts, or verification commands. Work Agent remains prohibited from testing. Do not commit. Write the detailed revision receipt and required machine receipt to the runtime-declared paths. Include addressed finding IDs and the mandatory test status.
