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

## Sources

- [Google: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Google: Code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [PEP 8: Comments](https://peps.python.org/pep-0008/#comments)
