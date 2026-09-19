# Agent Factory for Codex

English | [한국어](README.ko.md)

Human-facing responses support the language the Human uses or explicitly selects.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory is a Codex plugin for Human-directed software delivery. It provides
a bounded agent workflow, evidence exploration, and shared project conventions.

## VS Code extension

- This plugin is fully installable and usable on its own; the VS Code extension is optional.
- The Agent Factory VS Code extension requires this plugin to be installed and
  enabled at the identical semantic base version. For example, extension `1.0.12`
  accepts plugin `1.0.12+codex.<token>`.

- On activation, the extension checks whether the plugin is installed, enabled, and compatible,
  and attempts automatic installation when needed. An already active, compatible plugin is used without reinstalling.
  If compatibility cannot be confirmed afterward, activation stops with an error.
- To install or update it yourself, see [Manual installation](#manual-installation) below.

## Skills

The plugin exposes three public Skills:

- [Agent](skills/agent/SKILL.md): Dispatches Work and Verification agents and manages
  their sessions, execution progress, and results.
- [Convention](skills/convention/SKILL.md): Provides shared rules for communication,
  user decisions, development, testing, research, and interviews.
- [Document](skills/document/SKILL.md): Guides project document writing, organization,
  storage, and search, and synchronizes project specifications to Codex Skills.

### Agent execution

- Main communicates with you and handles tasks in ordinary messages directly by default.
- For each message, you can select Work (delegate a task), Plan (create a plan only),
  or Verification (check existing work). Combine planning, work, and verification with
  Plan·Work, Work·Verification, or Plan·Work·Verification.
- Your selection applies only to that message. See the
  [execution guide](skills/agent/references/execution-modes.md) for details.
- Research and interviews help gather evidence and clarify requirements.

## Manual installation

- The Agent Factory VS Code extension installs the plugin automatically by default.
- To use the plugin on its own or install it manually, run:

  ```bash
  codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
  codex plugin add agent-factory@agent-factory
  ```

- To install a published update:

  ```bash
  codex plugin marketplace upgrade agent-factory
  codex plugin add agent-factory@agent-factory
  ```

- Start a new Codex thread after installation or update so the Skills and tools are loaded.

## Document synchronization

- Project specification documents written according to Agent Factory rules in `docs/skills/`
  are synchronized to `.codex/skills/`, making them available to Codex as project Skills.
- After writing project specification documents in `docs/skills/`, agents run the
  [Document Skill synchronization script](skills/document/SKILL.md#continuous-codex-synchronization)
  and check the result. They also run it after modifying or deleting these documents.
- If synchronized documents are edited independently, synchronization reports a conflict
  and stops to preserve those changes.
- Existing Skills outside managed synchronization are preserved without modification.
  Document migration may proceed according to Agent Factory rules only when the user
  explicitly requests it, and only within the requested scope.

## Compatibility

- **Operating system:** Execution supports Linux and macOS; WSL must meet the Linux requirements.
  Native Windows is unsupported. macOS requires validation in your actual environment.
- **Python:** Python 3.10+.
- **Codex:** Codex CLI must be installed. Required capabilities and environment readiness are checked before execution.
- See [host readiness](skills/agent/references/home-runtime.md#host-readiness-and-diagnostics)
  for environment-specific requirements and limitations.

## Bug reports

Please report bugs by email to [m.leechanghyun@gmail.com](mailto:m.leechanghyun@gmail.com).

## License

MIT License. See [LICENSE](LICENSE).
