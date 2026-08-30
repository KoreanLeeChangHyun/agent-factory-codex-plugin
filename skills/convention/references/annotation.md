# Annotation Convention

Use this capability whenever code comments, documentation comments, or TODO
annotations are created, changed, or reviewed.

## Code Comment Convention

- Document intent, constraints, side effects, and exceptional decisions that
  are not evident from the code itself.
- Do not restate the code's behavior in natural language.
- Use the programming language's standard documentation format for public APIs.
- Verify related comments and documentation whenever the code changes.
- Remove or correct comments that conflict with the code or lack verified
  support.
- Include a reason and completion condition or a traceable issue in every TODO.
- Do not preserve inactive code in comments; rely on version control history.
- Prefer clear names, small units, type information, and tests over comments.
- Prioritize accuracy and information value over comment quantity.

## Evidence basis

This convention follows the common guidance that comments should explain
reasoning the code cannot express, must stay aligned with the implementation,
and should not restate obvious operations:

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [Python PEP 8: Comments](https://peps.python.org/pep-0008/#comments)
