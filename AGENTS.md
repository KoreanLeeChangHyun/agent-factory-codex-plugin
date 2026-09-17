<INSTRUCTIONS>
<agent-factory>
# Plugin guidance

- This repository is the Agent Factory plugin, with exactly two public Skills:
  `agent` and `convention`.
- Read the relevant owning Skill and references before acting; maintain detailed
  contracts there rather than duplicating them in this entrypoint.

## Reference locations

- Managed execution and role boundaries: [Agent](skills/agent/SKILL.md);
  [execution modes](skills/agent/references/execution-modes.md) and
  [Work profiles](skills/agent/references/project-specialist.md).
- Runtime paths, sessions and receipts:
  [local runtime](skills/agent/references/home-runtime.md).
- Shared rules and reference index: [Convention](skills/convention/SKILL.md);
  [core model](skills/convention/references/agent-factory-core.md),
  [layout](skills/convention/references/directory-structure.md) and
  [Document ownership](skills/convention/references/documents.md).
- Changes, shared checkout, commits and release readiness:
  [development](skills/convention/references/development.md).
- Test organization, selection and execution authority:
  [testing](skills/convention/references/testing.md).
- Human-facing language and respectful register:
  [communication](skills/convention/references/communication.md).

## Ownership and storage

- Keep distributed Skills under `skills/`; preserve their identities and do not
  mirror them into this repository's `.codex/`.
- Agent entrypoints live in `skills/agent/scripts/`, support code in
  `skills/agent/runtime/`, and role prompts in `skills/agent/prompt/`.
- Resolve runtime storage through `skills/agent/runtime/paths.py`, outside the
  checkout; do not create a checkout `.agent-factory/` runtime.
- Standalone operation is complete. Document, Gather, Tool and Workspace remain
  MCP-owned; keep their backends and assets out of this plugin. Connected use
  requires explicit selection and applicable authorization.
- `skills/convention/assets/AGENTS.md` is a consumer bootstrap template, separate
  from this repository's guidance; follow Convention's bootstrap contract.

## Contribution boundaries

- Keep plugin documentation and Provider execution guidance in English.
- Use the shared checkout, preserve unrelated work and stay within assigned paths.
- Work performs no self-verification or commits; follow the owning Agent and
  testing contracts for the selected execution route.
- Keep tests grouped under `tests/` by the categories in the testing contract.
  Release and publication changes follow the development contract.
</agent-factory>
</INSTRUCTIONS>
