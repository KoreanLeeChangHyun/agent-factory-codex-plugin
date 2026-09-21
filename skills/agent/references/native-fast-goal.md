# Native Fast and Goal

<a id="capability-discovery"></a>

## 1. Capability discovery

- For managed Main, run `exec.py capabilities` against the session-bound executable.
- Schema support proves no model/account/admin-policy/tier entitlement. Preserve native
  rejection diagnostics; never change credentials/install/sandbox/policy to force
  access.
- Installed protocol discovery/runtime is authoritative; historical benchmarks or pinned
  CLI versions are not product guarantees.

<a id="fast-tier"></a>

## 2. Fast tier

- `--fast`: advertised Fast tier; `--no-fast`: default; omission: inherit session
  setting.
- Model/reasoning overrides work on initial/resumed turns with the exact stored thread
  ID.

<a id="goal-continuation"></a>

## 3. Goal continuation

<a id="scope"></a>

### 3.1. Scope

- `--goal-mode` creates/reopens a persisted native objective. Supply it through the first
  request or `--goal-objective`; never infer a token budget.
- Work execution and revision requests automatically bind a native Goal to their bounded
  request; necessary own checks belong to Work. Main can use Goal for direct tasks.
  Verification and plan-only never execute Goals. A delegated route with Main
  `--goal-mode` is rejected: submit that route without a Main Goal, since Work owns
  execution continuation. Unsupported Goal fails explicitly;
  do not replace it with repeated dispatches or silently disable it.
- Native Goal owns execution continuity. The management loop owns completed Work →
  independent Verification and failed Verification → the same Work/Verification sessions.
  Native turns, status and accounting cannot replace a bound receipt or Verification.
- Each revision receives its current request and result/receipt contract in the same
  thread. Long requests remain complete in developer instructions. No token budget is invented.
- Plan·Work uses actual Plan, then a default-mode transition turn without implementation,
  then native Goal activation in that same thread. Plan-only stops after the plan.
- Goal `complete` still requires the latest exact turn's valid result and Work receipt.
  Blocked/paused goals require Human input; usage/budget limits and cleared objectives
  fail rather than complete. Preserve reported failures and required Human decisions.
  Cancellation retains its cancelled runtime state. No automatic retry is added.
- Objective replacement/pause/reopen/clear follows installed host semantics.

<a id="commands"></a>

### 3.2. Commands

- Use `exec.py goal --project-root PROJECT --agent AGENT`:

- `get`: last observation.
- `refresh`: current native state, no model turn.
- `pause`: preserve objective, interrupt active work.
- `reopen` / `resume`: reactivate existing objective in idle Main.
- `cancel` / `clear`: remove objective.
- `disable`: clear objective and turn Goal mode off.

<a id="recovery-and-completion"></a>

### 3.3. Recovery and completion

1. Confirm controls through later Goal events or refreshed state; acceptance alone is
   insufficient.
2. After crash, termination, transport error or unconfirmed pause, refresh before
   reopening.
3. Correlate terminal Goal state with authoritative thread history; validate the latest
   native turn's exact result. Ordinary `turn/completed` does not prove objective completion.

- Never replay ambiguous launched runs or substitute earlier valid answers for later
  failed, interrupted or invalid turns.
