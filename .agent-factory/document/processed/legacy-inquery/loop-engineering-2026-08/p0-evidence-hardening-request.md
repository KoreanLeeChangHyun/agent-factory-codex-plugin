Implement the P0 false-completion hardening for the Agent Factory bounded Work/Review loop.

Scope is limited to:

- skills/agent/scripts/agent_loop.py
- skills/agent/references/loop.md
- skills/agent/SKILL.md only if the command summary must change
- tests/test_agent_loop.py

Required behavior:

1. A test evidence file supplied at loop start must no longer be accepted as completion evidence. Keep a compatibility parser flag only if useful, but fail closed with a precise contract error when it is supplied.
2. When Review approves a loop whose test evidence policy is required, persist an acceptance binding containing the original request SHA-256, the latest Work run ID, the approving Review run ID, and a deterministic SHA-256 fingerprint of the reviewed Git source state. Stop in `needs-human-decision` with `test_evidence_required`; do not mark completed.
3. Add a public `attach-evidence` command. It may transition only that exact `needs-human-decision` / `test_evidence_required` state to completed.
4. Evidence must use an exact, versioned JSON schema and bind to the original request hash, latest Work run ID, approving Review run ID, and captured workspace fingerprint. Require actor `human` or `main`, a timestamp, authorization reference, command, integer exit status, and output hash.
5. Require a separate test output file. Hash its actual bytes and compare to `outputHash`; copy the bounded output and evidence into the loop directory atomically. Require exit status zero. Reject stale source state by recomputing the workspace fingerprint before acceptance.
6. Compute the source fingerprint from Git HEAD plus staged, unstaged, deletion, binary, and untracked source state. Exclude `.agent-factory/` runtime files so state writes do not invalidate the binding. Fail closed for non-Git projects or oversized/unreadable state. Do not invoke tests; Git read-only inspection is allowed.
7. Evidence attachment must be lock-protected and idempotent for the exact same evidence; conflicting reattachment must fail closed. The completed state must retain the evidence binding and hashes.
8. Add focused unit tests for: pre-start evidence rejection; valid post-Review attachment; mismatched request/work/review/workspace/output hash; non-zero status; source mutation after approval; wrong lifecycle state; idempotent repeat. Tests must create isolated Git repositories as needed.
9. Update loop documentation to explain the two-phase Review approval -> Main/Human test -> evidence attachment gate and its trust boundary.

Preserve all unrelated files and existing behavior. Work Agent is prohibited from running tests or verification commands. Make the implementation and test edits only, then publish the Work receipt.
