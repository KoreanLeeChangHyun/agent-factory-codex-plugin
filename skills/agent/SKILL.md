---
name: agent
description: Dispatch and manage Agent Factory Work and Verification runs, sessions, and execution results. Use for managed execution operations, not greetings or ordinary conversation merely hosted by Agent Factory.
metadata:
  specification-id: agent
---

# Agent Factory Agent

- Use this Skill for the managed operation being performed, not just because the
  conversation runs in Agent Factory.
- Reuse instructions already present in context; read only references required for the
  next operation.
- `<plugin-root>` is the installed Agent Factory plugin directory that contains `skills/`,
  `runtime/` and `scripts/`; it is two levels above this `SKILL.md`.

<a id="roles-and-graph"></a>

## 1. Roles and graph

- Execution mode is captured per submitted task; conversation always remains Main.
- The default for each new Main input is `direct`; old saved selections do not apply. See [execution modes](references/execution-modes.md).

- **direct:** Main performs bounded work and appropriate own checks directly.
- **plan:** Work uses actual Plan collaboration mode and returns only a plan; no implementation transition.
- **verification:** managed standalone Verification of an explicit target, otherwise prior completed work in this chat; ask if no target is available. Its request-bound receipt cannot satisfy a Work loop.
- **work:** Main delegates Goal execution and necessary own checks to Work, then reports; no
  separate Verification. Report it as not requested, never a pass or Human skip.
- **plan-work:** Work plans in actual Codex Plan mode, then automatically executes in
  default mode within the same session. Main acknowledges the result/receipt and reports without rechecking implementation. Separate
  Verification is not requested.
- **work-verification:** Main -> Work -> Verification.
- **plan-work-verification:** Work plans in actual Codex Plan mode, then automatically
  executes in default mode within the same session. Separate Verification follows.
- **Work:** execute through native Goal with necessary own checks; no independent
  Verification pass claims, coordination or commits.
- **Verification:** independently check the exact completed Work run or an explicitly bound standalone target; no repair.
- **Fail in Work-bound verification modes:** return to the same Work and Verification sessions.
- **END:** direct completes after Main own checks; work/plan-work complete after
  Work Goal completion and its bound result/receipt;
  Work-bound verification routes require pass or evidenced Human skip applied after completed Work.
  Record skip before the next Verification; never equate failure/cancellation/input
  requests with completion. Mode selection is independent of Human approval policy.

### Managed execution quick path

- Reuse the installed Skill location and the current project/parent bindings. Do not
  search the home directory or runtime source to discover how to submit work.
- `direct` needs no managed commands. For authorized managed work, use the captured
  route below. Paths are relative to this Skill; invoke the installed absolute script
  path and pass the actual project root and bounded request file.

| Captured route | Command |
| --- | --- |
| `work`, `plan-work` | `python3 <plugin-root>/scripts/loop.py start --project-root PROJECT --task-mode MODE --work-agent UNIQUE_WORK_ID --request-file REQUEST` |
| `work-verification`, `plan-work-verification` | Same loop command, plus `--verification-agent UNIQUE_VERIFICATION_ID` |
| `plan` | `python3 <plugin-root>/scripts/exec.py submit --project-root PROJECT --role work --task-mode plan --agent UNIQUE_WORK_ID --request-file REQUEST` |
| `verification` | `python3 <plugin-root>/scripts/exec.py submit --project-root PROJECT --role verification --task-mode verification --agent UNIQUE_VERIFICATION_ID --request-file REQUEST` |

- Agent IDs are at most 64 ASCII letters/digits/`.`/`_`/`-`, starting with a letter
  or digit. Use a new identity per independent chain; keep it for revisions.
- Loops own dispatch IDs, recovery and bound verification transitions. Standalone
  submit/send generates a dispatch ID when omitted and returns it in the acceptance.
  Preserve returned identities. A lost acknowledgement is not permission to submit
  again: inspect the existing Agent first. Explicit recovery keys use
  `dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` and the same immutable request.
- Inspect capabilities once for the selected executable/configuration and reuse
  that evidence until it changes or a capability-related failure occurs. Do not
  prepend doctor/capabilities to every submission. Use doctor for first host selection,
  host changes or relevant failures; launch-time policy/preflight checks still apply.
- Use `loop.py status/reconcile --project-root PROJECT --work-agent WORK_AGENT_ID --loop-id RETURNED_LOOP_ID`
  for a loop, or `exec.py status/result --project-root PROJECT --agent AGENT_ID
  --run-id RETURNED_RUN_ID` for a standalone run. Acceptance is not completion.
- Keep the inherited execution policy and role model choices. Read the linked
  mode/runtime reference only for options or recovery details needed by this task.

<a id="delegation"></a>

## 2. Delegation

- Main asks the Human when a required decision is missing and waits before the affected action.
- Work and Verification report decision gaps to Main; neither asks the Human directly nor
  proceeds through the unresolved decision. Follow [Human decision and authority rules](../convention/SKILL.md#human-decisions).

- Under every approval policy, Main directly answers greetings, thanks, casual conversation
  and questions answerable from context. Keep replies proportional, without children,
  unnecessary tools or execution reports. Read the
  managed request as required; the runtime persists the reply. Conversation preserves
  active authorized work.
- Under the default Human approval policy, require clear outcome, scope, constraints,
  completion criteria and explicit Human execution instruction. Under runtime-injected
  `bypass`, a Human request for work authorizes immediate bounded dispatch without a
  separate plan approval. Conversation alone authorizes no dispatch under either policy.
- Continue conversation during child work; apply input to the active task. Record
  explicit redirects as control-plane transitions; preserve execution/results.
- CLI (default), exec and VS Code expose the same Main role.
- Parallelize only independent paths, writes and shared resources. Give chains distinct
  Agent/loop/run IDs, bounded inputs, authority and capabilities. Main sequences
  dependencies/integration and owns conflict avoidance. Use one shared checkout without
  separate Git worktrees; follow Convention's [shared checkout coordination](../convention/references/development.md#shared-checkout-coordination).

<a id="execution-and-shared-contracts"></a>

## 3. Execution and shared contracts

- **Local execution:** Main, Work, Verification and exec/loop provide the complete local workflow.
- **Git:** follow [Convention's publication contract](../convention/references/development.md#git-publication).
- **Runtime storage:** use [runtime locations](references/home-runtime.md#storage-and-identity).
- **Durable documents:** use [Document](../document/SKILL.md); keep temporary execution evidence in its run.
- **Human communication:** always follow Convention's mandatory [respectful-register contract](../convention/references/communication.md).

<a id="references"></a>

## 4. References

Read only the file for the operation at hand:

- Before dispatching (Main):
  - `references/execution-modes.md`: captured routes, completion rules, runtime interface, Plan
    transitions and providers.
  - `references/task-dispatch.md`: task binding, one-source announcement, ordered loop
    submission and worker assignment.
- While a run executes or is inspected:
  - `references/managed-execution.md`: prompts, sessions, run files, retries, CLI responses
    and receipts.
  - `references/home-runtime.md`: storage, cancellation and containment, capability bindings,
    legacy records and progress repair.
- When setting up or diagnosing a host:
  - `references/installation.md`: initialization, permissions, host readiness and relocation.
- Only for these features:
  - `references/native-fast-goal.md`: installed Codex Fast and native Goal.
  - `references/project-specialist.md`: project-specialized Work profiles.
