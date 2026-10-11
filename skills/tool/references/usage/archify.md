# `archify.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `install`: Download and verify the pinned official renderer; no npm/global install.
Required: `--tool-dir TOOL_DIR`

## `preview`: Validate JSON from stdin and return an isolated SVG preview; writes no project files.
Required: `--tool-dir TOOL_DIR`

## `validate`: Validate JSON with the official schema.
Required: `--project-root PROJECT_ROOT`, `--tool-dir TOOL_DIR`, `input INPUT`

## `render`: Validate then deliver HTML without replacing files.
Required: `--project-root PROJECT_ROOT`, `--tool-dir TOOL_DIR`, `input INPUT`, `--output OUTPUT`
- `--open`: Open generated HTML in the local OS browser.

## `open`: Open an existing artifact HTML in the local OS browser.
Required: `--project-root PROJECT_ROOT`, `output OUTPUT`
