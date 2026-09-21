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
- Resolve filesystem targets and adapters explicitly; never silently broaden, mirror or
  migrate storage. Initialization preserves files unless exact overwrite/merge behavior
  is authorized.
- Distinguish generated/copied assets from reusable source; document their sync contract.
- Agent Factory document paths are not a universal source-code layout.
- Follow [Testing](testing.md#source-organization) for test placement.
- Keep domain names/interfaces consistent; separate observed facts, accepted decisions,
  inferences and unresolved questions. Local implementations are not universal
  architecture rules.

<a id="shared-checkout-coordination"></a>

## 2. Shared checkout coordination

- Use the current shared checkout; do not create or switch to separate Git worktrees for
  ordinary or parallel Agent tasks.
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
  Human skip applied after Work completion in verification modes. Work/Verification
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
