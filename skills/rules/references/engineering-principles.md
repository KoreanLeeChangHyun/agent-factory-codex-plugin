# Engineering Principles

## Agent Factory Engineering Principles

Apply these principles to design, code, refactoring, review, Work Units,
artifacts, and skill work:

- SOLID: keep object and module boundaries change-local and extensible.
- SoC: separate different responsibilities and concerns explicitly.
- DRY: do not repeat the same knowledge, rule, or ownership decision in
  multiple places.
- YAGNI: do not add features, abstractions, or structure not needed by the
  current recorded requirement.
- Refactoring: improve internal structure while preserving external behavior
  unless the Human explicitly approves behavior change.
- CI/CD: keep integration, verification, and deployment paths automatable and
  deployable.
- Test Pyramid: when the Human explicitly authorizes testing, balance unit,
  integration, and E2E checks according to risk and blast radius within the
  bounded selected commands.
- Agile Principles: keep changes small, get feedback quickly, and improve
  continuously.
- Human-in-the-loop Review: AI-produced results require Human review and Human
  responsibility.
- Project-Skill Guidance: use the target Project Skill as the default AI-facing
  project context; Specification is an explicit optional artifact.
- Human Feedback Evaluation: deliver small results quickly and treat Human
  feedback as the primary iteration signal. Tests and metrics run only when the
  Human explicitly requests verification; exact supplied commands are unchanged
  and otherwise the smallest bounded commands come from repository evidence.
- Observability: make inputs, outputs, decisions, and errors traceable.
- Security by Design: include security, authorization, and data protection from
  the design phase.

Use `conventions` whenever code comments, documentation comments, or
TODO annotations are created, changed, or reviewed.
