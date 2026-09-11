# Development

Follow stronger established project conventions.

## Changes

- Inspect the owning component, callers and existing patterns; keep changes
  bounded. Preserve unrelated work, public contracts and accepted identities.
- Separate broad formatting/refactoring when it would obscure behavioral review.
- Reuse existing abstractions and the smallest maintainable implementation.
  Use `libraries.md` for dependencies and `directory-structure.md` for paths.
- Resolve filesystem targets and adapters explicitly; never silently broaden,
  mirror or migrate storage. Initialization preserves files unless exact
  overwrite/merge behavior is authorized.
- Distinguish generated/copied assets from reusable source; document their sync
  contract. Keep reusable code in scripts and conditional guidance in references.
- Keep domain names/interfaces consistent; separate observed facts, accepted
  decisions, inferences and unresolved questions. Local implementations are not
  universal architecture rules.

## Shared checkout coordination

- Use the current shared checkout; do not create or switch to separate Git
  worktrees for ordinary or parallel Agent tasks.
- Before dispatch, Main explicitly assigns each Work bounded read and write
  scopes. Reads may overlap, but concurrent writes must be disjoint. Prefer
  directory or module ownership, narrowed to exact files when necessary.
- Parallelize only when write scopes and mutable shared resources are
  independent. Sequence overlapping paths, shared dependencies, configuration,
  generated files and cross-cutting integration work.
- Main orchestrates dependencies, scope ownership, integration order and
  conflict avoidance. When a shared file requires an edit, Main assigns it to
  one bounded Work in sequence; Main does not perform Work itself.
- Work never silently modifies paths outside its assigned write scope and
  reports any unavoidable scope conflict.
- Hold relevant paths and dependencies stable during each Verification. After
  parallel results are integrated, independently verify the combined state.
  The runtime does not enforce file ownership.
- Main serializes Git index and commit operations in the shared checkout.

## Technical documentation

- Use sections/subsections for topics and deeper headings only for distinct subtopics.
- Use bullets for parallel rules and numbered lists for ordered procedures.
- Use tables actively for comparisons and mappings with shared dimensions,
  such as roles, ownership, options and reference purposes.
- Use diagrams actively to explain flows, structures and relationships;
  follow [diagrams.md](diagrams.md) for diagram selection and authoring.
- Keep each item focused; use short introductory prose only when it adds context.
- Consolidate duplicates in the owning document; preserve constraints and update callers.
- Store generated documents using [MCP/docs routing](directory-structure.md#ai-generated-documents).

## Comments and TODOs

- Explain non-obvious intent, constraints, side effects and exceptional decisions;
  do not narrate code. Prefer clear names, types and small units.
- Use language-standard public API documentation; update or remove inaccurate,
  unsupported comments when code changes. Keep inactive code in Git history.
- Each TODO needs a reason and completion condition or traceable issue.

## Tests

- Read `testing.md` for test organization, focused execution and Verification boundaries.

## Git publication

- Main directly makes authorized ordinary commits after independent pass or
  evidenced Human skip applied after Work completion. Work/Verification never
  commit; add no commit turn, role or graph node.
- Inspect Work result/receipt, pass/skip evidence and current status/diff. Stage
  only bound paths, excluding unrelated dirty, untracked, generated and runtime data.
- Commit authority grants no push, amend, force, history rewrite, reset, restore
  or delete. Report staging/commit obstructions without expanding scope.

## Plugin release readiness

The repository marketplace installs this plugin from `main`. Treat another branch
as a release candidate, not as published state.

1. Inspect the candidate diff against the current remote `main`; resolve unrelated
   changes and confirm the exact release scope.
2. Update the manifest cachebuster with Plugin Creator's
   `update_plugin_cachebuster.py`; preserve the base semantic version and keep one
   `+codex.<cachebuster>` suffix.
3. Obtain explicit Human verification authority. Run either the manually dispatched
   `Human-authorized verification` workflow or the exact Human-supplied checks.
   A full release check covers the configured Python 3.10 and 3.12 baselines and
   the distribution, contract, runtime and integration suites.
4. Run the Plugin Creator validator against the candidate checkout. This separately
   checks the current Codex plugin ingestion shape; repository tests do not replace it.
5. Recheck the manifest, marketplace source/ref, Skill inventory and release diff.
   Record the exact verification evidence before an authorized ordinary commit.
6. Merge or push to `main` only with explicit Human publication authority. Confirm
   the remote `main` contains the verified commit before describing the release as
   published, then verify a fresh marketplace installation in a new Codex thread.

- The marketplace/manifest contract test prevents local metadata drift but cannot
  prove that a remote branch, installation, account or deployment is current.
- Do not move MCP-owned schemas, services or Workspace assets into the plugin to
  make a release self-contained.

## Sources

- [Google: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Google: Code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [PEP 8: Comments](https://peps.python.org/pep-0008/#comments)
