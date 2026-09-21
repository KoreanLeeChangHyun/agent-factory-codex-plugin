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
| `work`, `plan-work` | `python3 scripts/loop.py start --project-root PROJECT --task-mode MODE --work-agent UNIQUE_WORK_ID --request-file REQUEST` |
| `work-verification`, `plan-work-verification` | Same loop command, plus `--verification-agent UNIQUE_VERIFICATION_ID` |
| `plan` | `python3 scripts/exec.py submit --project-root PROJECT --role work --task-mode plan --agent UNIQUE_WORK_ID --request-file REQUEST` |
| `verification` | `python3 scripts/exec.py submit --project-root PROJECT --role verification --task-mode verification --agent UNIQUE_VERIFICATION_ID --request-file REQUEST` |

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

- Main directly answers greetings, thanks, casual conversation and questions answerable
  from available context.
  - This applies under every approval policy.
  - Create no managed children or unnecessary tool calls for these replies.
  - Keep conversational replies proportional and omit execution reports.
  - Read the managed request as required.
  - The runtime persists the final response.
  - Preserve active authorized work when responding to conversational steering.
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

- Read before the corresponding operation:

- `references/execution-modes.md`: captured execution routes, completion rules, runtime interface and Plan
  transitions.
- `references/home-runtime.md`: dispatch, sessions, receipts, prompts, containment, bindings, storage and
  migration.
- `references/native-fast-goal.md`: installed Codex Fast and native Goal.
- `references/project-specialist.md`: project-specialized Work profiles.

### Required task binding before dispatch

Register each task that has its own completion criteria as a separate entry in `tasks`,
independent of worker count. Preserve the individual tasks communicated to the Human,
including each task's identity, scope and completion criteria, so its progress, completion,
waiting or blockage remains separately visible. For example, six announced tasks require
six registered entries even when one worker executes them sequentially in the same session.
Do not collapse them into one aggregate task because they share a worker or session.

Every Work/Verification submission (including sends and standalone verification) requires `--task-list-file <json>` and `--task-id <id>`. Main first consolidates the Human's request and asks about any material missing information. Write a JSON document with `id`, `title`, and a nonempty `tasks` array. Each task requires `id`, `title`, `description` and `completionCriteria`. Do not calculate or supply `requestHash`. Caller-provided hashes are ignored; they never gate task submission. It normalizes a private snapshot without rewriting the submitted task-list file. IDs are at most 128 letters/digits/dots/underscores/hyphens, starting with a letter or digit; titles are at most 300 characters and descriptions/criteria at most 4000. Task IDs must be unique. Pass the same options to `loop.py start`; the loop snapshots the document and preserves the original request hash through revision and verification turns. Never manufacture placeholder task names to bypass this check. The accepted run stores `taskBinding` together with its agent/run identity. Display that submitted task name and content to the Human and track the selected route through completion. Existing historical runs remain readable; new submissions require the binding.

### One source for task presentation and submission

Before initial managed dispatch from Main, include an absolute `requestFile` for every
task (including the first) in the structured task-list document. Run the installed
`python3 scripts/exec.py announce-tasks --project-root PROJECT --task-list-file FILE`.
This command requires the active managed Main parent binding; it does not launch work.
It stores the ordered metadata and exact request bytes under that Main run and returns
`taskFlow`, `taskListFile`, `taskId` and `requestFile` from the same snapshot.
Show the returned `taskFlow` unchanged in a commentary fenced `task-flow` JSON block,
then use the returned paths and ID for `--task-list-file`, `--task-id` and `--request-file`
on the selected submission route. Do not independently reconstruct the display list or
parse natural-language tables. Preserve completion criteria as well as IDs, titles,
order and descriptions. Runtime preparation is neither proof of display nor acceptance.

The runtime owns `task-announcements/<workflow-id>/announcement.json`, `task-list.json`
and captured request files under the parent run. The announcement records the runtime
binding and parent Agent/run identity for later submission checks; never trust a UI
cache or a caller-supplied path as ownership evidence. Repeating the same preparation
returns the same snapshot; changed content under the same workflow ID is rejected.
Do not edit these files. If the installed command is unavailable, report the compatibility
limitation. Revisions retain their already accepted task binding and captured requests.
After acceptance, update only actual bindings and statuses in the presented flow while
preserving its task metadata and order.

New Main runs record `taskAnnouncementContract: 1`. Before `loop.py start` or a new
Work/Verification `submit` or `send` is accepted under that parent, the runtime compares
the entire submitted list with the parent's stored announcement: workflow identity/title,
task IDs, count, order, titles, descriptions and completion criteria must match. Missing
announcements, omitted/merged or duplicate tasks, reordered tasks and changed metadata
produce specific `task_announcement_*` errors before a child starts. Caller-provided
counts, hashes and announcement paths cannot substitute for this comparison.

Historical Main runs without the marker retain their prior submission contract unless
they explicitly prepared announcements. Unparented CLI submissions retain their existing
task-binding contract. Historical records are not migrated or re-registered. Already
accepted dispatch retries follow their immutable-tuple deduplication path; continue an
accepted loop through its stored identity instead of starting it again. Revisions and
Verification keep the same list metadata; their execution requests may differ. No manual
request hash is required.

### Supplied preparation context

Use the host-supplied Git change paths, collection time and instruction sources when available. Main consolidates relevant conversation and scope and includes the relevant snapshot with its provenance in the child request. Work consumes that context. Do not repeat Git status or reread identical supplied instructions merely for preparation; recheck when stale, concurrent changes or the intended operation justify it. Unavailable Git data is not a clean tree. Read any required instructions that have not been supplied, and preserve all execution and authorization checks. If an older runtime rejects submission without hashes, report the compatibility limitation instead of adding a manual hash step. Retries and loop revisions retain the accepted immutable request binding.

### Ordered workflow execution

Submit the complete ordered task list once to `loop.py start` with its first task ID. Every subsequent task must include `requestFile`. Submit the request content without calculating or supplying a hash. Legacy caller hash fields are ignored. The engine validates and snapshots all requests before dispatch. Its detached driver executes the graph independently of Main and the chat panel. Work-only routes advance after the Work receipt; Work–Verification routes advance only after a passing Verification receipt, with failed findings returned to the same worker and verifier. Do not dispatch the next task from Main. Runtime errors stop at their recorded recovery point. The host renders the accepted full graph and each stage's stored status.


### Main-owned worker assignment

Main chooses worker count and session reuse from context continuity, dependencies, write overlap,
shared resources and coordination cost. Do not equate task count with worker count or create a
worker for every domain automatically. Preserve the captured execution route and Human authority.

In an ordered loop, each task may specify `workAgentId` and `verificationAgentId`. Omitted values
use the corresponding start arguments. The first task must use `--work-agent`; that ID remains the
loop's storage/control identity for status, reconcile, recovery and skip, even when later tasks use
other workers. All Work and Verification session identities must be disjoint across the list.
New assignees are submitted; existing sessions are sent the next request. A failed Verification
returns to that task's assigned worker and verifier. Assignments are captured with the immutable
request snapshot; do not edit an accepted list to reassign running work.

Tasks within one loop still execute in list order. For useful independent parallel chains, Main
submits distinct lists with distinct workflow IDs and worker/verifier sessions, preserving each
returned loop ID. Do not submit the same full list to multiple workers. Sequence cross-chain
integration only after its prerequisites complete. There is no automatic cross-loop dependency
scheduler; Main must track that dependency explicitly. Never share an active worker across
parallel chains. Reuse one worker for related sequential tasks when that is more efficient.
