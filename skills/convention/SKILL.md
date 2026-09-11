---
name: convention
description: Apply Agent Factory's core model and cross-cutting conventions for project structure, development, testing, libraries, design, technical documentation, comments, Document types, and Skill ownership.
metadata:
  specification-id: convention
---

# Agent Factory Convention

## Ownership

- **Plugin:** only `agent` and `convention` under `skills/`; preserve identities.
  Never mirror into this repository's `.codex/`.
- **MCP:** Document, Gather, Tool, Workspace. **Local exec/loop:** execution.
- **Contracts:** maintain in owning references; avoid entrypoint duplication.

## Human communication

- Before producing any Human-facing message, read and follow the mandatory
  [respectful-register contract](references/communication.md).

## References

Read the matching references before acting.

### Core and development

- `references/communication.md`: mandatory respectful Human-facing register.
- `references/agent-factory-core.md`: roles, authority, Document types, decisions.
- `references/directory-structure.md`: source, installation, runtime, MCP/docs document storage, migration.
- `references/development.md`: shared checkout boundaries, changes, technical documentation, comments, commits.
- `references/testing.md`: test organization, selection, parallel execution and execution boundaries.
- `references/explicit-human-input.md`: missing Human decisions.
- `references/libraries.md`: dependencies, renderers.

### Design and knowledge

- `references/design.md`: interfaces, documents, SVG icons.
- `references/diagrams.md`: ERD, behavior and sequence diagrams.
- `references/explorer.md`: evidence exploration, provenance.
- `references/interview.md`: Main's Human elicitation.

## Bootstrap

- Copy `assets/AGENTS.md` only when authorized and project `AGENTS.md` is absent.
- Preserve existing files. The manifest injects none; the local initializer is retired.
