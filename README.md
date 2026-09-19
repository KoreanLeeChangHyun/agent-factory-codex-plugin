# Agent Factory for Codex

Maintained documentation: English. Human-facing responses support the language
the Human uses or explicitly selects.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory is a Codex plugin for Human-directed software delivery. It provides
a bounded agent workflow, evidence exploration, and shared project conventions.

## VS Code extension relationship

- This plugin is fully installable and usable on its own; the VS Code extension is optional.
- The Agent Factory VS Code extension requires this plugin to be installed and
  enabled at the identical semantic base version. For example, extension `1.0.11`
  accepts plugin `1.0.11+codex.<token>`.

On activation, the extension:

1. Checks configured Codex marketplaces and prefers the official `agent-factory` marketplace.
2. Attempts one installation of a compatible plugin when it is missing or mismatched.
3. Rechecks the installed and enabled state; blocks activation if those conditions
   cannot be satisfied.

For manual installation or update:

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

- The plugin and VS Code extension are released together and must remain on
  matching semantic base versions.
- The extension invokes Codex plugin installation; it does not contain or bundle
  the plugin.

## Distribution units

- **Extension + plugin:** A complete local workflow. It requires no Agent Factory MCP
  package, server, account, tenant, connection, or authenticated resource.
  The extension and plugin MUST have identical semantic base versions and ship together.
  Their separate packages form one coordinated release; both must be available before
  that release is reported complete. The plugin cachebuster is build metadata.
- **MCP:** An independently versioned and deployed application owns Document, Gather,
  Tool, and Workspace capabilities. It requires neither the extension nor the plugin.
  Its version and release schedule are not tied to the extension/plugin pair.
- These are independent services. This plugin's distributed Skills describe only the
  extension/plugin service; MCP usage and operations belong to that service.

## Included Skills and agent model

The plugin exposes three public Skills:

- `agent` supports direct Main input and six per-message execution actions through Main and managed sessions.
- `convention` owns the core model and shared project conventions.
- `document` owns Document authoring, classification, storage, local catalog/search and
  Codex Skill synchronization.

- Main communicates with the Human, delegates bounded tasks, and integrates results.
- Ordinary input defaults to direct Main execution. Work, Plan, Verification, Plan·Work,
  Work·Verification and Plan·Work·Verification actions apply to one message only.
- Plan alone uses actual Work Plan collaboration mode and stops after planning.
  Standalone Verification dispatches a managed verifier for an explicit target, otherwise
  prior completed work in the current chat; missing targets require a Human answer.
- `plan-work` runs actual Plan then default implementation in the same Work
  thread, followed by Main checks without separate Verification.
- Work-bound verification modes check completed Work independently, with optional actual
  Plan/default turns in the same Work thread. See the
  [execution modes contract](skills/agent/references/execution-modes.md).
- Evidence exploration is a Work capability, also available to Main in direct mode.
- Interview is a Main capability. Neither exploration nor Interview adds a Skill or role.
- Codex CLI is the default interface. The same graph can also be hosted through
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

- Start a new Codex thread after installation or update so the Skills and tools are loaded.
- The plugin manifest is `.codex-plugin/plugin.json`.
- The three distributed Skills are under `skills/`; they are not mirrored into a
  repository-local `.codex/`.

## Document synchronization

- Agents explicitly invoke the [Document Skill synchronization CLI](skills/document/SKILL.md#continuous-codex-synchronization)
  after creating, modifying or deleting `docs/skills/` packages and inspect its result.
- Synchronization manages only manifest-owned output, preserves unowned skills, and reports
  independent destination changes as conflicts. Existing legacy mirrors are not adopted.
- No automatic plugin hooks are bundled. Human edits wait for an explicit invocation.

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

- These are compatibility boundaries, not proof that a particular host, account,
  model, tier, or sandbox is ready.

## Detailed documentation

Durable contracts remain with their owning Skill and references:

- [Agent Skill](skills/agent/SKILL.md): graph roles, delegation, and execution.
- [Convention Skill](skills/convention/SKILL.md): shared conventions and ownership.
- [Runtime contract](skills/agent/references/home-runtime.md): managed sessions,
  paths, receipts, recovery, containment, and migration.
- [Document Skill](skills/document/SKILL.md): mandatory common writing rules,
  storage, Original/Processed catalog and search, export and synchronization.
- Type-specific writing: [Specification](skills/document/references/specification.md),
  [Processed](skills/document/references/processed.md), and [Original](skills/document/references/original.md).
- [Development](skills/convention/references/development.md): changes, Git
  publication authority and technical documentation.
- Repository development and release rules: `../docs/skills/rule-plugin-development/SKILL.md`
  (project-local; not part of the distributed Skills).
- [Testing](skills/convention/references/testing.md): test organization and
  verification boundaries.
- [Native Fast and Goal](skills/agent/references/native-fast-goal.md) and
  [project-specialized Work](skills/agent/references/project-specialist.md):
  optional execution guidance and specialization design.

## Status

Feedback and issue reports are welcome.

## License

MIT License. See [LICENSE](LICENSE).
