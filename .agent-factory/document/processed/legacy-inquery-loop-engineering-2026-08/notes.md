# Loop engineering adoption — unrefined research notes

As-of date: 2026-08-28. Inquiry boundary: terminology and source-backed practices for autonomous coding-agent loops, followed by a static assessment of this repository's managed Agent runtime. No product changes were made and no tests, linters, builds, or other verification commands were run.

## Working conclusion

"Loop engineering" is a useful new umbrella for designing the *outer operational cycle* that repeatedly discovers or receives work, packages context, launches one or more agent runs, obtains independent or deterministic evidence, persists state, decides whether to retry/stop/escalate, and remains observable and bounded. The name is emerging practitioner vocabulary from mid-2026, not a settled standard or a newly invented algorithm. Most of its mechanisms predate the label.

Agent Factory already has a credible bounded Work -> independent static Review -> revision state machine. It is stronger than a naive Ralph-style shell loop in identity binding, finite budgets, crash recording, liveness, authority separation, and machine-readable receipts. It is not yet a general proactive "loop engineering" platform: there is no scheduler/discovery queue, isolated per-task worktree, deterministic verifier inside the loop, artifact snapshot binding, exact dispatch idempotency key, or production-grade trace/metric surface. That narrower scope is not itself a defect; the repository's Human-owned test-authority contract intentionally prevents the strongest common pattern—letting the loop run tests and use them as its stop oracle.

The most serious correctness problem found is narrower and concrete: `agent_loop.py` accepts test evidence only at `start`, before any Work or revision exists, then may use that unbound evidence to complete after later revisions. The evidence contains no Work run, request hash, tree/diff hash, output artifact, freshness window, or verified authorization binding. A successful exit status is therefore an assertion about an unknown prior subject, not proof about the latest code.

## Terminology map

### Agent loop (old, inner execution mechanism)

The agent loop is the model/tool interaction cycle inside a single turn or session: construct context, call the model, execute requested tools, append observations, repeat until the model returns or a limit trips. OpenAI's January 2026 "Unrolling the Codex agent loop" explicitly calls the Codex harness the core agent loop and execution logic: https://openai.com/index/unrolling-the-codex-agent-loop/ . OpenAI's practical guide similarly describes the runner looping until final output or a maximum-turn condition: https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/ . ReAct (Yao et al., 2022/ICLR 2023) is an earlier research formulation that interleaves reasoning and environment actions: https://arxiv.org/abs/2210.03629 .

This is below Agent Factory's `agent_loop.py`: every managed `codex exec` child already contains an inner Codex agent loop; `agent_loop.py` orchestrates multiple completed semantic turns around it.

### Evaluator-optimizer workflow (older workflow pattern)

Anthropic's December 2024 "Building Effective Agents" defines evaluator-optimizer as one LLM generating while another evaluates and feeds back in a loop, suitable when evaluation criteria are clear and iteration measurably improves the result: https://www.anthropic.com/engineering/building-effective-agents . This is the closest named ancestor of Agent Factory's Work/Review pairing. It is a workflow shape, not a full durable runtime contract: by itself it says little about process recovery, exact run identity, path safety, budgets, scheduling, cancellation, or operator observability.

### Iterative refinement, Self-Refine, and Reflexion (older inference/trial techniques)

Self-Refine uses the same LLM as generator, feedback provider, and refiner over an output; it does not require an external operational environment or a distinct reviewer (Madaan et al., 2023): https://arxiv.org/abs/2303.17651 . Reflexion stores verbal reflection from task feedback in episodic memory for later trials (Shinn et al., 2023): https://arxiv.org/abs/2303.11366 . These explain how feedback can improve later attempts, but they are not synonymous with engineering a safe autonomous lifecycle. Agent Factory deliberately chooses separate Work and Review sessions rather than self-grading, and persists protocol state rather than a free-form reflective memory.

### Ralph / Ralph Wiggum loop (older coding practice and implementations)

The Ralph technique popularized an outer script that repeatedly launches a coding agent, often with fresh context, a durable spec/implementation plan, one bounded unit of work, tests, and progress written back to files. Geoffrey Huntley's original-method repository is the appropriate implementation lineage to inspect: https://github.com/ghuntley/how-to-ralph-wiggum . Anthropic later described Ralph-like hooks/scripts as community convergence around continuous iteration, while noting coherence and self-evaluation failures in longer work: https://www.anthropic.com/engineering/harness-design-long-running-apps .

Ralph is a particularly simple instance of an autonomous coding loop. "Loop engineering" generalizes beyond the while-loop recipe to trigger/discovery, task isolation, permissions, state, independent checkers, explicit machine stop conditions, recovery, observability, cost limits, and human escalation. Agent Factory is almost the inverse trade-off of a minimal Ralph loop: much stronger lifecycle binding, but no automated test oracle and no fresh-context-per-iteration strategy.

### Harness engineering (environment around a run)

Harness engineering shapes the environment in which a model acts: prompts/context, tools and their interfaces, repository legibility, sandboxes, memory/compaction, feedback, and architectural constraints. OpenAI describes strict boundaries, repository-visible knowledge, enforceable architecture, and feedback loops in "Harness engineering": https://openai.com/index/harness-engineering/ . SWE-agent experimentally showed that an agent-computer interface materially changes software-engineering performance (Yang et al., 2024): https://arxiv.org/abs/2405.15793 . Anthropic stresses structured handoffs, context resets, independent evaluators, and measurable criteria for long-running applications: https://www.anthropic.com/engineering/harness-design-long-running-apps .

Useful boundary: the harness is what makes one agent execution effective and safe; loop engineering decides when and why to invoke harnessed runs again, what state/evidence crosses iterations, and when the outer process stops. The boundary is not universal—OpenAI also calls its orchestration layer a harness—so it should not be treated as a formal taxonomy.

### Classical control loop (much older systems concept)

A classical feedback controller measures a plant, compares output with a reference, and applies control action under explicit dynamical assumptions; stability, delay, noise, observability, and convergence have mathematical meanings. Coding-agent loops borrow negative-feedback language, but the "plant" includes a mutable repository and tools, the controller is a stochastic language model, observations can be incomplete or adversarial, objectives are semantic, and the state can change exogenously. A repeated model call is not evidence of convergence. Practical implications carried over from control theory are still sound: use truthful sensors/verifiers, define the controlled variable and tolerance, bound gain/retries, detect oscillation/no progress, expose state, and fail safe. Claims of "closed loop" should not imply classical stability guarantees.

### Loop engineering (emerging 2026 outer-operating discipline)

The clearest original practitioner statement found is Addy Osmani's June 2026 essay: stop prompting turn by turn and design the small system that prompts the agent; his example combines automation, isolated worktrees, skills, connectors, maker/checker separation, durable state, and a human inbox: https://addyosmani.com/blog/loop-engineering/ . His follow-up keeps human accountability at the outer boundary: https://addyo.substack.com/p/own-the-outer-loop .

The strongest evidence that the label is recent rather than long-established is the August 2026 exploratory paper "Loop Engineering: Building Blocks, Adoption, and Impact," which says practitioners began using the term in June 2026 and derives common elements from gray literature before mining repositories: https://arxiv.org/abs/2608.21884 . This is a primary research paper about the discourse, but its taxonomy is exploratory, not normative.

Secondary sources used only to triangulate emergence: IBM's July 2026 overview calls the practice emerging (https://www.ibm.com/think/topics/loop-engineering), and TechCrunch reported Boris Cherny's June 2026 public comments that agents increasingly prompt agents (https://techcrunch.com/2026/06/22/the-ai-world-is-getting-loopy/). These support term diffusion, not technical invariants.

OpenAI Symphony is a stronger primary implementation comparator than the commentary. Its draft service spec separates policy/configuration/coordination/execution/integration/observability layers, uses a single authoritative orchestrator state, isolated issue workspaces, eligibility reconciliation, bounded concurrency, retries/backoff, stall detection, structured logs, and a detailed conformance matrix: https://github.com/openai/symphony/blob/main/SPEC.md . Symphony is broader and tracker-driven, so not every feature belongs in Agent Factory's bounded Human-request loop.

## Strongest source-backed practices (synthesis, not a claimed standard)

1. **A narrow, machine-inspectable goal and stop condition.** Anthropic recommends evaluator-optimizer only with clear criteria; OpenAI recommends retry/action thresholds and human intervention. A model saying "done" is evidence only of its claim.
2. **Independent and/or deterministic verification.** Separate maker and evaluator to reduce self-grading bias; prefer environment evidence such as tests where authority permits. Anthropic's 2026 harness work explicitly reports self-evaluation leniency and uses a separate evaluator. Human judgment remains necessary for subjective or high-risk acceptance.
3. **Finite resources and explicit escalation.** Bound semantic iterations, elapsed time, actions/tokens/cost, repeated failures/no-progress, and irreversible actions. Stop into a typed Human state rather than silently continuing.
4. **Durable, externally inspectable state and exact identities.** Persist task/run/attempt/session/workspace/artifact identities and transition reasons; make dispatch/retry idempotent across crash windows. Anthropic's long-running-agent work uses structured handoff artifacts; Symphony specifies single-authority orchestration and reconciliation.
5. **Isolation and artifact provenance.** Give concurrent tasks isolated workspaces, preserve a baseline, and bind checks/review to the exact artifact being accepted. OpenAI's 2026 Agents SDK announcement emphasizes controlled sandboxes, externalized state, snapshot/rehydration, and separation of credentials from model-executed compute: https://openai.com/index/the-next-evolution-of-the-agents-sdk/ .
6. **Least authority and a human outer loop.** Layer sandbox/tool/approval boundaries, treat external or irreversible effects separately, and escalate risk choices. OpenAI's practical guide calls for layered guardrails and human intervention at failure thresholds and high-risk actions.
7. **Useful observations, not just liveness.** Record structured transition events, last meaningful progress, phase latency, attempt/retry causes, token/tool/cost totals, artifact/evidence hashes, and terminal provenance. OpenAI's Agents tooling exposes tracing/evaluation; Symphony requires structured logs and operator-visible state.
8. **Context lifecycle is designed, not accidental.** Curate context and use compact structured handoffs; for very long work, evaluate fresh sessions/context resets against resuming one ever-growing conversation. Anthropic's context-engineering and long-running-harness reports are primary evidence: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents and https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents .
9. **Evaluate the loop as a system.** Use representative tasks and ablations, track false acceptance, false escalation, cost, time, and recovery behavior. Do not optimize only model pass rate. OpenAI's tracing/evals guidance and Anthropic's one-component-at-a-time harness simplification support this.

## Repository evidence inspected

- `skills/agent/SKILL.md`: common topology, file handoff, background execution, liveness, timeout/retry, and Human-led testing contract.
- `skills/agent/references/{main,work,review,inquery,loop}.md`: authority and role separation. Work cannot test; Review is independent and static; Main owns tests and Human decisions.
- `skills/agent/scripts/agent_exec.py`: filesystem safety, per-Agent session/run lifecycle, exact-session resume, JSONL event collection, heartbeat, cancellation/reconciliation, result envelope, Work/Review receipt schemas and validation.
- `skills/agent/scripts/agent_loop.py`: Work/Review state machine, budgets, finding fingerprints, test-evidence ingestion, crash-window recovery, status/cancel/reconcile.
- `tests/test_agent_exec.py`, `tests/test_agent_loop.py`, `tests/test_agent_role_contracts.py`: static inspection of current coverage. Tests were not run.

## Concrete strengths

### Strong runtime and identity boundaries

- `agent_exec.create_run` copies each delegated request into a run directory, hashes it, emits an exact result-path schema, and creates atomic state/heartbeat files.
- `build_codex_command` resumes the exact stored Codex session identifier and reasserts project root and sandbox. There is no `resume --last` ambiguity.
- `agent_loop._verify_session_identity` pins stable Work and Review session IDs and rejects a shared session. Work and Review are serialized, not concurrent.
- Work/Review receipts have exact fields and bind request hash, run ID, latest reviewed Work run, decision semantics, and a proof that those roles did not run tests. `validate_receipt` rejects noncanonical and symlinked managed paths.

### Explicit finite state and fail-closed outcomes

- Loop budgets cover Work turns, Review turns, revisions, elapsed time, and unchanged blocking-finding rounds; contradictory budgets are rejected.
- Terminal states distinguish completion, Human decision, failure, and cancellation. Child non-completion does not become an automatic revision.
- Reused finding IDs cannot materially change their core problem/correction fields; unchanged blocking findings trip a circuit rather than spin indefinitely.
- Approval is stopped when required test evidence is absent or its supplied exit status is nonzero. The policy must be explicit; it is not inferred from prose.

### Crash/liveness mechanics are materially better than a shell loop

- State writes are atomic and loop/session transitions use file locks.
- `_set_pending_dispatch` records intent before child dispatch, and `_recover_pending_dispatch` attempts to adopt a child created across an ACK crash window.
- Heartbeats are supervisor-authored, correctly treated as process liveness rather than model progress. Startup and turn timeouts are distinct.
- A managed attempt is retried only if Codex never started; a started semantic turn is not blindly replayed. This is a sound default for potentially visible or irreversible actions.
- Reconciliation advances at most one semantic phase. Cancellation is designed to be idempotent at the loop level.

### Authority design is unusually clear

- The loop cannot silently grant testing, deployment, commit, external transmission, or destructive authority. Static Review cannot trigger revisions for advisory preferences. Missing Human choices stop rather than get guessed.
- Inquiry material, runtime state, Specifications, and Skills are separated. This prevents exploratory notes from becoming implicit acceptance truth.

## Missing invariants and unsafe failure modes

### P0 — test evidence is stale-by-construction and not subject-bound

`agent_loop.start_loop` copies `--test-evidence-file` before initial Work. `_copy_test_evidence` validates only seven syntactic fields (`authorizationReference`, `command`, `actor`, `timestamp`, `exitStatus`, `outputHash`). `_advance_review` later accepts any stored evidence with `exitStatus == 0`, including after one or more revisions.

Missing bindings: loop ID, original request hash, latest Work run ID, repository/worktree identity, baseline/current tree or diff hash, command-output artifact path, authorization scope, and freshness relative to the accepted revision. `outputHash` is regex-checked but no output bytes are copied or hashed by the runtime. `authorizationReference` is an arbitrary nonempty string. This can yield `completed` for code the test never exercised.

This conflicts with evidence-gated loop practice and with the loop contract's wording that evidence "shows success." It does **not** authorize letting Work or Review run tests. The bounded safe response is to stop calling pre-start metadata acceptance proof; completion with `required` evidence should remain a Human gate until evidence can be attached after the exact latest Work artifact is known.

### P0/P1 — no exact change/artifact identity; all roles share the live dirty workspace

The Work receipt's `changedPaths` is Agent-authored and only checked for relative syntax. The runtime does not compare it with the actual diff, record a baseline, or hash the resulting artifact. Review reads "current changed files" from the shared project workspace. Concurrent Human edits or other agents can be attributed to the Work run, omitted changes can escape review, and later mutations can invalidate an earlier approval.

The design explicitly says Work edits the current Git workspace, so automatic worktrees would be a product-policy change, not a silent fix. At minimum the result must accurately say Review approved a live workspace observation rather than an immutable patch. If isolated workspaces are adopted later, Main should explicitly own merge/application into the Human workspace.

### P1 — pending dispatch recovery uses a non-unique correlation

`pendingDispatch` stores role, Agent ID, request-content hash, ordinal, and revision flag, but no generated dispatch ID. `_recover_pending_dispatch` scans run states and matches only request hash plus role (the selected Agent narrows the scan). Repeated identical generated requests or a retried send can produce zero or multiple matches, turning a recoverable ACK loss into terminal `dispatch_outcome_unknown` or `dispatch_binding_ambiguous`. The manager's `submit/send` API has no caller-provided idempotency key.

An exact `dispatchId` persisted in loop intent and copied into child run state would make creation/adoption one-to-one. A uniqueness test must cover crash before ACK, retry, duplicate call, and two byte-identical revision requests.

### P1 — cancellation can leave descendants and PID identity is weak

`run_codex_attempt` launches Codex without a new process session/group; `terminate_process` signals only the direct Codex PID. Tool subprocesses can outlive cancellation or timeout. `command_cancel` and `command_reconcile` trust numeric PIDs and use `os.kill(pid, ...)`/`pid_alive` without a process birth-time or command identity. PID reuse creates a low-frequency but severe risk of treating or signaling an unrelated process.

Use a dedicated process group/cgroup (platform permitting), persist a process identity fingerprint, and reconcile conservatively. Tests should use controlled child/grandchild fixtures rather than invoking Codex.

### P1 — persisted state is only minimally schema-validated

`agent_loop._read_state` checks four bindings, then later code indexes mutable nested fields. `agent_exec.load_session` validates only a subset of session identity. Corruption or local tampering can alter counters, deadlines, paths, execution settings, or Agent IDs and surface as generic runtime failure or unintended execution. Atomicity prevents torn writes but not semantically invalid state.

Define an exact versioned state schema plus transition invariants: monotonic counters/version/timestamps, canonical paths below the expected root, legal phase/status/current-child combinations, immutable identity/execution fields, and budget consistency. Validate before action; preserve the corrupt file and fail closed with a typed code.

### P1/P2 — completion artifacts are mutable and unbounded

The runtime checks that `result.md` exists and is nonempty but records no digest/size bound. Receipt JSON is size-bounded when validated but its digest is not sealed into terminal state. JSONL event lines are individually capped at 1 MiB, while the total event file and `stderr.log` can grow without bound. A terminal result/receipt can change after completion without state revealing it.

Record result/receipt hashes and byte counts at terminal publication, reject later mismatch, cap or rotate total log bytes, and surface truncation explicitly. Do not discard the raw source path needed for audit.

### P2 — liveness is observable; semantic progress and cost are not

Status exposes state plus heartbeat, and raw JSONL is preserved, but the loop surface lacks last meaningful event time, per-phase latency, queue/lock wait, retry chronology, tool/model/token/cost counts, context size/compactions, evidence/artifact hashes, and transition history. A live but spinning Codex process looks healthy. There is no stall timeout distinct from total turn timeout. `reconcile` reports `stale-alive` indefinitely while a PID exists.

Add bounded structured transition records and derived counters without making telemetry correctness-critical. A stall policy should stop/escalate, not replay a started semantic turn.

### P2 — finding lifecycle is incompletely enforced

Review receipts contain `resolvedFindingIds`, but `_advance_review` does not require a previously pending finding that disappears to appear there. Work only self-asserts `addressedFindingIds`; it need not correspond to an actually changed location. The next Review can drop a finding and approve without a machine-checkable resolution trail.

Require follow-up Review to partition prior pending IDs into still-present vs. explicitly resolved; reject unknown resolved IDs and stable-ID reuse after resolution unless a documented reopen transition exists. Static Review remains the semantic authority; the runtime enforces only lifecycle consistency.

### P2 — context strategy is fixed to resume, not evaluated

Exact session resume is a correctness strength and an explicit repository requirement. It also accumulates Work and Review histories over revisions. Anthropic reports that for some long tasks, fresh context plus structured handoff outperformed compaction/resume. With only two revisions by default, this is not urgent. Treat a reset/handoff mode as a future evaluated option, not a presumed best practice; changing it would conflict with today's exact-session-continuity contract.

### Scope gaps, not defects

- No schedule/event trigger, discovery/triage queue, tracker integration, or bounded concurrency pool. `reconcile` must be called externally. This is a finite Human-started lifecycle kernel, not a proactive service like Symphony.
- No automated deterministic verifier. This follows the Human-owned testing contract. Static independent Review reduces self-bias but cannot prove runtime behavior.
- No isolated worktree. This follows the deliberate "edit current Git workspace" contract and should change only through a Human-owned product decision.

## High-value tests (proposed; not run)

Priority order emphasizes false completion, unintended execution, and recovery.

1. **Reject stale/unbound evidence:** evidence created before Work, evidence bound to another request/run/tree, and evidence reused after revision must never yield `completed`; validate copied output bytes against `outputHash` if that field remains.
2. **Finding lifecycle partition:** a follow-up Review that silently drops a pending ID fails; exact resolved IDs pass; unknown/resolved-and-current overlap fails; reopening has explicit semantics.
3. **Exact dispatch idempotency:** simulate crash after child run creation but before ACK/state update, then reconcile; duplicate retry adopts the same run; identical request bodies in different ordinals cannot be confused.
4. **State transition property tests:** generate legal/illegal combinations of status, phase, current child, pending dispatch, counters, deadline, and terminal reason; only legal transitions persist and version is monotonic.
5. **Artifact mutation:** mutate result/receipt/current workspace after terminal capture and require a typed hash mismatch rather than continued approval.
6. **Process-tree cancellation:** a fake worker starts a child and grandchild; cancel/timeout terminates the owned group and never signals a reused/unrelated PID.
7. **Worker/reconcile matrix:** pre-start crash is retried once; post-start crash is terminal; missing/malformed event, session mismatch, stale-dead heartbeat, stale-live heartbeat, queue wait, timeout, and cancellation each produce the declared state/error exactly once.
8. **Log quotas:** oversized single events, many valid events exceeding aggregate quota, and unbounded stderr are truncated/stopped deterministically with observable metadata.
9. **Workspace concurrency provenance:** mutate an unrelated file between Work and Review and demonstrate either isolation or an explicit provenance failure; verify claimed `changedPaths` against captured artifact identity.
10. **Crash points around every atomic transition:** before/after intent write, child creation, ACK, dispatched-child record, terminal write, evidence attachment, and cancel. Reconciliation must be idempotent from each point.
11. **Observability contract:** every transition records loop/run/attempt/session IDs, previous/new phase, reason, timestamp, and relevant artifact hash; secret-bearing prompt/event content is not copied into summary fields.
12. **Context-growth evaluation (not ordinary unit test):** representative two-revision tasks compare exact resume with fresh-session structured handoff for false approval, token cost, latency, and completion. This requires separate Human test authorization.

Current tests cover receipt field/path binding, sandbox propagation, schema path, budget validation, happy Work/Review approval, required-evidence absence, unchanged-finding stop, child terminal mapping, and two pending-dispatch cancellation cases. They do not exercise real worker lifecycle, heartbeat/reconcile behavior, process cancellation, aggregate event limits, state corruption, evidence subject binding, artifact provenance, resolved-finding lifecycle, or positive/ambiguous dispatch recovery.

## Bounded change sequence that preserves current role/test authority

1. **Truthful evidence semantics first.** Prevent pre-start evidence from authorizing `completed` for a later artifact. Either (a) always stop `required` loops for Human acceptance and report supplied evidence as an unverified attestation, or (b) add a Main/Human-owned post-Work evidence attachment transition bound to exact request/Work/artifact hashes. Do not let Work or Review execute tests.
2. **Exact dispatch correlation.** Add a runtime-validated `dispatchId`/idempotency key to submit/send and pending state; recovery matches it exactly. This is internal lifecycle hardening, not expanded authority.
3. **Seal terminal provenance.** Record byte sizes and SHA-256 for result/receipt/evidence, validate canonical paths and immutable identity fields, and report what an approval actually covered. Add aggregate log quotas.
4. **Enforce finding lifecycle.** Make prior pending IDs machine-accounted as current or resolved on every follow-up Review.
5. **Harden process ownership.** Use owned process groups plus identity fingerprints; add a stall-to-Human/failed transition without replay.
6. **Add compact structured observability.** Transition log, phase durations, last progress, retry reason, resource counters, and artifact/evidence bindings. Keep raw model content separate and access-controlled.
7. **Defer worktree/scheduler/test-oracle changes.** These require Human product choices because they alter the current-workspace route, proactive scope, or test authority. Evaluate them in a separate Inquiry/Specification rather than smuggling them into hardening.

## Contradictions and limitations

- The strongest coding-loop examples use tests as a deterministic stop signal. Agent Factory expressly prohibits Work and Review from all verification and reserves testing to Human/Main authorization. Therefore the runtime cannot honestly claim the same autonomous verification strength without a contract change. Independent static Review is valuable but not equivalent.
- Anthropic's long-horizon guidance favors fresh contexts and structured handoffs in some experiments; Agent Factory requires exact resumable sessions. Both can be rational at different horizons. No repository-specific experiment was authorized, so there is no evidence that reset would improve this bounded two-revision loop.
- Worktree isolation is widely recommended for concurrent autonomous work, but this repository intentionally targets edits in the Human's current dirty workspace. Isolation changes delivery semantics and needs a Human-owned decision.
- Recent "loop engineering" sources are unusually new. The label has practitioner momentum and two recent exploratory papers, but there is not yet a stable standards body, long-term field data, or consensus vocabulary. Vendor posts describe their own systems and may overgeneralize.
- Static inspection can identify protocol gaps but not establish incidence or exploitability. Tests were prohibited and not run; no process, crash, concurrency, or symlink experiment was performed.

## Smallest useful follow-up Inquiry

Design only the evidence/provenance state transition for a `required` loop under the existing Human/Main test authority: define who may attach evidence, when, the exact latest-Work/workspace subject binding, output retention/hash rules, whether a stopped loop can resume, and what terminal wording is truthful. That focused design resolves the highest-risk false-completion issue without deciding worktrees, schedulers, automated tests, or broader factory orchestration.

---

# Follow-up: bounded loop hardening design (2026-08-28)

Boundary: convert the risks above into an implementable, backward-conscious design for the existing `agent_exec.py` + `agent_loop.py` runtime. This is design only. No product files were changed and no test or verification command was run.

## Additional primary-source anchors

- OpenAI Symphony's draft service spec uses a single authoritative orchestrator state, reconciliation before dispatch, per-issue workspace identity, stall detection, structured logs, typed configuration, and a conformance matrix. It also distinguishes worker success from tracker-level completion: https://github.com/openai/symphony/blob/main/SPEC.md . Agent Factory should borrow exact durable transition/correlation ideas, not Symphony's broader tracker/scheduler product scope.
- Temporal's architecture makes the durable-workflow distinction explicit: deterministic orchestration is replayed, while fallible side-effecting activities must be idempotent or non-retryable: https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md . Its retry documentation warns that Activities can execute again and therefore require idempotence, while whole workflows do not retry by default: https://github.com/temporalio/documentation/blob/main/docs/encyclopedia/retry-policies.mdx . This supports an exact dispatch key and Agent Factory's existing rule not to replay a started semantic turn.
- SLSA's attestation model separates a `subject` artifact identity from a typed `predicate` describing it: https://slsa.dev/spec/v1.1/attestation-model . The analogy is useful but limited: the proposed local evidence is an unsigned Main/Human attestation, not SLSA provenance or a supply-chain trust claim.
- Git documents that `git write-tree` represents the index, not the live worktree unless the index is updated first: https://git-scm.com/docs/git-write-tree.html . It is therefore insufficient for Agent Factory's current dirty-workspace route. `git ls-files` can enumerate cached and untracked/non-ignored working-tree paths with NUL termination: https://git-scm.com/docs/git-ls-files .
- Python exposes new-session/process-group creation and POSIX group signaling; Linux documents that numeric PID reuse makes traditional signaling racy and that pidfds avoid that race: https://docs.python.org/3/library/subprocess.html , https://docs.python.org/3/library/os.html , https://www.man7.org/linux/man-pages/man2/pidfd_send_signal.2.html . `/proc/<pid>/stat` field 22 is process start time since boot: https://www.man7.org/linux/man-pages/man5/proc_pid_stat.5.html .
- OpenAI's Agents SDK announcement treats externalized state, sandbox snapshot/rehydration, and separation of credentials from model-executed compute as durable execution primitives: https://openai.com/index/the-next-evolution-of-the-agents-sdk/ .

## Proposed target lifecycle

The target remains one Human-started bounded loop. It does not add scheduling, automatic testing, deployment, commits, worktrees, or new Agent roles.

```text
start
  -> Work (same managed Work session)
  -> capture exact git-visible workspace snapshot
  -> Review (different managed Review session, snapshot-bound)
     -> blocking: revision -> capture a new snapshot -> Review
     -> approved + policy=not-required: recheck snapshot -> completed
     -> approved + policy=required + no matching evidence:
          active / awaiting-evidence (no child running)
             -> Main/Human runs an already-authorized command
             -> attach evidence + output
             -> recheck request, latest Work, Review, output, snapshot
             -> completed
```

`awaiting-evidence` is a resumable orchestration phase, not a model turn and not a new authority grant. The total loop deadline remains in force. `cancel` works in this phase. `reconcile` is a no-op status transition while evidence is absent; it must not fail because `currentChild` is null.

Why not terminal `needs-human-decision` and later reopen it: terminal reopening complicates every existing terminal invariant and inbox consumer. A nonterminal phase accurately says that a predeclared required input is pending. If the deadline expires, snapshot mutates, evidence is invalid, or evidence attachment requires an unspecified choice, the loop becomes terminal `needs-human-decision`.

## Phase 0: immediate false-completion safety rule

This rule is safe to apply before the fuller evidence feature:

- Any evidence supplied to existing `start --test-evidence-file` is labeled `legacyPreWorkEvidence` and **never** satisfies `testEvidencePolicy == required`.
- On an approved Review, an old loop with only pre-Work evidence stops `needs-human-decision` with code `evidence_not_bound_to_latest_work`. It must never return `completed` from that evidence.
- New CLI help deprecates `--test-evidence-file` at `start`; retain parsing so callers do not fail unexpectedly. The ACK includes a non-secret warning field. Remove the flag only in a later major schema/CLI version.
- Existing terminal loops are not reopened or retroactively reclassified. Existing active `not-required` loops retain their behavior. Existing active `required` loops get the fail-closed rule above on their next transition.

This is a safety correction, not a Human product choice: current evidence cannot support the claim the runtime makes.

## Phase 1: reproducible workspace subject

### Why a custom manifest instead of `git write-tree`

The current contract edits the live working tree, commonly with unstaged and untracked files. `git write-tree` hashes only the index. Mutating the index to manufacture a tree would alter Human state and is outside the runtime's authority. A read-only manifest using `git ls-files` plus Python hashing is the smallest standard-library/Git implementation.

### Algorithm `af-git-visible-workspace-v1`

Preconditions:

1. Run `git rev-parse --show-toplevel` with `shell=False`; its resolved path must equal `projectRoot`.
2. Run `git ls-files -z --cached --others --exclude-standard --`. Reject nonzero exit, unmerged index entries (`git ls-files -z --unmerged` nonempty), duplicate paths, absolute paths, `..`, NUL anomalies, and non-UTF-8 paths with a typed `workspace_snapshot_unsupported` error.
3. Exclude only operational paths that mutate because the loop is observing itself: `.agent-factory/agent/**` and `.agent-factory/inquery/**`. Do not exclude `.agent-factory/specification/**`, `sync.json`, or other project artifacts if Git lists them.
4. Ignored files are intentionally outside `v1` because hashing them may capture credentials, environments, caches, and unbounded build outputs. The subject must be named **git-visible workspace**, not entire filesystem/workspace.

For every sorted path, use `os.lstat` and record one canonical entry:

```json
{"path":"relative/utf8/path","type":"file","executable":false,"bytes":123,"sha256":"..."}
{"path":"relative/link","type":"symlink","targetBytesBase64":"...","sha256":"..."}
{"path":"tracked/deleted","type":"missing"}
```

- Regular-file digest is SHA-256 of exact bytes. Record only Git-significant executable state (`st_mode & 0o111`), not owner/group/mtime.
- For symlinks, hash and store the raw link-target bytes; never follow the target.
- A listed directory indicates a submodule/gitlink or unsupported file shape. `v1` fails `workspace_snapshot_unsupported` rather than silently under-hashing it. Submodule support is deferred.
- Compare pre-read and post-read `lstat` identity/type/size/mtime-ns/ctime-ns for every entry. If anything changes, discard the whole manifest and retry once. A second change fails `workspace_mutating`; it never produces an acceptance subject.
- Also record resolved project root and `HEAD` object (`git rev-parse --verify HEAD`, or JSON null for unborn HEAD) as metadata. HEAD is diagnostic; entry contents remain the acceptance subject.

Canonical subject bytes are UTF-8 JSON with sorted keys, compact separators, no floating point, and the exact object:

```json
{
  "algorithm": "af-git-visible-workspace-v1",
  "entries": [],
  "head": "<40-or-64-hex-or-null>",
  "projectRoot": "/resolved/root"
}
```

`workspaceSha256 = sha256(canonical_subject_bytes)`. The stored snapshot envelope adds `snapshotId`, `capturedAt`, `latestWorkRunId`, `originalRequestSha256`, `manifestPath`, `manifestSha256`, and `workspaceSha256`. Store it atomically under the loop directory `snapshots/<snapshot-id>.json` with mode 0600. `snapshotId` is a generated opaque ID; equality is decided by `workspaceSha256`, not timestamp or ID.

### Capture and mutation checks

- Capture automatically in `_advance_work` only after the Work receipt/request/session bindings pass and immediately before Review dispatch intent is persisted.
- Put `snapshotId`, `workspaceSha256`, algorithm, and manifest path in the Review request and `pendingDispatch`.
- Add `reviewedWorkspaceSha256` to new Review receipt schema and state binding. Before accepting a completed Review, recapture and require the same `workspaceSha256`. If it differs, stop `needs-human-decision` with `review_subject_mutated`; do not send an automatic Work revision because the source of mutation is unknown.
- Immediately before loop completion, recapture again and require equality with both the approved Review and accepted evidence (when required).
- A later Work revision always invalidates prior snapshots, Review approval, and evidence by replacing `latestWorkRunId` and `latestWorkSnapshot`.

This detects ordinary concurrent edits and TOCTOU windows around Review/evidence. It does not defend against a privileged adversary rewriting files between individual reads while preserving metadata, kernel compromise, or ignored-file influence.

### Snapshot compatibility and product decision boundary

No Human product choice is needed to add an accurately named Git-visible subject and fail closed on mutation. A Human product/risk choice **is** required before claiming that ignored files, nested repositories/submodules, generated dependencies, or the full test environment are covered. Possible future policies are an explicit include allowlist or isolated worktree/container snapshot. `v1` must not silently include ignored `.env`/cache data.

## Phase 2: post-Work Main/Human evidence

### CLI

Add one command; it does not execute the test:

```text
agent_loop.py evidence \
  --work-agent ID --loop-id ID \
  --actor main|human \
  --evidence-file PATH --output-file PATH
```

The actor is routed the same way as existing managed runtime actors; it is an auditable assertion, not cryptographic authentication. The Main/Human separately runs the authorized command. `evidence` only validates, copies, hashes, and attaches artifacts while holding `.loop.lock`.

Input evidence schema (`agent-loop-test-evidence`, version `0.2.0`, exact fields):

```json
{
  "schemaVersion": "0.2.0",
  "kind": "agent-loop-test-evidence",
  "loopId": "loop-...",
  "actor": "main",
  "authorizationReference": "human message/run reference",
  "command": "exact command text that was authorized and run",
  "startedAt": "RFC3339 UTC",
  "finishedAt": "RFC3339 UTC",
  "exitStatus": 0,
  "subject": {
    "originalRequestSha256": "...",
    "latestWorkRunId": "run-...",
    "snapshotId": "snapshot-...",
    "workspaceAlgorithm": "af-git-visible-workspace-v1",
    "workspaceSha256": "..."
  },
  "output": {"sha256": "...", "bytes": 1234}
}
```

Attachment checks, in order:

1. Loop is nonterminal, policy is `required`, actor and loop IDs match, latest Work and snapshot exist, and phase is `review-running` or `awaiting-evidence`. Reject evidence during Work because its subject may still change.
2. Evidence request hash, Work run, snapshot ID/algorithm/hash match current state exactly.
3. `startedAt >= snapshot.capturedAt`, `finishedAt >= startedAt`, `finishedAt <= now + 5 minutes` clock-skew allowance, and Work state `finishedAt <= startedAt`. Timestamp is attested context, not trusted proof.
4. Read output with no symlink following and a finite default cap (proposed 8 MiB). Compute bytes/SHA-256 and require exact match. Copy descriptor and output atomically to `evidence/<evidence-id>/`; never retain the caller's mutable path as acceptance material.
5. Recapture workspace and require the same subject hash. This catches changes after the reviewed snapshot and during/between test and attachment, provided they affect the defined subject.
6. Store a runtime-generated evidence envelope with copied artifact paths/hashes and `attachedAt`. An `exitStatus != 0` may be retained as failed evidence for inspection but cannot satisfy acceptance.

Only one accepted evidence record may bind a latest Work run; a byte-identical repeated attachment returns the existing record. A different record supersedes only failed evidence. Replacing successful evidence requires an explicit `--replace-evidence` future design and is deferred; silent replacement weakens auditability.

### Truthful claim

Even after these checks, the runtime proves only: a Main/Human actor attested that a named command produced this copied output/exit status while the Git-visible source subject before Review and at attachment/finalization remained identical. It does not prove the command actually ran, authorize the command, cover ignored environment files, or establish correctness. Result text should say `Main/Human test attestation accepted for snapshot ...`, not `tests proved success`.

Cryptographic signatures, OS-level command supervision by Main, CI-issued attestations, and external identity are separate product/security designs.

## Phase 3: exact dispatch correlation and idempotency

### State/API changes

Generate `dispatchId = dispatch-<uuid>` before every child submit/send and persist it in `pendingDispatch`:

```json
{
  "dispatchId": "dispatch-...",
  "role": "review",
  "agentId": "review-loop",
  "ordinal": 1,
  "revision": false,
  "requestPath": ".../requests/review-1.md",
  "requestSha256": "sha256 of this child request",
  "originalRequestSha256": "loop request hash",
  "reviewedWorkRunId": "run-work-1",
  "workspaceSha256": "latest snapshot when role=review"
}
```

Add optional `--dispatch-id` to `agent_exec.py submit/send`; `agent_loop.py` always supplies it. Persist it in child run state and return it in ACK/status. Under an Agent-level `.dispatch.lock`:

- no existing ID: create exactly one run and bind the full request tuple;
- existing ID + byte-identical tuple: return the original ACK/run ID with `deduplicated: true` and do not create a run;
- existing ID + different tuple: fail `dispatch_id_collision`;
- IDs are unique within an Agent session. The tuple includes role, actor, child request hash, receipt/original request hash, reviewed Work run (if any), and Agent ID.

### ACK crash handling

After persisting intent, loop dispatch calls runtime with the same ID. If the call outcome is unknown, leave `pendingDispatch` intact. On reconcile:

1. Search only by exact Agent + `dispatchId`.
2. If found, verify the entire tuple and adopt that run.
3. If absent, call submit/send again with the same ID; the manager creates it once.
4. Never match by content hash alone and never generate a new dispatch ID for recovery.

Crash after run creation but before worker PID publication is handled in the *same run*. A duplicate dispatch returns that run and asks runtime reconciliation to inspect its heartbeat/session/process state. It does not spawn another semantic run. Only a proven never-started attempt can be re-launched, preserving the current retry rule.

For the new-Agent first submit, serialize session creation with an Agent-root lock and make same-dispatch duplicate submission return the created session/run rather than `agent_exists`. This closes the initial Work ACK window as well as follow-up sends.

This is an internal correctness change and does not require a Human product choice.

## Phase 4: Review finding ledger

Add loop-state fields:

```json
"findingLedger": {
  "known": {"REV-001": {"fingerprint": "...", "firstReviewRunId": "..."}},
  "pending": ["REV-001"],
  "resolved": {"REV-000": {"resolvedByReviewRunId": "..."}}
}
```

Validation for each Review receipt:

- Initial Review: `resolvedFindingIds` must be empty. Every current finding ID becomes known; blocking IDs become pending.
- Follow-up Review: `resolvedFindingIds` must equal `priorPending - currentBlockingIds`. It may not contain an unknown, advisory-only, already-resolved, or still-current ID.
- Current blocking findings may include new IDs found in the revision. Existing IDs must preserve the current material fingerprint invariant. A resolved ID may not reappear; a genuinely regressed problem gets a new stable ID. Reopening semantics are deferred because they need reviewer protocol/UI decisions.
- Before dispatching revised Work, its receipt must still list every prior pending ID in `addressedFindingIds` (existing rule). This proves only accounting, not correction.
- An approved Review requires `currentBlockingIds` empty and exact resolution accounting. Advisory IDs are tracked separately only if useful for reporting; they never enter pending or trigger Work.

This is a protocol invariant consistent with the existing Review contract, so it does not require a product choice.

## Phase 5: versioned loop-state invariants

Do not reuse `agent_exec.SCEMA_VERSION` for every artifact. Introduce independent constants, for example `LOOP_STATE_SCHEMA_VERSION = "0.2.0"`, `EVIDENCE_SCHEMA_VERSION = "0.2.0"`, and retain existing child receipt versions until deliberately migrated.

### Required immutable state binding

On every read before action, validate exact types/keys and canonical locations for:

- loop ID, project root, Work/Review Agent IDs (distinct), original request path/hash;
- execution settings, budgets, start/deadline timestamps;
- loop-state path derived from root/Work Agent/loop ID;
- child run IDs/roles/Agents/ordinals and session IDs;
- snapshot/evidence/dispatch paths below this exact loop directory with no symlinks.

### Legal phase/state combinations

- `work-running` / `review-running`: status `active`, exactly one matching `currentChild`, no `pendingDispatch`.
- `work-dispatching` / `review-dispatching`: status `active` (or `cancelling` during cancellation), exactly one matching pending intent; current child absent.
- `awaiting-evidence`: status `active`, no current child or pending dispatch, latest Review receipt approved, policy `required`, latest snapshot fixed.
- `cancelling`: optional current child or pending intent; no new semantic dispatch.
- terminal: phase equals terminal status, `currentChild` and `pendingDispatch` null, `finishedAt` and terminal reason present.

Counter invariants: all finite integers within budgets; `revisions == max(0, workTurns - 1)` after dispatch recording; `reviewTurns <= workTurns`; child-run counts/ordinals match counters; unchanged rounds cannot exceed Review turns. Snapshot Work run must equal `latestWorkRunId`; accepted evidence and approved Review must bind it.

Use a single transition function that validates old state, applies one named transition, increments existing `version`, updates timestamp, validates new state, and atomically writes. Append a bounded transition record containing old/new version, phase, reason, run/dispatch IDs, and relevant hashes. A hash chain helps detect accidental mutation but is not secure against a local writer that can rewrite the whole chain.

### Compatibility

- `0.1.0` terminal state remains readable and immutable.
- Active `0.1.0` is migrated under `.loop.lock` only by a pure, explicit `migrate_0_1_to_0_2` function. Preserve original bytes beside state as `state.v0.1.0.json` and record its SHA-256.
- Old pending dispatch without `dispatchId` cannot be made exactly idempotent retroactively. Perform the existing one-time role+hash adoption only when exactly one run matches; otherwise fail closed with the existing typed ambiguity error. New transitions thereafter use dispatch IDs.
- Old required evidence moves to `legacyPreWorkEvidence` and cannot satisfy acceptance. Old `not-required` behavior remains.
- Compact terminal response schema (`status`, `resultPath`) and current public command names remain unchanged; new CLI command/fields are additive.

## Phase 6: bounded artifact and log provenance

### Terminal artifact ledger

At terminal publication, read with `O_NOFOLLOW`, enforce caps, and record runtime-computed values:

```json
"artifacts": {
  "result": {"path": ".../result.md", "sha256": "...", "bytes": 1234},
  "receipt": {"path": ".../receipt.json", "sha256": "...", "bytes": 456},
  "events": {"path": ".../events.jsonl", "sha256": "...", "bytes": 789},
  "stderr": {"path": ".../stderr.log", "sha256": "...", "bytes": 12}
}
```

Suggested conservative defaults: result 2 MiB, receipt 1 MiB (existing), events aggregate 32 MiB/run, stderr 8 MiB/run, evidence output 8 MiB. Make caps initial-submit configuration persisted in the session; reject nonpositive/unreasonable values. Exact defaults are engineering tuning, not product direction.

If result/receipt exceeds a cap or changes between validation and sealing, the run fails `artifact_too_large`/`artifact_mutated`; it does not publish completion. Status/result/loop acceptance rechecks sealed result and receipt hashes. Atomic writes reduce torn-file risk; hashes expose later mutation. Do not claim immutability against the same OS user.

For event/stderr limits, do not silently truncate a semantic record and continue. Route both pipes through bounded drain threads; once an aggregate limit is crossed, terminate the owned Codex process group and fail `event_log_limit` or `stderr_log_limit`, while recording byte count and limit. A final small supervisor diagnostic should be stored separately so failure remains explainable without recursively exceeding the same log.

## Phase 7: Linux process-tree cancellation with portable fail-closed behavior

### Linux/POSIX fast path

- Launch Codex with `start_new_session=True`; its PID is the process-group ID. Persist `{pid, pgid, platform, bootId, startTicks, cmdlineSha256}` immediately. Read Linux boot ID and `/proc/<pid>/stat` starttime; hash `/proc/<pid>/cmdline` for diagnostics.
- The live worker owns the `Popen` object and is the preferred canceller. Verify PID/PGID identity, send `SIGTERM` with `os.killpg`, wait up to 5 seconds, then verify again and send `SIGKILL`. Always reap the leader.
- The manager signals the worker first. If stale reconciliation must signal Codex directly, it does so only after the persisted Linux identity matches current `/proc` and `os.getpgid(pid) == pgid == pid`. Any mismatch yields `process_identity_mismatch` and Human escalation; never signal the numeric PID/group.
- Where available in the running Python/Linux version, `os.pidfd_open` can pin the leader identity for live-process signaling. A pidfd cannot be persisted across manager restart, so `/proc` identity remains the restart-time guard. Process group signaling is still needed for descendants.

Limit: a descendant that deliberately calls `setsid()` escapes the group. Full containment needs a cgroup/systemd scope/container, which is beyond the standard-library design.

### Portability behavior

- POSIX non-Linux: still use a new session/group while the worker is alive and owns `Popen`; after worker loss, do not kill a stale numeric PID without a reliable birth identity. Return `cancellation_incomplete`/`needs-human-decision` with recorded PIDs.
- Windows: retain direct `Popen.terminate/kill` only for the direct child unless a later Windows Job Object implementation is selected. If descendants cannot be proven stopped, fail closed and report `process_tree_control_unavailable`; never report clean cancellation.
- WASI/unsupported: reject managed execution at submit with a typed platform error.

This hardening does not broaden Agent authority. It narrows which processes the runtime may signal.

## Threat cases and required behavior

| Threat/failure | Required response |
|---|---|
| Pre-Work successful test file reused after Work | Cannot satisfy required evidence; await new bound attestation or stop Human. |
| Evidence from another loop/request/Work run | Exact binding rejection; retain neither as accepted evidence nor completion input. |
| Source mutates during Review, test, attachment, or finalization | Snapshot mismatch; no automatic revision and no completion. |
| Ignored `.env` changes test outcome | `v1` explicitly does not cover it; result limitation remains visible. Full-environment policy deferred. |
| Two identical review request bodies | Distinct dispatch IDs; never correlate by body hash alone. |
| Crash after child run creation before ACK | Same dispatch ID adopts same run; no new semantic run. |
| Crash after Codex `thread.started` | No automatic replay; terminal failure/Human path under current policy. |
| Follow-up Review drops `REV-001` silently | Receipt rejected unless `REV-001` is exactly listed resolved. |
| Result or receipt changed after sealing | Hash mismatch; loop cannot accept it. |
| Event flood or stderr flood | Owned process group terminated at cap; typed failure, bounded diagnostic. |
| PID recycled before stale cancel | Identity mismatch; no signal sent. |
| Child forks grandchild in same group | TERM/KILL reaches group. |
| Child escapes process group | Reported containment limitation; cgroup option deferred. |
| Loop state counter/phase/path tampered | Schema/invariant failure before action; original state preserved for inspection. |

## Phased implementation order and file impact

1. **False-completion guard** — `agent_loop.py`, `references/loop.md`, focused legacy evidence tests. Small and urgent.
2. **Snapshot module/functions** — preferably a small `workspace_snapshot.py` beside Agent scripts, called by `agent_loop.py`; no dependency outside Python stdlib + Git. Add snapshot fixtures/tests without running real test suites.
3. **Evidence CLI and awaiting phase** — `agent_loop.py`, loop contract, parser/status tests, evidence artifact fixtures.
4. **Dispatch ID** — `agent_exec.py` state/parser/ACK + `agent_loop.py` intent/recovery; crash-point unit tests using fake runtime.
5. **Finding ledger and state validator/migration** — `agent_loop.py`; table/property-style unit cases.
6. **Artifact/log seals and process ownership** — `agent_exec.py`; fake subprocess fixtures and platform-gated tests.
7. **Documentation/public status** — expose snapshot/evidence/provenance identifiers and truthful completion wording, while keeping detailed content out of compact terminal JSON.

Phases 2 and 3 should land together before advertising required evidence as acceptance-capable. Phase 1 can land independently.

## Acceptance tests (design; explicitly not run)

### Evidence/snapshot

1. `required` + legacy start evidence + approved Review never completes.
2. Bound evidence succeeds only for exact request/latest Work/snapshot/output; mutate each field independently and assert typed rejection.
3. Output hash/byte mismatch, symlink, nonregular file, oversized file, future timestamp, pre-Work timestamp, and nonzero exit cannot satisfy acceptance.
4. Modify a tracked file, non-ignored untracked file, executable bit, symlink target, or delete a tracked file between snapshot and Review/evidence/finalization; each changes `workspaceSha256`.
5. Changes only under runtime exclusions do not change the subject. Ignored-file change does not change it and the limitation flag remains in status/result.
6. Concurrent file mutation during hashing retries once then fails; snapshot files are canonical and reproducible for unchanged content.
7. Approved Review enters `awaiting-evidence`; status/reconcile are idempotent, cancel works, deadline expires, and valid attachment completes exactly once.

### Dispatch durability

8. Crash injection before intent, after intent, after run creation, after worker spawn, after ACK, and after child-record write. Reconcile produces zero or one child run as specified.
9. Duplicate same dispatch+same tuple returns original run; same ID+different tuple fails; identical body+different IDs produces distinct intended turns.
10. A started turn is never redispatched after missing ACK/heartbeat; only the same run's proven pre-start attempt may restart.

### Findings/state

11. Initial resolved IDs rejected; follow-up exact partition accepted; omitted, unknown, duplicate, current-and-resolved, and reopened IDs rejected.
12. Exhaustively exercise legal phase/current/pending/status combinations and counter boundaries; migration preserves hashes and makes legacy evidence non-accepting.
13. Tampered canonical path, Agent ID, project root, request hash, snapshot binding, or immutable execution field fails before any runtime call.

### Artifacts/logs/processes

14. Result/receipt mutation before and after sealing is detected; exact cap accepted and cap+1 rejected.
15. Event/stderr aggregate cap terminates a fake owned process and produces bounded typed diagnostics without deadlock.
16. Linux fake leader+child+grandchild in one group all terminate; an escaped-session fixture yields the documented limitation.
17. Simulated PID identity mismatch sends no signal. Non-Linux mocked capability path returns incomplete cancellation rather than false success.

These are unit/integration fixtures for runtime mechanics, not authorization to execute the repository's test suite now.

## Compatibility decisions summary

- Keep the current compact Agent terminal envelope and existing public lifecycle commands.
- Add `evidence`; deprecate but parse start-time evidence.
- Never reopen old terminal loops.
- Fail closed for old active required loops; preserve old not-required semantics.
- Use independent schema versions and explicit migration, not permissive optional-field reads.
- Preserve exact Work/Review managed sessions and static Review/test prohibitions.
- Describe the subject as Git-visible source, not a whole environment or immutable proof.

## Changes that do not need a Human product choice

- Preventing pre-Work evidence from completing later Work.
- Exact request/Work/snapshot/output binding and truthful attestation wording.
- Exact dispatch IDs and duplicate-return semantics.
- Receipt finding lifecycle accounting and state validation/migration.
- Runtime-computed artifact hashes/limits, bounded logs, safer process ownership, and fail-closed portability reporting.

These implement or tighten existing promises without expanding authority.

## Changes that remain deferred for Human decision

- Automatic execution of tests by Work, Review, or the loop.
- Which test command is authorized; signatures/external CI identity; whether Main should supervise command execution.
- Claiming ignored files, submodules, generated dependencies, containers, or the whole environment in the snapshot subject.
- Replacing the current dirty-workspace route with isolated worktrees and deciding merge/application semantics.
- Scheduler/discovery/tracker automation, deployment, commit/PR actions, or proactive external effects.
- Fresh context/session replacement instead of exact resume.
- Linux cgroup/systemd containment and Windows Job Objects beyond the standard-library baseline.

## Remaining unresolved decision and smallest follow-up

The design can be implemented safely with `af-git-visible-workspace-v1`, but required evidence may still depend on ignored environment files. The smallest follow-up is a Human decision on whether the acceptance claim is intentionally source-only (use `v1` as written) or must cover a declared environment allowlist/container identity. That decision should occur before documentation uses language broader than "Git-visible workspace subject."
