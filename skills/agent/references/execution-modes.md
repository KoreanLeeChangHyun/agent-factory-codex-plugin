# Execution modes

<a id="captured-routes"></a>

## 1. Captured routes

| Mode | Implementation | Completion |
| --- | --- | --- |
| `orchestrate` (orchestrator mode, new Main input default) | Main routes; managed Work for changes and research | Completed Work Goal and receipt with own checks; separate Verification only on explicit Human request |
| `direct` (worker mode) | Main directly | Appropriate Main checks |
| `work` | Managed Work | Completed Work Goal and receipt with own checks; separate Verification not requested |
| `plan` | Actual Work Plan collaboration mode only | Return plan; no execution or Verification |
| `verification` | Managed standalone Verification | Request-bound standalone receipt and findings; no repairs |
| `plan-work` | Actual Plan then default execution in the same Work thread | Completed Work Goal and receipt with own checks; separate Verification not requested |
| `work-verification` | Managed Work | Separate Verification pass or evidenced Human skip |
| `plan-work-verification` | Actual Plan then default execution in the same Work thread | Separate Verification pass or evidenced Human skip |

- Conversation and Human Interview always remain Main.
- The Human chooses between orchestrator mode (`orchestrate`) and worker mode (`direct`).
  In orchestrator mode Main keeps conversation, planning, Interview, requirement shaping,
  routing, reporting, commits and light lookups (a known file or fact). It delegates every
  project change and broader research to Work, sizing the Work model light (bounded,
  already-decided change) or heavy (multi-file, design or unknown cause) and retrying a
  failed light attempt once with the heavy profile. It adds Verification only when the
  Human explicitly requests it. In worker mode Main implements directly.
- An orchestrator brief is the short-term contract of its change, not a long-term work
  contract. The brief carries Goal, Scope (including what not to do), Done and Report, and
  its loop state is the project's record of it. A read-only brief needs no task-list JSON,
  announcement or long-term contract. Exact Explorer Document assignments use the existing
  task-list/task-ID binding, not prose path inference. Long-term work contracts
  remain the Human-selected multi-task procedure between the Human and Main (Convention's
  [work contracts](../../convention/references/work-contracts.md#scope)).
- Orchestrator mode is enforced per provider by tool permissions, not model choice. Main may
  read, write inside its own run directory, run `python3 <plugin-root>/scripts/*` of an
  installed Agent Factory copy and read-only Git (`status`, `diff`, `log`, `show`); it
  cannot edit implementation. It may perform an approved ordinary local commit through
  the [receipt-bound commit tool](role-exceptions.md#ordinary-local-commit); raw Git mutation stays denied.
  Bounded fact/link confirmation from existing context is direct, including web tools;
  multi-source analysis, specialist research and implementation remain delegated. Classify
  by purpose, responsibility and effect, never arbitrary time or file-count limits.
  The run's sandbox policy is unchanged, so delegated Work keeps its permissions.
  - Claude: `dontAsk` with an `--allowedTools` list and a `PreToolUse` hook on shell/edit tools.
    Explorer native Write/Edit permissions name exact assigned files; the hook also rejects
    symlink traversal. Main retains bounded web confirmation tools.
  - Codex: a session-flag `PreToolUse` hook (`runtime/tasks/orchestrator_guard.py`) on
    `Bash`, `apply_patch` and the sub-agent start tools. The runtime adds an exact-hash
    `hooks.state` trust entry to the user's Codex config on first use and fails the run if
    Codex does not trust the hook.
  - Antigravity: the same guard as a global plugin hook (`~/.gemini/config/plugins/
    agent-factory-<id>-guard/`). It is inert unless the runtime arms it through the
    `AGENT_FACTORY_ORCHESTRATOR_GUARD` environment of an orchestrate Main run.
- Work may start only read-only exploration sub-agents; `capabilities` reports the result
  as `workSubagents`.
  - Claude: a PreToolUse hook allows only `Explore`.
  - Codex: `none`. The model can choose no sub-agent type and sub-agents inherit the parent's
    sandbox, so none is read-only. Work carries Main's hook definition (Codex keeps one trust
    hash for session-flag hooks), armed with Work rules that deny `spawn_agent` and
    `resume_agent`. A hook is a guardrail, not a complete boundary: a shell command that
    launches another agent CLI and the legacy `codex exec` backend are not covered.
  - Antigravity: the managed agent lists no sub-agent tool.
- Selecting a mode does not satisfy the independent Human approval gate or expand
  execution permissions.
- Composer actions send the current draft through Main immediately and are never persisted.
  Ordinary Enter/send always captures direct, even after restoring old saved modes.
  Queued messages retain their action; different actions must never merge.
- Main preserves an active task's route when handling conversational steering.

<a id="runtime-interface"></a>

## 2. Runtime interface

- `exec.py submit/send --task-mode MODE` snapshots the route. New Main requests without a flag capture `orchestrate`;
  persisted runs with no mode use `work-verification`. Explicit flags participate in the
  immutable dispatch tuple.
- `loop.py start` without `--task-list-file`/`--task-id` is the orchestrator brief route: the
  runtime derives one task (title from the brief's first line) so the panel shows it; no
  announcement check applies. Announced lists keep their full binding contract.
- Main performs `direct` work itself; do not create a direct-mode loop. `orchestrate` is
  Main-only: Main starts `loop.py start --task-mode work` (or a verification route on
  explicit request) and never submits Work with `--task-mode orchestrate`.
- `loop.py start --task-mode work --work-agent ID --request-file PATH` (also `--task-mode plan-work`) needs no Verification identity. Its completed Work
  receipt ends the loop with terminal reason `work-completed`. Main acknowledges the bound result/receipt and reports without reviewing implementation
  or rerunning checks.
- Work-bound verification modes additionally require `--verification-agent ID`. Failure revises the same Work
  session, then reuses the same Verification session and binds its receipt to the new
  exact Work run. No planning role or extra Agent exists.
- A task gets at most `--max-revisions` Work revisions (default 3; `0` is unlimited). The next
  failed Verification stops the loop as `needs-human-decision` with `revision_limit_reached`
  and the open finding IDs. Only a Human continues it, with
  `loop.py extend-revisions --actor human --authorization-reference REF --decision-evidence TEXT [--additional N]`,
  or ends it with `loop.py close`. Loops persisted before the limit stay unbounded.
  The loop's public state carries the stop as `pause` (`code`, `revisionCount`, `maxRevisions`,
  `pendingFindingIds`, `findings`), `null` otherwise; `capabilities` advertises
  `revisionLimitPause` so a host can offer the Human both decisions.
- The low-level loop CLI's omitted flag retains `work-verification` for existing callers.
  Persisted loops without the field use `work-verification`. New Main uses its captured mode
  explicitly when starting a loop.
- `capabilities` version 0.1.0 exposes `submit/send.taskModes`. Clients require the selected mode in
  that list before dispatch; absence is unsupported, never an invitation to inject prose
  or silently choose another route. Existing fields and receipt schema versions remain
  compatible.

<a id="actual-plan-transition"></a>

## 3. Actual Plan transition

- `plan`, `plan-work` and `plan-work-verification` require advertised Plan support.
- The runtime plans and executes within the same exact Work session, preserving model,
  reasoning, permissions and approval policy.
- The plan is retained as `plan.json`. In `plan` mode the host stops after the actual Plan turn,
  records a read-only Work completion receipt (no project changes or tests), and returns
  the plan. Other Plan routes require implementation before Work completion.
- No transition click is required.
- An unresolved required Human decision returns `needs-human-decision`.
- Failure or interruption cannot start implementation or Verification.
- Missing Plan support fails before a model turn; do not imitate the transition in prose.
- For Plan·Work routes, completed implementation and a valid Work receipt are required.
- `plan-work` completes with Work own checks; `plan-work-verification` requires separate Verification.

<a id="reports-and-authority"></a>

## 4. Reports and authority

- Use `not requested` for separate Verification in orchestrate/direct/work/plan-work modes, not
  `pass` or Human skip.
- Report Main's own checks for direct and Work-reported own checks for delegated work separately
  from independent Verification. Status and receipt identity checks do not re-verify work.
- Work performs necessary own checks but never claims independent Verification pass or commits.
- Permission, approval, publication and destructive-action authority remain independent
  of mode.
- Mode selection alone sends no messages to external services.


<a id="standalone-verification-and-planning"></a>

## 5. Standalone verification and planning

- Main resolves a standalone verification target from explicit input first, then prior
  completed work in this chat. Missing or ambiguous targets require a Human answer;
  never fabricate a Work ID or evidence.
- Dispatch `exec.py submit --role verification --task-mode verification --agent ID --request-file PATH`.
  The bounded request identifies the exact target and authorized checks. Do not supply
  `--verified-work-run-id` or `--receipt-request-hash`. Sends to this verifier also use
  `--task-mode verification` explicitly.
- `standalone-verification-receipt` binds `runId` and `requestHash` of this target request,
  with `decision` and `findings`; it contains no Work binding and cannot close a Work loop.
  Work-bound receipts and loop fix/recheck transitions keep their existing contracts.
- Plan alone dispatches `exec.py submit --role work --task-mode plan`; it does not create
  a loop or substitute literal `/plan` text for collaboration mode. Plan·Work routes
  continue using loop.py and the same Work session for Plan/default turns.
- Historical runs and omitted legacy loop routes retain their original meaning.

<a id="role-specific-model-overrides"></a>

## 6. Role-specific model overrides

- `loop.py start` accepts `--work-model`, `--work-reasoning-effort`, `--work-fast`/`--no-work-fast`,
  `--verification-model`, `--verification-reasoning-effort`, and `--verification-fast`/`--no-verification-fast`. These overrides
  are captured with the loop and passed to both initial and revision turns for
  that role. Plan uses the same Work profile. The existing `--model` remains a
  shared fallback for initial submissions when no role model is supplied.
- An orchestrator brief also passes `--work-profile` naming the profile Main chose, together
  with that profile's exact model ID and effort; the one retry after a failed `workLight` or
  `scribe` attempt passes `--work-profile work`. The profile is stored with the loop and each
  of its Work runs, including revision and receipt-recovery turns, so hosts display the
  choice instead of inferring it from model settings. It selects no model.

  | Profile | Role | Tools |
  |---|---|---|
  | `work` | Expert (heavy) | Authorized permissions |
  | `workLight` | Worker (light) | Authorized permissions |
  | `explore` | Explorer | Source reads, web lookups, exact assigned evidence Documents and own records |
  | `scribe` | Scribe | Public web search/read for Document research and source checks; writing, integration and shortening only inside `docs/` |

  Explorer and Scribe narrow tools below the authorized permissions and never widen them:
  Claude through an allowed-tool list, Codex and Antigravity through the runtime's tool guard.
  Each may run only its Agent Factory Document scripts, never `exec.py` or `loop.py`, and
  neither may start sub-agents, so only Main dispatches agents.
- Scribe's web access grants no code/configuration writes, external writes or publishing,
  sensitive-data transmission, dispatch or commits. Skills whose sources are outside
  `docs/` remain outside its write scope; report the needed change for a code Work owner.
  Report completed research separately from pending drafting, integration and Human acceptance.
  A research result alone does not complete a follow-up role's work.
- Use the [direct role exceptions](role-exceptions.md) for exact Explorer assignments,
  shared Document ownership, own records, captured authority and ordinary local commits.
- A Scribe's changes are drafts for Human review. `loop.py start` rejects a scribe code
  Work Unit (`scribe_draft_review_required`), because Work Units merge automatically; with
  Work isolation on, Scribe uses the read-only plan in the shared checkout. A completed
  scribe loop reports `draftReview` with the changed paths. Main relays them and records
  the Human's answer with `loop.py review --decision accepted|changes-requested|discarded`;
  the runtime records only and never commits or reverts. Rule candidates that a Scribe
  prepares from Lessons Learned are drafts in the same way; publication needs Human approval.
- For standalone `exec.py submit/send`, use `--model`, `--reasoning-effort`, and `--fast`/`--no-fast`.
- Fast selects Codex's service tier independently of reasoning effort. Preserve both values exactly. Role Fast is omitted for non-Codex providers.
- Model settings do not change execution authority or add an agent to the route.

## 7. Execution providers

- Historical sessions remain Codex sessions. `--model claude-opus`, `claude-sonnet`,
  or `claude-haiku` selects Claude Code's corresponding alias. Full `claude-*`
  model IDs such as `claude-opus-5-5`, `claude-sonnet-5`, `claude-fable-5-1` and
  `claude-haiku-4-5-20251001` pass through unchanged; account access is checked by Claude at execution.
- `exec.py submit` accepts `--provider codex|claude|antigravity`, `--claude <executable>` and
  `--agy <executable>`.
  `send` preserves the captured executable and provider unless an unstarted or
  explicitly cleared conversation selects another provider. Never pass a Codex
  session ID to Claude, or vice versa. Existing run history is retained.
- `capabilities --model <model>` reports the selected provider before submission.
  Do not infer Claude capabilities from Codex's app-server schema.
- Claude supports every task mode. Fast is accepted as a no-op; Goal uses Claude's `/goal`
  (see [Native Fast and Goal](native-fast-goal.md#claude-goal)). Plan runs in Claude's `plan`
  permission mode; plan-work routes then resume the same session to execute the approved plan.
- Execution policies map to the nearest Claude permission mode, always with
  `--permission-prompts none`:

  | Policy | Claude permission mode |
  |---|---|
  | `danger-full-access` | `bypassPermissions` |
  | `workspace-write` | `acceptEdits`, extra writable roots as `--add-dir` |
  | `read-only` | `dontAsk` |

  Claude tool permissions are not an OS sandbox: network access is not confined. Without an
  explicit policy (CLI default), `permissions.defaultMode` from the user, project and local
  Claude settings selects the policy; an unset or other mode maps to `read-only`.
- Claude effort values are `low`, `medium`, `high`, `xhigh`, and `max`. `minimal` maps to
  `low`, `ultra` to `max`, and `none` leaves Claude's default effort.
- Claude child runs load the user's Claude settings, hooks, tool servers and CLAUDE.md.
  Each run records `contextUsage` (latest prompt size and context window) in its state.

<a id="antigravity"></a>

### 7.1. Antigravity

- The Antigravity CLI (`agy`) runs Google AI subscription models in print mode. `gemini-*`
  models select it. Name its other models `antigravity/<id>` (for example
  `antigravity/claude-sonnet-4-6`) or pass `--provider antigravity` with the plain `<id>`;
  a plain `claude-*` model always selects Claude Code.
- Runs use an `agent-factory-<id>` custom agent, which each installed plugin copy writes to
  `~/.gemini/config/agents/agent-factory-<id>/agent.md` and prunes when its copy is removed. It replaces agy's default system prompt and
  keeps only file, shell, web, image generation and `finish` tools and the Agent Factory Skills; project rules (`AGENTS.md`, `GEMINI.md`) still
  apply, and the user's agy tool servers are not loaded.
- Every task mode and Goal are supported; Fast is a no-op and images are rejected (text only).
  Plan runs by instruction without skipped permissions, because agy's `plan` mode waits for review.
- Policies map to agy permissions, which are not an OS sandbox:

  | Policy | agy permissions |
  |---|---|
  | `danger-full-access` | `--dangerously-skip-permissions` |
  | `workspace-write` | default; extra writable roots as `--add-dir` |
  | `read-only` | default, with a read-only instruction |

  The default denies commands and reads outside the workspace, run directory and Agent Factory
  Skills, and allows
  workspace edits even under `read-only`. A denied call ends the turn without a result, so
  the run fails. The CLI default policy is `workspace-write`.
- `--effort` applies to agy's default model and base IDs such as `gemini-3.8-flash`; IDs
  ending in a level (`-low`, `-medium`, `-high`) fix their effort, and other families ignore it.
  A level the model does not offer (`gemini-3.1-pro` has `low` and `high`) uses the nearest one.
  `minimal` maps to `low`, `xhigh` and `ultra` to `max`, and `none` leaves the default.
