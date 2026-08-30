# Development Convention

Use these shared rules for implementation and maintenance work in Agent Factory
and its consumer projects. Follow a stronger project-local convention when one
has been explicitly established.

## Change boundaries

- Inspect the owning component, its callers, and its established patterns
  before changing it.
- Keep each change self-contained and bounded to the requested behavior.
  Preserve unrelated Human work, public contracts, storage authority, and
  accepted identities.
- Separate broad formatting, renaming, or refactoring from a behavioral change
  when combining them would obscure review or recovery.
- Do not turn a current local adapter, framework, or implementation detail into
  a universal architecture rule.
- Keep distributed plugin Skills, consumer Project Skills, runtime state,
  source collections, and Specifications in their declared ownership
  boundaries. Read `directory-structure.md` when a change affects paths.

## Implementation choices

- Prefer the smallest maintainable implementation that satisfies the accepted
  requirement and fits the existing codebase.
- Reuse an established abstraction before adding a parallel one. Avoid a new
  dependency when the current stack or standard library is sufficient; read
  `libraries.md` when selecting one.
- Make filesystem targets and adapter choices explicit. Do not silently select,
  mirror, migrate, or broaden a storage backend.
- Preserve existing files by default in initialization and scaffolding flows.
  Define overwrite, merge, or force behavior explicitly and scope it to exact
  targets.
- Keep generated or copied assets distinguishable from their reusable source
  and document the synchronization contract when both are maintained.

## Maintainability

- Keep names and interfaces consistent with their owning domain.
- Put reusable executable behavior in scripts and substantial conditional
  guidance in focused references rather than duplicating it across entry
  points.
- Update documentation and annotations affected by the code change. Read
  `annotation.md` when comments, documentation comments, or TODOs are involved.
- Report observed behavior separately from accepted decisions, inferred state,
  and unresolved questions.

## Evidence basis

Google's engineering practices recommend one self-contained concern per change
and separating substantial refactoring from feature or bug-fix work. They also
frame review around system-wide maintainability rather than local perfection:

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
