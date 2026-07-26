# Verification Evidence

## Execution Target

- Work Unit: `prevent-direct-artifact-json-authoring`
- Revision: `1`
- Attempt: `2`
- Invocation: `019f9c41-ba3a-7003-8ab6-bfa0d75d7b26-verification`
- Git head: `13b0a6ecc43085948f383d3a5545aaef6bcecbb5`

## TDD And Focused Verification

- The initial focused test run failed because the hook policy and generator did
  not exist.
- `python3 skills/lifecycle/tests/test_artifact_json_authoring_hook.py`
  passed 17 tests at the execution target.
- The tests cover direct `apply_patch` add, update, delete, and move; Bash
  redirection, heredoc, Python write, copy, move, split-path construction, and
  arbitrary-writer calls; all three canonical artifact collections; exact
  manager allowlisting; fake manager suffix rejection; read-only and
  non-artifact JSON allowance; malformed-input fail-closed behavior; explicit
  Human-decision validation; exact session, tool, path, expiry, and multi-path
  scope; one-shot consumption and audit records; grant routing; generated hook
  configuration; and skill contract consistency.
- `python3 skills/lifecycle/tests/test_skill_metadata.py` passed 5 tests.
- `python3 hooks/generate_hooks_config.py --check` passed.
- `python3 /home/deus/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .`
  passed.
- `git diff --check` passed.

## Skill Validation

The following commands each returned `Skill is valid!`:

- `python3 /home/deus/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/intake`
- `python3 /home/deus/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/work-unit-planner`
- `python3 /home/deus/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/specification`
- `python3 /home/deus/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/lifecycle`

## Regression Verification

- Lifecycle suite: 32 tests passed.
- Intake manager suite: 32 tests passed.
- Work Unit manager suite: 26 tests passed.
- Specification manager suite: 9 tests passed.
- These suites ran against implementation commit
  `9eaf13860d1eadfd387762b174cad04637a2b3d9`. The later target delta contains
  only Work Unit execution metadata and one additional hook-routing test.
  `git diff --quiet 9eaf13860d1eadfd387762b174cad04637a2b3d9..HEAD -- skills/intake/scripts skills/specification/scripts skills/work-unit-planner/assets/scripts skills/lifecycle/assets/scripts`
  returned success.

## Authoritative Codex Hook Evidence

- The current Codex manual was fetched with
  `/home/deus/.codex/skills/.system/openai-docs/scripts/fetch-codex-manual.mjs`.
- The manual documents default Plugin discovery at `hooks/hooks.json`,
  `PLUGIN_ROOT` and `PLUGIN_DATA`, `PreToolUse` matching for Bash and
  `apply_patch` aliases, tool-input inspection, trust and disable behavior, and
  specialized tool-path opt-out:
  `https://learn.chatgpt.com/docs/hooks.md`.
- Current OpenAI Codex source shows `PreToolUse` input uses `tool_name` and
  `tool_input.command`, and exit code `2` with a stderr reason blocks the tool:
  `https://github.com/openai/codex/blob/main/codex-rs/hooks/src/events/pre_tool_use.rs`.
- Current OpenAI Codex source shows `apply_patch` supplies its raw patch as
  `tool_input.command`:
  `https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/apply_patch.rs`.

## Residual Boundary

- A non-managed Plugin hook requires trust, can be disabled, can time out, and
  does not cover specialized tool paths that opt out of hooks.
- The Agent Factory skill contract remains mandatory when the hook is inactive.
- Absolute organization enforcement requires managed hooks and managed policy;
  this Work Unit does not implement enterprise `requirements.toml`.
- The exception CLI records Human approval as an auditable attestation. A
  Plugin hook cannot independently authenticate the semantics of a chat
  approval, so skills prohibit invoking `grant` without a prior explicit Human
  decision.
