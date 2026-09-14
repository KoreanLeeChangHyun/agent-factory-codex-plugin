# Agent Factory for Codex

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory is a Codex plugin for Human-directed software delivery. It provides
a bounded agent workflow, evidence exploration, and shared project conventions.

## VS Code extension relationship

This plugin is fully installable and usable on its own; the VS Code extension is
optional. The Agent Factory VS Code extension, however, requires this plugin to be
installed and enabled at the identical semantic base version. For example, extension
`1.0.6` accepts plugin `1.0.6+codex.<token>`.

On activation, the extension checks configured Codex marketplaces, prefers the
official `agent-factory` marketplace, and attempts one installation of a compatible
plugin when the plugin is missing or mismatched. It then rechecks the installed and
enabled state. If that cannot be satisfied, activation blocks and the plugin can be
installed or updated manually:

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

The plugin and VS Code extension are released together and must remain on matching
semantic base versions. The extension invokes Codex plugin installation; it does not
contain or bundle the plugin.

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

- `agent` supports four per-request execution modes through Main and managed sessions.
- `convention` owns the core model and shared project conventions.

Main communicates with the Human, delegates bounded tasks, and integrates results.
The default delegates Work without separate Verification; direct mode lets Main
perform the task. Verification modes check completed Work independently, with
optional actual Plan/default turns in the same Work thread. See the
[execution modes contract](skills/agent/references/execution-modes.md). Evidence exploration is
a Work capability (also available to Main in direct mode), and Interview is a Main
capability; neither adds a Skill or role.

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

- **Operating system:** Managed execution has Linux and macOS backends. WSL must
  satisfy the Linux checks; native Windows is unsupported. macOS uses private
  process groups with weaker descendant containment; actual Mac validation is
  required. See [host readiness](skills/agent/references/home-runtime.md#host-readiness-and-diagnostics).
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

Feedback and issue reports are welcome.

## License

MIT License. See [LICENSE](LICENSE).
