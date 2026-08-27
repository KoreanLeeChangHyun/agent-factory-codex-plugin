# Bounded Work/Review Loop

## Policy

The loop serializes one Work session and one different Review session. It uses
the exact session identifiers managed by `agent_exec.py`; it never constructs a
Codex command, selects `resume --last`, creates a replacement session, or runs
the two roles concurrently. Advisory findings do not cause revisions.

Work and Review remain prohibited from tests and from external or destructive
actions. A loop flag cannot broaden the original request. Test evidence may be
consumed only when a Human or Main-owned JSON evidence file is explicitly
supplied to `start`; it never grants either child role test authority.
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
approved Review with no blocking findings -> completed
```

Runtime reconciliation may revive only a child attempt that the managed
runtime proves never started. It never replays a started semantic turn.

The loop state is atomically stored below
`.agent-factory/agent/<work-agent-id>/loops/<loop-id>/state.json` and guarded by
its loop lock. It records request, run, Agent, and Codex session identities;
counters and deadline; finding fingerprints; test evidence; terminal reason;
and a monotonic version. There is no central loop index.

## Stop conditions

- `completed`: the latest valid Review receipt approves the latest valid Work
  receipt, has no blocking findings, and any required Human test evidence shows
  success.
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
```

Defaults are three Work turns, three Review turns, two revisions, 7200 elapsed
seconds, and one unchanged-finding round. All budgets must be finite positive
integers and must leave enough Work and Review turns for the revision count.
`start` also accepts the managed execution options `--codex`, `--sandbox`, and
`--model`, plus `--test-evidence-file` for explicitly supplied orchestration
evidence. Evidence may be supplied only with policy `required`; when required
evidence is absent or does not show success, approval stops for Human action.

When `reconcile` omits the loop ID, it selects the first active loop by stable
loop-directory ordering and still advances no more than one semantic phase.

Every child process reasserts the stored project root and sandbox through the
parent `codex exec` options. JSONL and the compact output schema are repeated on
every exact-session resume. A classified `sandbox_unavailable` child failure is
terminal infrastructure failure, not a Review finding or revision trigger.
