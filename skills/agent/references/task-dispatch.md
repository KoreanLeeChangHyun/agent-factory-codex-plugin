# Task Binding and Dispatch

- Contracts Main follows when announcing, binding, submitting and assigning managed tasks.

<a id="task-binding"></a>

## 1. Required task binding before dispatch

- Register each task that has its own completion criteria as a separate entry in `tasks`,
  independent of worker count.
  - Preserve the individual tasks communicated to the Human, including each task's identity,
    scope and completion criteria, so its progress, completion, waiting or blockage remains
    separately visible.
  - For example, six announced tasks require six registered entries even when one worker
    executes them sequentially in the same session.
  - Do not collapse them into one aggregate task because they share a worker or session.
- Every Work/Verification submission (including sends and standalone verification) requires
  `--task-list-file <json>` and `--task-id <id>`, except an orchestrator brief: `loop.py start`
  without them derives a single task from the brief (see
  [execution modes](execution-modes.md#runtime-interface)) and skips announcements.
  - Main first consolidates the Human's request and asks about any material missing information.
  - Write a JSON document with `id`, `title`, and a nonempty `tasks` array. Each task requires
    `id`, `title`, `description` and `completionCriteria`.
  - IDs are at most 128 letters/digits/dots/underscores/hyphens, starting with a letter or digit;
    titles are at most 300 characters and descriptions/criteria at most 4000. Task IDs must be unique.
  - Never manufacture placeholder task names to bypass this check.
  - When executing a work contract, the document also carries its structured `contract`
    object and every task's `requiredFileOperations`, per Convention's
    [work contracts](../../convention/references/work-contracts.md#execution-rules). The runtime
    then rejects out-of-scope operations; a list without `contract` is unbound.
- Do not calculate or supply `requestHash`. Caller-provided hashes are ignored; they never gate
  task submission. It normalizes a private snapshot without rewriting the submitted task-list file.
- Pass the same options to `loop.py start`; the loop snapshots the document and preserves the
  original request hash through revision and verification turns.
- The accepted run stores `taskBinding` together with its agent/run identity. Display that
  submitted task name and content to the Human and track the selected route through completion.
- Existing historical runs remain readable; new submissions require the binding.

<a id="task-announcement"></a>

## 2. One source for task presentation and submission

### 2.1. Announcement

- Before initial managed dispatch from Main, include an absolute `requestFile` for every task
  (including the first) in the structured task-list document.
- Run the installed
  `python3 <plugin-root>/scripts/exec.py announce-tasks --project-root PROJECT --task-list-file FILE`.
  - This command requires the active managed Main parent binding; it does not launch work.
  - It stores the ordered metadata and exact request bytes under that Main run and returns
    `taskFlow`, `taskListFile`, `taskId` and `requestFile` from the same snapshot.
- Show the returned `taskFlow` unchanged in a commentary fenced `task-flow` JSON block, then use
  the returned paths and ID for `--task-list-file`, `--task-id` and `--request-file` on the
  selected submission route.
  - Do not independently reconstruct the display list or parse natural-language tables.
  - Preserve completion criteria as well as IDs, titles, order and descriptions.
- Runtime preparation is neither proof of display nor acceptance.

### 2.2. Runtime-owned snapshot

- The runtime owns `task-announcements/<workflow-id>/announcement.json`, `task-list.json` and
  captured request files under the parent run.
  - The announcement records the runtime binding and parent Agent/run identity for later
    submission checks; never trust a UI cache or a caller-supplied path as ownership evidence.
  - Repeating the same preparation returns the same snapshot; changed content under the same
    workflow ID is rejected.
  - Do not edit these files.
- If the installed command is unavailable, report the compatibility limitation.
- Revisions retain their already accepted task binding and captured requests.
- After acceptance, update only actual bindings and statuses in the presented flow while
  preserving its task metadata and order.

### 2.3. Submission comparison

- New Main runs record `taskAnnouncementContract: 1`.
- Before `loop.py start` or a new Work/Verification `submit` or `send` is accepted under that
  parent, the runtime compares the entire submitted list with the parent's stored announcement:
  workflow identity/title, task IDs, count, order, titles, descriptions and completion criteria
  must match.
- Missing announcements, omitted/merged or duplicate tasks, reordered tasks and changed metadata
  produce specific `task_announcement_*` errors before a child starts.
- Caller-provided counts, hashes and announcement paths cannot substitute for this comparison.

### 2.4. Historical runs

- Historical Main runs without the marker retain their prior submission contract unless they
  explicitly prepared announcements.
- Unparented CLI submissions retain their existing task-binding contract.
- Historical records are not migrated or re-registered.
- Already accepted dispatch retries follow their immutable-tuple deduplication path; continue an
  accepted loop through its stored identity instead of starting it again.
- Revisions and Verification keep the same list metadata; their execution requests may differ.
  No manual request hash is required.

<a id="preparation-context"></a>

## 3. Supplied preparation context

- Use the host-supplied Git change paths, collection time and instruction sources when available.
- Main consolidates relevant conversation and scope and includes the relevant snapshot with its
  provenance in the child request. Work consumes that context.
- Do not repeat Git status or reread identical supplied instructions merely for preparation;
  recheck when stale, concurrent changes or the intended operation justify it.
- Unavailable Git data is not a clean tree.
- Read any required instructions that have not been supplied, and preserve all execution and
  authorization checks.
- If an older runtime rejects submission without hashes, report the compatibility limitation
  instead of adding a manual hash step.
- Retries and loop revisions retain the accepted immutable request binding.

<a id="ordered-workflow"></a>

## 4. Ordered workflow execution

- Submit the complete ordered task list once to `loop.py start` with its first task ID.
  - Every subsequent task must include `requestFile`.
  - Submit the request content without calculating or supplying a hash. Legacy caller hash
    fields are ignored.
- The engine validates and snapshots all requests before dispatch. Its detached driver executes
  the graph independently of Main and the chat panel.
- Work-only routes advance after the Work receipt; Work–Verification routes advance only after a
  passing Verification receipt, with failed findings returned to the same worker and verifier.
- Do not dispatch the next task from Main.
- Runtime errors stop at their recorded recovery point.
- The host renders the accepted full graph and each stage's stored status.

<a id="worker-assignment"></a>

## 5. Main-owned worker assignment

### 5.1. Worker count and reuse

- Main chooses worker count and session reuse from context continuity, dependencies, write
  overlap, shared resources and coordination cost.
- Do not equate task count with worker count or create a worker for every domain automatically.
- Preserve the captured execution route and Human authority.

### 5.2. Per-task assignment in one loop

- Each task may specify `workAgentId` and `verificationAgentId`. Omitted values use the
  corresponding start arguments.
- The first task must use `--work-agent`; that ID remains the loop's storage/control identity for
  status, reconcile, recovery and skip, even when later tasks use other workers.
- All Work and Verification session identities must be disjoint across the list.
- New assignees are submitted; existing sessions are sent the next request.
- A failed Verification returns to that task's assigned worker and verifier.
- Assignments are captured with the immutable request snapshot; do not edit an accepted list to
  reassign running work.

### 5.3. Parallel chains

- Tasks within one loop still execute in list order.
- For useful independent parallel chains, Main submits distinct lists with distinct workflow IDs
  and worker/verifier sessions, preserving each returned loop ID.
- Do not submit the same full list to multiple workers.
- Sequence cross-chain integration only after its prerequisites complete. There is no automatic
  cross-loop dependency scheduler; Main must track that dependency explicitly.
- Never share an active worker across parallel chains.
- Reuse one worker for related sequential tasks when that is more efficient.

<a id="task-workspaces"></a>

## 6. Captured task Work Units

- Work isolation is the Human's toggle, captured on the Main run as `workIsolation`. Off keeps the
  shared checkout. On (runtime advertising `workIsolation`), Main supplies `loop.py start
  --workspace-file FILE` for every brief or task: `code` for changes, `read-only` for research
  and questions; `shared` and a missing plan are rejected. Loops inherit the toggle.
- Store the input in the Main run directory. A code plan contains `mode: code` and
  `repositories`: exact `path`, optional `targetBranch`, and nonempty `checks` arrays of executable
  argv arrays from project rules. Derive repositories from the brief's target paths; nested
  repositories need separate tasks. Under isolation an omitted target is the current branch.
- Select only repositories owned by the task. Use the selected Work Unit's captured target when
  present, otherwise inspect the actual repository default branch. Missing repository/semantic
  decisions require clarification; do not guess targets or select every repository.
- Ordered task lists may instead carry each task's `workspace` plan. The accepted private list
  retains it, and each task acquires its own space before dispatch. Explicit `shared` and
  `read-only` modes have no repositories or automatic Git operations.
- The runtime prepares repository-specific branches under the project's managed `worktrees/`,
  relocates Work/Verification CWD and workspace-write roots, and retains original projectRoot,
  session/run/receipt identity. Source dirty/untracked changes remain excluded and visible.
- Revisions and recovery reuse the accepted task workspace. A duplicate code-task start with
  the same Agent/request/options returns the accepted loop; different options are rejected.
  Never retrofit an accepted loop, ignore an isolation prohibition, or isolate conversation,
  read-only research, standalone Verification or planning-only work.
- Work and Verification never commit. After Work's actual own checks and the requested
  Verification pass or recorded Human skip, runtime commits receipt-bound changes and prepares
  a checked ordinary two-parent target merge. Integration locks serialize each repository.
  Latest-target checks precede the target update; external updates require rechecking.
- An active competing checkout owner or integration lock keeps the loop `active` in
  `integrating`, with `integrationWait` evidence. The driver retries the same completed
  Work and receipt, without re-dispatch. New lifecycle-versioned loops preserve this wait
  across restarts without an arbitrary observation limit; historical loops keep their captured budget.
  Only the exact accepted parent Main is
  exempt on the target; another Main, queued runs and uncertain process ownership block.
  Expired runs are ignored only with positive empty containment or dead identity evidence.
  Historical busy stops can be reconciled
  in their original loop. Project bindings, provider failures and Human decisions remain enforced.
- Conflicts remain isolated. Runtime sends exact files/base/target and Git-stage instructions
  to the same Work session. Work stages justified resolutions and rechecks without committing.
  Requested Verification runs again. Without isolation, revision limits and unchanged conflict
  stages stop for concrete Human decisions. Never force ours/theirs, rewrite unrelated files or weaken tests.
- Under isolation conflicts never wait for a Human. Unchanged stages, the revision limit, a dirty
  target or another unmergeable outcome preserve branches and paths. New loops report
  `runtime-error` and `completion.integration=preserved|partial`; historical
  `completed/integration_preserved` records remain unchanged. Failed integration checks
  send their exact evidence back to Work for repair; unchanged failure evidence is preserved
  instead of repeatedly spending model tokens on the same repair.
- Failure, cancellation, dirty/active targets and failed checks preserve Work Units without
  reporting integration complete. Multi-repository outcomes are partial and resumable, not atomic.
  Cleanup retains unpreserved/ignored files and active runs; it removes only proven merged units.
- Inspect `taskWorkspaces` in loop status/progress for paths, branches, base/result/merge commits,
  check evidence, conflict/error and cleanup state. Chat/run/receipt history remains accessible.
  Supply exact integration commits for rollback; execute no revert, push, deploy or history rewrite.

### Durable continuation

- New loops snapshot linked local guidance and prepare lockfile-bound npm dependencies before
  model dispatch. `preflight` exposes the exact operation and output path; failed preparation
  preserves the pending task without consuming a Work turn.
  After resolving its external cause, the Human can use `loop.py retry-preparation`
  with the exact task ID, authorization reference and decision evidence. Each retry
  preserves prior operations and refuses an uncertain or still-live previous owner.
- Checks run under detached owners with persisted command, commit, process identity, output
  and exit evidence. UI status requests never drive or kill checks. An unknown exit is
  interrupted, never success; inspect its evidence before retrying.
- A pending decision binds project, task, role, child run, policy and question hash.
  `loop.py answer` accepts an exact Human response and resumes that same session once.
  Use `--response-file` or `--response-json` with decisionId, questionHash, projectRoot,
  loopId, taskId, runId and answer; include the Human authorization reference and evidence.
  Under bypass, only an explicitly classified task-execution approval receives one policy
  correction. Credentials, unknown scopes and expanded effects are never auto-approved.
- `loop.py steer` records an authorized in-scope addition bound to task/run IDs. Queued means
  waiting for a safe Work turn boundary, not live delivery; delivered records the accepted
  continuation run. Reuse the authorization reference to deduplicate a repeated submission.
- Reconcile a completed loop to retry safe pending cleanup. Unpreserved files remain intact.
