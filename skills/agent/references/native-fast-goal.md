# Native Fast and Goal

## Capability discovery

- For managed Main, run `exec.py capabilities` against the session-bound executable.
- Schema support proves no model/account/admin-policy/tier entitlement. Preserve
  native rejection diagnostics; never change credentials/install/sandbox/policy to force access.
- Installed protocol discovery/runtime is authoritative; historical benchmarks or
  pinned CLI versions are not product guarantees.

## Fast tier

- `--fast`: advertised Fast tier; `--no-fast`: default; omission: inherit session setting.
- Model/reasoning overrides work on initial/resumed turns with the exact stored thread ID.

## Goal continuation

### Scope

- `--goal-mode` creates/reopens a persisted native objective. Supply it through
  the first request or `--goal-objective`; never infer a token budget.
- Goal is Main-only; Work/Verification remain bounded with receipts. Native turns,
  status and accounting cannot advance loop, replace Verification or establish END.
- Objective replacement/pause/reopen/clear follows installed host semantics.

### Commands

Use `exec.py goal --project-root PROJECT --agent AGENT`:

- `get`: last observation.
- `refresh`: current native state, no model turn.
- `pause`: preserve objective, interrupt active work.
- `reopen` / `resume`: reactivate existing objective in idle Main.
- `cancel` / `clear`: remove objective.
- `disable`: clear objective and turn Goal mode off.

### Recovery and completion

1. Confirm controls through later Goal events or refreshed state; acceptance alone is insufficient.
2. After crash, termination, transport error or unconfirmed pause, refresh before reopening.
3. Correlate terminal Goal state with authoritative thread history; validate the latest
   native turn's exact result. Ordinary `turn/completed` does not prove objective completion.

- Never replay ambiguous launched runs or substitute earlier valid answers for later
  failed, interrupted or invalid turns.
