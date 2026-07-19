# Agent Factory for Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for structured software delivery through an
Intake, Work Unit, Execution, and Human Review lifecycle.

## Included skills

- Lifecycle routing and evidence-first project analysis
- Intake and specification artifact management
- Work Unit planning and execution
- Human review preparation
- Research, interview, diagram, and integration support

## Local installation

Remote marketplace installation is not available yet. For local development,
clone this repository and add a personal or repository marketplace entry that
points to the clone as the `agent-factory` plugin source. Marketplace packaging
for one-command remote installation is planned after the plugin stabilizes.

The plugin manifest is located at `.codex-plugin/plugin.json`, and reusable
workflows are under `skills/`.

After installing or updating the plugin, start a new Codex thread so newly
loaded skills and tools are available.

## Development

Validate the plugin structure with Codex's plugin validation tooling, then run
the focused Python test suites under each changed skill before publishing an
update.

## Status

Alpha. Feedback and issue reports are welcome, but production compatibility is
not guaranteed yet.

## License

MIT License. See [LICENSE](LICENSE).
