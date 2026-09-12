# Agent Factory for Codex

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for Human-directed software delivery. It provides
a bounded agent workflow, evidence exploration, and shared project conventions.

## Product modes

- **Plugin only:** A complete local workflow. It requires no Agent Factory MCP
  package, server, account, tenant, connection, or authenticated resource.
- **MCP only:** An independently installed MCP application owns its Document,
  Gather, Tool, and Workspace capabilities without requiring this plugin.
- **Plugin plus MCP:** Explicitly selected and authorized connected capabilities
  can extend the local workflow. They do not take over graph authority or
  implicitly transmit local artifacts.

## Included Skills and agent model

The plugin exposes exactly two public Skills:

- `agent` runs the `Main -> Work -> Verification` graph through managed sessions.
- `convention` owns the core model and shared project conventions.

Main communicates with the Human, delegates bounded tasks, and integrates results.
Work performs the task. Verification independently checks the completed Work and
returns pass or fail unless the Human explicitly skips it. Evidence exploration is
a Work capability, and Interview is a Main capability; neither adds a Skill or role.

Codex CLI is the default interface. The same graph can also be hosted through
`codex exec` or surfaced by a VS Code extension.

## Installation

Add the GitHub-backed marketplace and install the plugin:

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin add agent-factory@agent-factory
```

To install a published update:

```bash
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

Start a new Codex thread after installation or update so the Skills and tools are
loaded. The plugin manifest is `.codex-plugin/plugin.json`; the two distributed
Skills are under `skills/`. They are not mirrored into a repository-local `.codex/`.

## Compatibility

- **Operating system:** Managed execution supports Linux. WSL must satisfy the
  Linux checks; macOS and native Windows are not supported.
- **Python:** Python 3.10 is the source-level minimum. Release verification covers
  the configured Python 3.10 and 3.12 baselines.
- **Codex:** No repository-wide CLI version is assumed. Runtime preflight and
  installed-capability discovery determine readiness for the selected executable.
- **Containment:** User systemd with cgroup v2 is preferred. The private
  process-group fallback provides weaker descendant containment.

These are compatibility boundaries, not proof that a particular host, account,
model, tier, or sandbox is ready.

## Detailed documentation

Durable contracts remain with their owning Skill and references:

- [Agent Skill](skills/agent/SKILL.md): graph roles, delegation, and execution.
- [Convention Skill](skills/convention/SKILL.md): shared conventions and ownership.
- [Core model](skills/convention/references/agent-factory-core.md): roles,
  capabilities, authority, and product boundaries.
- [Runtime contract](skills/agent/references/home-runtime.md): managed sessions,
  paths, receipts, recovery, containment, and migration.
- [Directory structure](skills/convention/references/directory-structure.md):
  source, installation, runtime, cloud, and legacy layout.
- [Documents](skills/convention/references/documents.md): document types, routing,
  formats, projections, and synchronization.
- [Development](skills/convention/references/development.md): changes, Git
  publication, technical documentation, and release readiness.
- [Testing](skills/convention/references/testing.md): test organization and
  verification boundaries.
- [Native Fast and Goal](skills/agent/references/native-fast-goal.md) and
  [project-specialized Work](skills/agent/references/project-specialist.md):
  optional execution guidance and specialization design.

## Status

Alpha. Feedback and issue reports are welcome, but production compatibility is
not guaranteed yet.

## License

MIT License. See [LICENSE](LICENSE).
