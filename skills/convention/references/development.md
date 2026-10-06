# Development

- Follow stronger established project conventions.
- For contract-bound changes, apply [Work Contracts](work-contracts.md) for exact file
  operations, Human-confirmed amendments and completion reconciliation.

<a id="changes"></a>

## 1. Changes

- Inspect the owning component, callers and existing patterns; keep changes bounded.
  Preserve unrelated work, public contracts and accepted identities.
- Separate broad formatting/refactoring when it would obscure behavioral review.
- Reuse existing abstractions and the smallest maintainable implementation. Use
  [Libraries](libraries.md) for dependencies; follow the project's native layout.
- Before changing any UI, apply [Theme and visual acceptance](theme.md); include its
  applicable checks in the task's completion criteria.
- Resolve filesystem targets and adapters explicitly; never silently broaden, mirror or
  migrate storage. Initialization preserves files unless exact overwrite/merge behavior
  is authorized.
- Distinguish generated/copied assets from reusable source; document their sync contract.
- Agent Factory document paths are not a universal source-code layout.
- Follow [Testing](testing.md#source-organization) for test placement.
- Keep domain names/interfaces consistent; separate observed facts, accepted decisions,
  inferences and unresolved questions. Local implementations are not universal
  architecture rules.

<a id="code-ownership-and-minimal-design"></a>

### 1.1. Code ownership and minimal design

- **MUST NOT independently duplicate an existing implementation of the same
  responsibility or rule.** Before writing code, locate its owning module and callers;
  reuse or extend that implementation when it owns the required behavior.
- Paths that must behave alike—including live, completion and restoration paths—MUST
  use the same interpretation rules and MUST be checked for consistency. Keep
  intentional platform differences explicit, and identify generated copies separately
  from hand-maintained sources with their ownership and synchronization relationship.
- Add only the code needed to meet the current requirement, keeping it readable and
  maintainable. Do not add generalization, speculative future flexibility,
  pass-through wrappers or layers without a present need.
- Create an abstraction only when it removes real duplication and reduces the total cost
  of understanding or changing the behavior. Count tokens, review effort, and the files
  and layers contributors must trace as costs. A small shared function MUST NOT be
  expanded into a framework without a demonstrated need.
- Treat duplicate implementations as a serious structural defect: they multiply the
  places AI-assisted follow-up work must discover, change and validate, increasing the
  risk of missed or inconsistent fixes. Preventing such duplication is a project
  priority and a required rule.
- Do not shorten or compress code at the expense of readability, required error
  handling, validation or tests.

<a id="commands-and-paths"></a>

### 1.2. Commands and paths

- Locate a file with a file listing, search or an explicit link before reading, editing
  or passing it to a command. Do not guess names from a feature, and do not reuse paths
  from an earlier conversation or version without rechecking them.
- Fix the working directory of each command. In nested repositories, run each
  repository's commands from its own root or with an explicit prefix (`git -C`,
  `npm --prefix`); do not repeat a relative `cd` or duplicate a directory prefix that
  the working directory already supplies.
- Probe optional paths with an existence check. Distinguish "no match" exits (such as
  `rg` exit 1) from command errors and do not report them as failures.
- Write portable shell: avoid globs that may match nothing (zsh aborts on them), keep
  commands and arguments in arrays rather than string variables, delimit variables as
  `${NAME}` before adjacent text, and move deeply nested quoting into a script.
- Keep each tool output within its budget: read targeted ranges or narrowed searches,
  and write large surveys to a temporary file before reviewing them in parts.

<a id="shared-checkout-coordination"></a>

## 2. Shared checkout coordination

- Explicit shared-checkout requests and accepted legacy tasks use the current shared checkout;
  do not create or switch their Git worktrees. New code tasks with captured
  [task Work Units](../../agent/references/task-dispatch.md#task-workspaces) use the runtime's
  bound isolated directory. This exception grants no manual worktree or Git publication authority.
- Before dispatch, Main explicitly assigns each Work bounded read and write scopes.
  Reads may overlap, but concurrent writes must be disjoint. Prefer directory or module
  ownership, narrowed to exact files when necessary.
- Parallelize only when write scopes and mutable shared resources are independent.
  Sequence overlapping paths, shared dependencies, configuration, generated files and
  cross-cutting integration work.
- Main orchestrates dependencies, scope ownership, integration order and conflict
  avoidance. When a shared file requires an edit, Main assigns it to one bounded Work in
  sequence. In direct mode Main owns the bounded edits.
- Work never silently modifies paths outside its assigned write scope and reports any
  unavoidable scope conflict.
- Hold relevant paths and dependencies stable during each Verification. After parallel
  results are integrated, independently verify the combined state. The runtime does not
  enforce file ownership.
- Main serializes Git index and commit operations in the shared checkout.

<a id="technical-documentation"></a>

## 3. Technical documentation

- Follow [Document](../../document/SKILL.md) for language, writing structure, current-state
  guidance, source ownership and durable storage. Do not duplicate those rules here.
- Retain current compatibility, migration and recovery requirements when revising technical guidance.
- Place useful visuals near their explanation; follow [Diagrams](diagrams.md) for semantics
  and readable text. Avoid decorative or quota-driven visuals.
- Consolidate duplicate guidance at its owner and update every affected reference.

<a id="comments-and-todos"></a>

## 4. Comments and TODOs

- Explain non-obvious intent, constraints, side effects and exceptional decisions; do
  not narrate code. Prefer clear names, types and small units.
- Use language-standard public API documentation; update or remove inaccurate,
  unsupported comments when code changes. Keep inactive code in Git history.
- Each TODO needs a reason and completion condition or traceable issue.

<a id="tests"></a>

## 5. Tests

- Read `testing.md` for test organization, focused execution and Verification boundaries.

<a id="git-publication"></a>

## 6. Git publication

- Main directly makes authorized ordinary commits after the selected route completes:
  Main own checks in direct, completed Work with its own checks in work/plan-work, or independent pass/evidenced
  Human skip applied after Work completion in verification modes. Captured task Work Units may
  use Main's runtime-owned checked integration path described in Agent's
  [task Work Units](../../agent/references/task-dispatch.md#task-workspaces). Work/Verification
  never commit; add no commit turn, role or graph node.
- Inspect applicable Work result/receipt, check/pass/skip evidence and current
  status/diff. Stage only bound paths, excluding unrelated dirty, untracked, generated
  and runtime data.
- Commit authority grants no push, amend, force, history rewrite, reset, restore or
  delete. Report staging/commit obstructions without expanding scope.

<a id="sources"></a>

## 7. Sources

- [Google: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Google: Code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [PEP 8: Comments](https://peps.python.org/pep-0008/#comments)
