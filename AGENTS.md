<INSTRUCTIONS>
<agent-factory>
Use the relevant Agent Factory Skills when the task calls for them. Detailed
contracts live in their owning Skills and are not duplicated here.

Reference locations:

- Managed graph, role boundaries, and project-specialized Work profiles:
  `skills/agent/SKILL.md`
  `skills/agent/references/project-specialist.md`
- Core concepts, roles, authority, and shared invariants:
  `skills/convention/references/agent-factory-core.md`
- Project layout and ownership boundaries:
  `skills/convention/references/directory-structure.md`

This repository is the Agent Factory plugin. Keep its distributed Skills below
`<plugin-root>/skills/`; do not create or mirror them below this repository's
`.codex/`. Keep durable plugin guidance in its owning Skill; MCP domain guides
remain with the MCP application. Runtime paths are resolved by
`skills/agent/runtime/paths.py` outside the checkout.
</agent-factory>
</INSTRUCTIONS>
