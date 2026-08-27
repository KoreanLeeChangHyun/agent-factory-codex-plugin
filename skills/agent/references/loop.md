# Bounded Work/Review Loop

## Policy

The loop serializes one Work session and one different Review session. It uses
the exact session identifiers managed by `agent_exec.py`; it never constructs a
Codex command, selects `resume --last`, creates a replacement session, or runs
the two roles concurrently. Advisory findings do not cause revisions.

Work and Review remain prohibited from tests and from external or destructive
actions. A loop flag cannot broaden the original request. Test evidence may be
attached only after Review approval when it was produced by the Human or an
explicitly Human-authorized managed Verification Agent; Main may attach that
already-produced evidence as a control-plane operation. It never grants either
child role test authority. Pre-start evidence is rejected because it
cannot bind the source state that Review actually approved.
The caller must classify acceptance explicitly with
`--test-evidence-policy required|not-required`; the loop never infers this
policy from request prose.

## Lifecycle

`start` durably records the original request identity and finite budgets, then
asynchronously submits only the initial Work turn. Repeated `reconcile` calls
advance at most one semantic phase:

```text
initial Work -> new Review
blocking Review -> bounded send to the same Work session
revised Work -> send to the same Review session
approved Review, tests not required -> completed
approved Review, tests required -> test_evidence_required
Human/Verification test -> Main attach-evidence -> completed
```

Runtime reconciliation may revive only a child attempt that the managed
runtime proves failed before process launch. Once `Popen` succeeds, a missing
`thread.started` event is ambiguous and remains `launching`; neither in-worker
retry nor stale reconciliation replays it. Any durable state or event-stream
start marker also fails closed.

Every new loop child intent receives a durable `dispatch-...` identifier before
the loop calls `submit` or `send`. That identifier is scoped to one managed
Agent. Repeating it with the exact Agent, role, actor, child request SHA-256,
original/receipt request SHA-256, reviewed Work run, and submit/send operation
returns the original run; changing any member fails as
`dispatch_id_collision`. Reconcile looks up only the exact Agent and dispatch
identifier, validates the complete tuple, and retries a missing intent with the
same identifier. It never uses request hash and role to correlate new state.
Initial submit reserves this tuple before session creation, so an exact retry
can finish the session-created/run-state-missing boundary without converting a
normal submit against an established Agent into a send.
The request-hash recovery branch is isolated compatibility behavior for loop
state written before dispatch identifiers existed. It accepts only wholly
legacy active state with legacy child, current-child, pending-intent, and
finding fields. A hybrid containing any P1 dispatch provenance or finding-ledger
field fails closed instead of mixing correlation models.

The loop state is atomically stored below
`.agent-factory/agent/<work-agent-id>/loops/<loop-id>/state.json` and guarded by
its loop lock. It records request, run, Agent, and Codex session identities;
counters and deadline; finding fingerprints; acceptance and test-evidence
bindings; terminal reason; and a monotonic version. There is no central loop
index.

For required-evidence loops, before every Review dispatch the loop captures a
deterministic SHA-256 fingerprint of the Git state, persists it with the
original request and latest Work identities, and includes it in the Review
request. Review completion is accepted only if its run identity matches that
binding and a fresh fingerprint is unchanged. Review approval persists that
same fingerprint with the original request SHA-256, latest Work run ID, and
approving Review run ID. The fingerprint covers HEAD,
staged and unstaged changes (including deletions and binary patches), and the
path and bytes of untracked files. Runtime files below `.agent-factory/` are
excluded. Non-Git, unreadable, unsupported, or oversized source state fails
closed. Approval then stops as `needs-human-decision/test_evidence_required`;
it is not completion evidence by itself.

Loops whose policy is `not-required` preserve the original non-Git-compatible
Work/Review path and do not compute or require a workspace fingerprint.

Review finding state is a ledger, not a best-effort list. A finding ID keeps a
stable material fingerprint and its first and last Review run identities.
New-format state persists `latestAppliedReviewRunId`. The loop advances it only
after both receipt validation and finding-lifecycle application succeed, in the
same state transition as the updated ledger. Ledger ownership is always
validated against this durable identity, including after a later Review fails,
is cancelled, or is rejected before application.
The marker is also a phase invariant when the ledger is empty. Approval,
test-evidence waiting/completion, unchanged-finding and revision-budget stops,
and every Work revision state require it to equal the latest validated Review;
test-evidence states additionally bind the same identity as their approving
Review. Null remains valid when the first Review never applied, including
child failure, cancellation, or receipt/lifecycle rejection.
Initial Review resolves nothing. Each later Review must explicitly partition
every previously pending blocking ID between its current blocking findings and
`resolvedFindingIds`; new blocking IDs are allowed. Resolved IDs cannot
reappear, be resolved twice, or change material identity. Approval is valid
only after the Review explicitly resolves every prior pending ID. A Work
receipt's `addressedFindingIds` means the Work Agent claims it addressed the
requested items; only Review's `resolvedFindingIds` closes them.

Wholly legacy state predating dispatch provenance, the finding ledger, and the
applied-Review marker retains the narrow compatibility path described above.
Any state with new-format finding or dispatch fields but no applied-Review
marker is a hybrid and fails closed; the runtime does not infer ownership from
the latest dispatched Review.

## Stop conditions

- `completed`: the latest valid Review receipt approves the latest valid Work
  receipt, has no blocking findings, and either tests are explicitly not
  required or a successful, exactly bound evidence attachment was accepted.
- `needs-human-decision`: a child requests a Human choice, a semantic or elapsed
  budget expires, required test evidence is absent or inconclusive, or blocking
  findings survive the configured unchanged-finding threshold.
- `failed`: a child or protocol fails, a receipt/path/binding is invalid,
  session identity changes, request identity changes, or loop state is
  impossible.
- `cancelled`: cancellation was requested and the active child became terminal.
  Cancellation and terminal reconciliation are idempotent.

## Commands

```text
agent_loop.py start --request-file PATH --work-agent ID --review-agent ID \
  --test-evidence-policy required|not-required
agent_loop.py status --work-agent ID --loop-id ID
agent_loop.py cancel --work-agent ID --loop-id ID
agent_loop.py reconcile --work-agent ID [--loop-id ID]
agent_loop.py attach-evidence --work-agent ID --loop-id ID \
  --evidence-file PATH --test-output-file PATH
```

Defaults are three Work turns, three Review turns, two revisions, 7200 elapsed
seconds, and one unchanged-finding round. All budgets must be finite positive
integers and must leave enough Work and Review turns for the revision count.
`start` also accepts the managed execution options `--codex`, `--sandbox`, and
`--model`. The compatibility parser still recognizes `--test-evidence-file`,
but every use fails with `test_evidence_pre_start_forbidden`. When required
evidence is absent, approval stops for Human action.

`attach-evidence` accepts an exact JSON object with no additional fields:

```json
{
  "schemaVersion": "0.1.0",
  "kind": "agent-loop-test-evidence",
  "originalRequestHash": "<64 lowercase hex>",
  "latestWorkRunId": "<bound Work run>",
  "approvingReviewRunId": "<bound Review run>",
  "workspaceFingerprint": "<captured 64 lowercase hex>",
  "actor": "human",
  "timestamp": "<ISO-8601 timestamp>",
  "authorizationReference": "<Human authorization reference>",
  "command": "<test command that was run outside Work and Review>",
  "exitStatus": 0,
  "outputHash": "<SHA-256 of the separate output file's exact bytes>"
}
```

`actor` may be `human` or `verification`. The command hashes the separate bounded
output file, checks the zero exit status and all four acceptance bindings, then
recomputes the workspace fingerprint under the loop lock. It atomically copies
the evidence and output into the loop directory before publishing completed
state. An exact repeat is idempotent; a different reattachment fails closed.
The `status` response exposes the captured `acceptanceBinding` needed to author
the evidence object.

This gate is an integrity and lifecycle boundary, not an independent proof
that tests were honestly selected or executed. The Human owns authorization
and may supply the evidence directly; otherwise the Verification Agent owns
bounded command selection and execution under that authority. Main only
attaches the already-produced evidence. The loop proves only that the attached
bytes and declared successful result are bound to the source state approved by
Review. Main, Work, and Review never invoke the test command.

When `reconcile` omits the loop ID, it selects the first active loop by stable
loop-directory ordering and still advances no more than one semantic phase.

Every child process reasserts the stored project root and sandbox through the
parent `codex exec` options. JSONL and the compact output schema are repeated on
every exact-session resume. A classified `sandbox_unavailable` child failure is
terminal infrastructure failure, not a Review finding or revision trigger.

Each child attempt is Linux process-tree contained in its own session and
process group. The runtime binds worker and Codex PIDs to boot ID plus process
start ticks, verifies those identities before external cancellation or stale
reconciliation, and treats a mismatch as a reused PID rather than signalling
it. TERM and bounded KILL apply to the verified attempt group; unsupported or
unverifiable process identity fails closed. Terminal state atomically clears
the active Codex identity while preserving its last observed identity.

Across all attempts of one run, `events.jsonl` is capped at 8 MiB and
`stderr.log` at 4 MiB. Streaming checks reserve the complete next write before
persisting it, so the files never exceed those bounds. Either overflow is a
terminal protocol failure and shuts down the complete verified attempt group.
