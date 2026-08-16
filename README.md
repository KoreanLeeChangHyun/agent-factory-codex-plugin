# Agent Factory for Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for fast Human-feedback software delivery. A
Main Agent delegates bounded work to a Work Agent, returns the result
immediately, and records accepted progress afterward through a background
Recording Agent.

## Included skills

The plugin exposes nine modular skills:

- `lifecycle`
- `agents`
- `rules`
- `projects`
- `intakes`
- `work-units`
- `specifications`
- `conventions`
- `synchronization`

`projects` maintains the AI-facing Project Skill in a target repository and
serves a read-only local HTML/CSS/JavaScript view of project context, Git
progress, decisions, and diagrams. Intake, Specification, Work Unit, Work
Package, and linked worktree routes remain available only when explicitly
selected.

Each plugin skill keeps its entry contract in `SKILL.md`, UI metadata in
`agents/openai.yaml`, and detailed capability guidance in `references/`.
Executable managers, schemas, assets, and tests remain inside the owning skill
when that domain needs them.

## Project Skill and local view

In a target repository, initialize the AI-facing Project Skill with:

```bash
python3 <plugin-root>/skills/projects/scripts/project.py init \
  --project-root <project-root> \
  --name <project-name>
```

Serve the Human-facing read-only view on loopback with:

```bash
python3 <plugin-root>/skills/projects/scripts/viewer.py \
  --project-root <project-root>
```

The browser view derives Project Skill references, progress, decisions,
diagrams, and Git status at request time. It does not write project facts.

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
