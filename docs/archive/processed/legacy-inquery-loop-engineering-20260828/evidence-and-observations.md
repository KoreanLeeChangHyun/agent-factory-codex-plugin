# Loop engineering adoption — unrefined evidence and observations

Inquiry date: 2026-08-28 (Asia/Seoul)

Boundary: investigate a bounded Work -> Review -> Work revision loop for the
existing managed Agent runtime. This inquiry does not change product files,
does not authorize Work or Review Agents to test, and does not select a broader
autonomy or risk policy.

## Local observations

Inspected:

- `AGENTS.md`
- `skills/agent/SKILL.md`
- `skills/agent/references/main.md`
- `skills/agent/references/work.md`
- `skills/agent/references/review.md`
- `skills/agent/references/inquery.md`
- `skills/inquery/SKILL.md`
- `skills/inquery/references/workspace.md`
- `skills/agent/scripts/agent_exec.py`
- `tests/test_agent_exec.py`
- `git status --short`, the current diffs for the two product paths above, and
  the overall diff stat

Observed contract invariants:

- Main owns Human interaction, tests, risk decisions, result integration, and
  the Work -> independent Review -> bounded revision route.
- Work edits but never tests or self-reviews. Review is a separate managed
  Codex session, is static/read-only, never tests, and may request revision only
  for concrete blocking findings. Human-owned decisions stop automation.
- Managed Agents must use `codex exec`, never platform sub-agents. Each Agent's
  exact Codex thread/session ID is persisted in its `session.json` and resumed
  explicitly. Only one turn may be active in one session.
- Runtime state is already durable and inspectable beneath
  `.agent-factory/agent/<agent-id>/runs/<run-id>/`: request hash, state, result
  path, event stream, heartbeat, attempts, session ID, terminal status, unread
  flag, and stable error object.

Observed runtime mechanics:

- `submit` creates a session plus first run; `send` creates a run against an
  existing session; both return immediately after starting a background worker.
- A per-Agent `.session.lock` serializes turns. The worker verifies the immutable
  request hash, requires a `thread.started` event, rejects a resumed thread ID
  mismatch, validates the compact terminal JSON, and requires a nonempty regular
  result file.
- Worker retries are intentionally narrow. A failure before Codex has started
  may consume another `maxAttempts` attempt. A failure after `thread.started`
  breaks the attempt loop, avoiding replay of an Agent turn that may already
  have modified the workspace. `reconcile` only resubmits a stale run when no
  recorded process is alive and the attempt budget remains.
- `cancel` records `cancelRequested`, changes status to `cancelling`, and signals
  the worker. `status`, `result`, and `inbox` expose run state; `result --ack` and
  `inbox --ack` clear unread state.
- Existing terminal states are `completed`, `needs-human-decision`, `failed`,
  and `cancelled`. The detailed result is Markdown. The compact terminal schema
  does not contain role-specific Work or Review data, so it cannot currently
  prove "approved with zero blocking findings" or bind a Review decision to the
  latest Work run without parsing prose.

Observed uncommitted sandbox fix:

- `build_codex_command()` now reasserts stored `projectRoot` and `sandbox` before
  `resume`, while preserving the exact stored session ID and avoiding the
  dangerous bypass switch.
- Missing results whose stderr contains both known bubblewrap/helper fragments
  are classified as `sandbox_unavailable`; partial signatures remain
  `result_file_missing`. The resulting `AttemptFailure` is marked as started,
  so it is not automatically replayed.
- The test diff adds command-shape and signature-classification coverage and a
  per-test module reload. These are user changes and were not modified or run.
- Compatibility implication: loop orchestration should consume the existing
  terminal failure code and stop/escalate. It should not rebuild Codex commands,
  weaken sandbox settings, or retry `sandbox_unavailable` as a revision.

Read-only parser experiment:

- `python` is not installed under that command name; three help invocations
  failed with `command not found` and changed no files.
- Repeated with `python3`. Top-level help confirms the public commands
  `submit`, `send`, `status`, `result`, `cancel`, `list`, `inbox`, and
  `reconcile`. `submit` owns role/session/sandbox/timeouts/attempt budget;
  `send` accepts only an existing Agent and new request. This supports a thin
  orchestration layer over the current primitives rather than duplicating their
  process/session logic.
- No repository tests, builds, linters, type checks, servers, or health checks
  were run.

## Primary-source web evidence

URLs were read on 2026-08-28:

1. Geoffrey Huntley, original Ralph description:
   https://ghuntley.com/ralph/
   - The pure form is a shell loop repeatedly allocating the prompt.
   - It emphasizes one item per loop, a stable plan/specification spine, fresh
     context, feedback/backpressure, and operator observation/tuning.
   - It also explicitly warns that the technique can go off track and closes by
     saying he would not use that form on an existing codebase. This is evidence
     for borrowing the loop shape, not its unbounded authority, test behavior,
     or destructive recovery practices.
2. Huntley's later framing:
   https://ghuntley.com/loop/
   - Describes a loop as an orchestrator pattern around a backing specification
     and goal, one task per loop, with monitoring and intervention at failure
     domains.
3. Anthropic's official Ralph setup script:
   https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/scripts/setup-ralph-loop.sh
   - Persists local iteration, max-iteration, completion-promise, and start time.
   - Stops on exact completion text or iteration cap, but defaults the cap to
     unlimited and warns of infinite execution. Exact model-authored promise
     matching is too weak for this plugin's completion gate; the useful lesson
     is a hard external iteration cap and inspectable state.
4. Anthropic, Building effective agents:
   https://www.anthropic.com/engineering/building-effective-agents
   - Distinguishes code-defined workflows from model-directed agents, recommends
     the simplest adequate design, notes latency/cost tradeoffs, and documents
     evaluator-optimizer as generator plus evaluator feedback in a loop.
5. Anthropic, Effective harnesses for long-running agents:
   https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
   - Uses incremental sessions plus durable progress artifacts to bridge context
     windows; identifies multi-Agent specialization as an open question rather
     than a settled universal best practice.
6. Anthropic, Harness design for long-running application development:
   https://www.anthropic.com/engineering/harness-design-long-running-apps
   - Reports value from tractable chunks, structured file handoffs, distinct
     generator/evaluator roles, and context resets. It also reports that resets
     helped one model stay on task; that is contextual evidence, not proof that
     fresh context always dominates resume.
7. OpenAI, Harness engineering:
   https://openai.com/index/harness-engineering/
   - Reports iterative implementation/review until reviewers are satisfied and
     emphasizes mechanically enforced invariants and repository legibility.
8. OpenAI, Unrolling the Codex agent loop:
   https://openai.com/index/unrolling-the-codex-agent-loop/
   - A Codex turn itself loops model/tool calls until an assistant message; new
     messages to the same thread include prior history, increasing prompt size
     and requiring context management.
9. OpenAI, Running Codex safely at OpenAI:
   https://openai.com/index/running-codex-safely/
   - Recommends clear technical boundaries, explicit handling of higher-risk
     actions, managed sandbox/network policy, and auditable agent-native logs.
10. AWS Prescriptive Guidance, Circuit breaker pattern:
    https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/circuit-breaker.html
    - Recommends bounded backoff for transient failures, opening a circuit after
      a threshold, immediate failure while open, explicit operator control, and
      observability. For this local workflow, semantic revision is not a retry;
      repeated identical findings and terminal infrastructure errors need
      separate stop policies.

## Comparison against the requested dimensions

| Dimension | Common loop lesson | Agent Factory fit |
|---|---|---|
| Bounded stop | External iteration/time caps are safer than a model promise. | Require finite revision, turn, elapsed-time, and unchanged-finding caps. Never default to unlimited. |
| Persistent spine | Files/specs/progress records survive context boundaries. | Make an atomic `loop.json` the authority and link immutable run IDs, hashes, receipts, finding fingerprints, evidence, and budgets. Markdown remains explanatory only. |
| Maker/checker | Generator/evaluator roles reduce self-approval. | Existing Work and Review contracts already provide stronger separation: different exact sessions, serialized turns, Review read-only. |
| Retry/circuit breaker | Retry only transient faults; open after repeated failures. | Keep `agent_exec` pre-start/reconcile retry. Never replay a started Work turn. Stop on terminal infrastructure errors; stop after unchanged blocking fingerprints across revisions. |
| Human escalation | Unclear judgment and high-risk action need operator control. | `needs-human-decision` is terminal for automation. Also escalate budget exhaustion, contradictory receipts, test-required-without-evidence, and unresolved risk/product choices. |
| Budgets | Iterations alone are insufficient; time/cost/context matter. | V1 can enforce finite work/review turns, revisions, elapsed seconds, and per-turn runtime attempts. Token/cost metering is unavailable and must be a documented limitation, not estimated from prose. |
| Fresh vs resumable | Fresh context can reduce drift; resume retains rationale and avoids repeated discovery. | Resume the exact Work session for revisions and the exact Review session for follow-up review, as required. Counter context drift with small turn caps and durable receipts. Do not silently replace a session with a fresh Agent; escalate if context health becomes a blocker. |

## Working conclusion

Do not adopt an unbounded self-referential Ralph loop. Adopt a small,
code-defined, externally bounded evaluator-optimizer workflow. Keep the current
Agent runtime as the turn executor and add only durable loop coordination plus
machine-readable role receipts. The model proposes implementation and findings;
the orchestrator, not model prose, decides transitions.
