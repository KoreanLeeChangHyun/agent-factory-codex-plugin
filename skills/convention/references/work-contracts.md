# Work Contracts

<a id="scope"></a>

## 1. Scope

- Apply when the Human requests a work contract, consolidates requests into a task
  list for subsequent execution, or executes an existing contract.
- Main derives the contract from the conversation, attachments and relevant source
  inspection. Required fields are Main's preparation responsibility, not a form the
  Human must fill out. Preserve original requirements and source references.
- A request to organize a list or show a sample does not authorize implementation.
  Preserve the captured execution mode and approval policy; preparing a contract adds
  no routine approval gate under bypass.
- Use file-level change scope for code work. For research or other non-file work,
  identify the actual targets and deliverables without inventing code paths.
- Follow [Document](../../document/SKILL.md) when storing a durable contract; ordinary
  chat samples require no file creation. Contract identity does not itself promote a
  document to an accepted Specification.

<a id="contract-content"></a>

## 2. Contract content

| Section | Required content |
|---|---|
| Basic information | Contract ID, version and overall outcome |
| Task list | Stable task ID, task description and observable completion criteria |
| File change list, for file-changing work | Exact project-relative path, add/modify/delete operation and associated task IDs |

- Record the project or repository root when needed to resolve paths unambiguously.
- Include governing specifications with path/link, relevant section and version when
  applicable; explicitly distinguish no applicable specification from one not yet found.
- Include dependencies and task-specific constraints, preserved behavior and exclusions
  when applicable. Separate governing specifications from optional reference material.
- Reference material, priority and desired schedule are optional; do not invent them.
- A brief file-change purpose may aid review. Function designs, internal algorithms,
  code-region tracking and detailed diffs are not required contract fields.
- Task IDs link tasks, file operations and results. `T1` is an example, not a required
  prefix. Preserve existing IDs and never renumber them merely to change display order.
- Keep task-specific content in the Human-facing contract. Do not copy the common
  execution rules below or explanatory user instructions into every contract.

<a id="execution-rules"></a>

## 3. Common execution rules

- Before finalizing file scope, inspect relevant code, specifications, callers and
  dependencies, including needed test, configuration and generated-file changes.
  Mark unresolved paths as unconfirmed; never fabricate confirmed targets.
- Bind execution to the identified contract version and selected task IDs. Reuse
  existing task presentation/submission identities and snapshots; do not create a
  competing task list or silently replace the captured request.
- The executing Agent chooses detailed implementation within the agreed outcomes,
  governing specifications, exact file paths and add/modify/delete operations.
- Treat the file list as the change boundary. Reading relevant files is not permission
  to change them. Preserve unrelated pre-existing and concurrent changes.
- First seek a sound solution within scope. If a listed operation must be omitted or
  changed, or an unlisted file must change, present the reason and revised contract
  before the affected action and obtain explicit Human confirmation. Do not distort
  implementation or make unnecessary edits just to match the list. Continue independent
  authorized tasks while the affected work waits.
- Record confirmed amendments as a new contract version, retaining the original and
  decision evidence. A contract draft alone grants no deletion, publication or other
  additional authority; apply existing action-specific authorization rules.
- At completion, compare actual file operations with the bound version, accounting
  for the starting state; report missing or unexpected changes and task completion
  evidence. Do not call blocked, failed or unchecked work complete.
- Append results under the same task IDs without rewriting the original contract.
  Report file-level outcomes and completion criteria; distinguish own checks from
  independent Verification, and retain the selected route's reporting obligations.

<a id="sample"></a>

## 4. Sample contract

- The paths and specification below are illustrative, not inspected project facts.

### 4.1. Basic information

| Contract | Version | Goal |
|---|---|---|
| WC-001 | 1 | Run only the tasks selected by the user |

### 4.2. Task list

| Task ID | Task | Completion criteria |
|---|---|---|
| T1 | Add task selection | Individual and all-item selection can be set and cleared |
| T2 | Submit selected tasks | Only selected tasks are submitted; an empty selection does not execute |
| T3 | Remove the obsolete run-all helper | The helper and its references are removed; selected execution still works |

### 4.3. File change list

| Task IDs | File | Operation | Purpose |
|---|---|---|---|
| T1 | `src/ui/TaskList.tsx` | Modify | Display selection controls |
| T1, T2 | `src/state/taskSelection.ts` | Add | Manage selection state |
| T2, T3 | `src/actions/submitTasks.ts` | Modify | Submit selected tasks and remove the old helper reference |
| T3 | `src/actions/runAllTasks.ts` | Delete | Remove the obsolete helper |
| T1, T2, T3 | `tests/taskExecution.test.ts` | Modify | Check selection and execution behavior |

### 4.4. Specifications and conditions

| Item | Value |
|---|---|
| Governing specification | `docs/specs/task-selection.md` v1, Selection and Execution conditions |
| Dependencies | T2 after T1; T3 after T2 |
| Preserve | Existing task sorting and detail views |
| Exclude | Scheduling, cancellation and execution-history UI |
