# Execution modes

<a id="captured-routes"></a>

## 1. Captured routes

| Mode | Implementation | Completion |
| --- | --- | --- |
| `direct` (new Main input default) | Main directly | Appropriate Main checks |
| `work` | Managed Work | Completed Work Goal and receipt with own checks; separate Verification not requested |
| `plan` | Actual Work Plan collaboration mode only | Return plan; no execution or Verification |
| `verification` | Managed standalone Verification | Request-bound standalone receipt and findings; no repairs |
| `plan-work` | Actual Plan then default execution in the same Work thread | Completed Work Goal and receipt with own checks; separate Verification not requested |
| `work-verification` | Managed Work | Separate Verification pass or evidenced Human skip |
| `plan-work-verification` | Actual Plan then default execution in the same Work thread | Separate Verification pass or evidenced Human skip |

- Conversation and Human Interview always remain Main.
- Selecting a mode does not satisfy the independent Human approval gate or expand
  execution permissions.
- Composer actions send the current draft through Main immediately and are never persisted.
  Ordinary Enter/send always captures direct, even after restoring old saved modes.
  Queued messages retain their action; different actions must never merge.
- Main preserves an active task's route when handling conversational steering.

<a id="runtime-interface"></a>

## 2. Runtime interface

- `exec.py submit/send --task-mode MODE` snapshots the route. New Main requests without a flag capture `direct`;
  persisted runs with no mode use `work-verification`. Explicit flags participate in the
  immutable dispatch tuple.
- Main performs `direct` work itself; do not create a direct-mode loop.
- `loop.py start --task-mode work --work-agent ID --request-file PATH` (also `--task-mode plan-work`) needs no Verification identity. Its completed Work
  receipt ends the loop with terminal reason `work-completed`. Main acknowledges the bound result/receipt and reports without reviewing implementation
  or rerunning checks.
- Work-bound verification modes additionally require `--verification-agent ID`. Failure revises the same Work
  session, then reuses the same Verification session and binds its receipt to the new
  exact Work run. No planning role or extra Agent exists.
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

- Use `not requested` for separate Verification in direct/work/plan-work modes, not
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

- `loop.py start` accepts `--work-model`, `--work-reasoning-effort`,
  `--verification-model`, and `--verification-reasoning-effort`. These overrides
  are captured with the loop and passed to both initial and revision turns for
  that role. Plan uses the same Work profile. The existing `--model` remains a
  shared fallback for initial submissions when no role model is supplied.
- For standalone `exec.py submit/send`, use `--model` and `--reasoning-effort`.
- Model settings do not change execution authority or add an agent to the route.
