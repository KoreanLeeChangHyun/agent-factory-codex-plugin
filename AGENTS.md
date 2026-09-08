<INSTRUCTIONS>
<agent-factory>
Use the relevant Agent Factory Skills when the task calls for them. Detailed
contracts live in their owning Skills and are not duplicated here.

Reference locations:

- Core concepts, roles, authority, and shared invariants:
  `skills/convention/references/agent-factory-core.md`
- Project layout and ownership boundaries:
  `skills/convention/references/directory-structure.md`

This repository is the Agent Factory plugin. Keep its distributed Skills below
`<plugin-root>/skills/`; do not create or mirror them below this repository's
`.codex/`. Optional Korean reference documents are under `docs/specifications/`;
tracked historical evidence is under `docs/archive/`. Runtime paths are resolved
by `skills/agent/runtime/paths.py` outside the checkout.
</agent-factory>
</INSTRUCTIONS>
