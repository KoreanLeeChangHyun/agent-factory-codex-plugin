# Agent Factory for Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for Human-directed software delivery. It routes
bounded implementation through managed Work and independent Review Agents,
supports resumable investigation, maintains refined project Specifications,
and gathers distributed source material without promoting it to trusted truth.

## Included skills

The plugin exposes exactly five public skills:

- `agent`: Run the Main, Work, Review, and Inquiry Agent roles through the
  managed `codex exec` session runtime.
- `convention`: Apply annotation and SVG-only user-interface conventions.
- `inquery`: Maintain temporary unrefined Markdown investigation workspaces for
  uncertain questions.
- `specification`: Maintain one refined body of trusted project knowledge with
  paired Human-facing HTML/CSS/JavaScript and AI-facing Project Skill views.
- `gather`: Locate, import, refresh, or mirror distributed sources while
  preserving fidelity, provenance, identity, and resolved destinations.

Gathered collections remain evidence. Gather does not reconcile their claims,
refine them, or promote them into a trusted Specification. Operational Agent
sessions, Inquiry workspaces, and Specification collections remain separate.

Each plugin skill keeps its entry contract in `SKILL.md`, UI metadata in
`agents/openai.yaml`, and detailed capability guidance in `references/`.
Executable managers, schemas, assets, and tests remain inside the owning skill
when that domain needs them.

## Local installation

Install the GitHub-backed marketplace and the plugin with Codex CLI:

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin add agent-factory@agent-factory
```

To pick up a published update:

```bash
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

The plugin manifest is located at `.codex-plugin/plugin.json`, and reusable
workflows are under `skills/`.

After installing or updating the plugin, start a new Codex thread so newly
loaded skills and tools are available.

## Development

Validate the plugin structure with the bundled Plugin Creator validator:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" .
```

Run only the exact test commands the Human explicitly names. This authority boundary
also applies to smoke checks, lint, type checks, build verification, and other
commands whose purpose is to verify a change. When no test is explicitly
requested, report that tests were not run and leave verification to Human
review.

## Status

Alpha. Feedback and issue reports are welcome, but production compatibility is
not guaranteed yet.

## License

MIT License. See [LICENSE](LICENSE).
