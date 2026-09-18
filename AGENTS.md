<INSTRUCTIONS>
<agent-factory>

# Plugin guidance

- This checkout owns the plugin implementation and package. Extension UI, VSIX and MCP development belong to their respective repositories.

- Agent Factory exposes three public Skills under `skills/`: [agent](skills/agent/SKILL.md), [convention](skills/convention/SKILL.md) and [document](skills/document/SKILL.md). Preserve their identities; never mirror them into `.codex/`.
- Before choosing an edit target, apply the three-domain boundary in the [plugin project rules](docs/skills/rule-plugin-development/SKILL.md). Distributed Skills serve product users; both repositories’ project Skills serve their developers.

## Ownership and storage

- Agent entrypoints, support code and role prompts belong in `skills/agent/scripts/`, `skills/agent/runtime/` and `skills/agent/prompt/`, respectively.
- Resolve runtime storage through `skills/agent/runtime/paths.py`, outside the checkout; never create a checkout `.agent-factory/` runtime.
- The MCP service is independent of the extension/plugin service; keep its usage guidance, implementation and assets out of this product.
- `skills/convention/assets/AGENTS.md` is the consumer bootstrap template; follow Convention's bootstrap contract.

## Contribution boundaries

- For this repository’s development, testing and coordinated release, read the [project Skill](docs/skills/rule-plugin-development/SKILL.md). It is developer guidance, not a user-distributed Skill.

- Keep user-distributed Skill guidance in English; project documents follow their selected language.
- Use the shared checkout; preserve unrelated work and stay within assigned paths.
- Work performs no self-verification or commits; follow the owning Agent's execution route.
- Group tests under `tests/` by Convention's [testing contract](skills/convention/references/testing.md), including its execution boundaries.
- Follow Convention's [development contract](skills/convention/references/development.md) for shared change and Git authority boundaries.
</agent-factory>
</INSTRUCTIONS>
