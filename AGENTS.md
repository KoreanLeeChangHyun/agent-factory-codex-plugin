<INSTRUCTIONS>
<agent-factory>
# Plugin guidance

- Agent Factory exposes three public Skills under `skills/`: [agent](skills/agent/SKILL.md), [convention](skills/convention/SKILL.md) and [document](skills/document/SKILL.md). Preserve their identities; never mirror them into `.codex/`.
- Read the relevant owning Skill and references before acting; keep detailed contracts there.

## Ownership and storage

- Agent entrypoints, support code and role prompts belong in `skills/agent/scripts/`, `skills/agent/runtime/` and `skills/agent/prompt/`, respectively.
- Resolve runtime storage through `skills/agent/runtime/paths.py`, outside the checkout; never create a checkout `.agent-factory/` runtime.
- Standalone operation is complete. Document, Gather, Tool and Workspace remain MCP-owned; keep their backends and assets out. Connected use requires explicit selection and applicable authorization.
- `skills/convention/assets/AGENTS.md` is the consumer bootstrap template; follow Convention's bootstrap contract.

## Contribution boundaries

- Keep plugin documentation and Provider execution guidance in English.
- Use the shared checkout; preserve unrelated work and stay within assigned paths.
- Work performs no self-verification or commits; follow the owning Agent's execution route.
- Group tests under `tests/` by Convention's [testing contract](skills/convention/references/testing.md), including its execution boundaries.
- Follow Convention's [development contract](skills/convention/references/development.md) for changes, commits, releases and publication.
</agent-factory>
</INSTRUCTIONS>
