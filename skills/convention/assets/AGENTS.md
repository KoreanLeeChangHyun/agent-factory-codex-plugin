<INSTRUCTIONS>
<agent-factory>
Use the relevant Agent Factory Skills when the task calls for them. Detailed
contracts live in their owning Skills and are not duplicated here.

Resolve the installed Agent Factory `agent` and `convention` Skills from the
host's available Skills. The following references are relative to their owning
installed Skill roots, not to this project:

- Managed graph, role boundaries, and project-specialized Work profiles:
  Agent `SKILL.md` and `references/project-specialist.md`
- Core concepts, roles, authority, and shared invariants:
  Convention `references/agent-factory-core.md`
- Project layout and ownership boundaries:
  Convention `references/directory-structure.md`
- Document types, routing and Specification projections:
  Convention `references/documents.md`

This project uses Agent Factory. Keep its Human-requested Project Skills below
`.codex/skills/<category>-<name>/`, synchronized with their Human-facing
`docs/<category>-<name>.html` projections under the Documents contract. Preserve
existing project guidance; do not copy the installed plugin's Skills into this
project. MCP domain guides remain with the MCP application. Resolve managed
runtime locations through the installed Agent runtime, outside the checkout.
</agent-factory>
</INSTRUCTIONS>
