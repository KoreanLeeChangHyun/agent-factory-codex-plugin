# Artifact JSON authoring guard completion audit

- Work Unit: `prevent-direct-artifact-json-authoring`
- Revision: 1
- Attempt: 3
- Invocation: `019f9c41-ba3a-7003-8ab6-bfa0d75d7b26-completion-audit`
- Verified implementation HEAD: `2905f262c341307bc49cc2bfcfc6a171ac62118f`
- Audit date: 2026-07-26

## Requirement evidence

1. Canonical Intake, Work Unit, and Specification JSON authoring is manager-only.
   - `skills/intake/SKILL.md`
   - `skills/work-unit-planner/SKILL.md`
   - `skills/specification/SKILL.md`
   - `skills/lifecycle/SKILL.md`
   - `skills/lifecycle/references/common-document-contract.md`
   - The contract also forbids filesystem-capable local and MCP tools.
2. The generated Plugin `PreToolUse` hook blocks direct authoring before execution.
   - `apply_patch`, `Edit`, and `Write` aliases are treated as patch tools.
   - Bash redirection, heredoc, interpreter writes, copy/move, custom writers,
     split collection names, and dynamic canonical-root writes or deletion are denied.
   - Exact owning manager commands, single read-only commands, and non-artifact JSON
     remain allowed.
3. The LLM cannot create its own exception grant.
   - An exact `grant` command submitted through an LLM Bash tool call is denied.
   - A Human must run the printed exact command outside Codex tool execution.
   - Only an exact session, tool, artifact, absolute-path set, reason, approval
     reference, unexpired TTL, and one-shot grant can be consumed.
   - Expiry is fail-closed at `current epoch >= expiresAtEpoch`.
   - Grant and consumption events are audited in Plugin data, not canonical artifacts.
4. Hook configuration is generated, not hand-authored.
   - `hooks/generate_hooks_config.py` deterministically creates `hooks/hooks.json`.
   - The generated hook uses the default Plugin hook location, a matcher for Bash and
     patch aliases, and a 30-second timeout.
5. Platform limits are disclosed.
   - Non-managed Plugin hooks require trust, can be disabled, can be skipped by
     specialized tool paths, and can fail open on timeout.
   - Managed hooks and policy are required for an administrator-enforced boundary.

## Verification

- `python3 skills/lifecycle/tests/test_artifact_json_authoring_hook.py`
  - 19 tests passed.
- `python3 -m unittest discover -s skills/lifecycle/tests -p 'test_*.py'`
  - 36 tests passed.
- `python3 skills/lifecycle/tests/test_skill_metadata.py`
  - 5 tests passed.
- Four Skill Creator quick validations passed.
- Plugin Creator validation passed.
- Generated hook configuration check passed.
- `git diff --check` passed.
- Intake, Work Unit, Specification, and shared sectioned-document manager sources
  have no diff from the commit where their full regression suites passed:
  Intake 32, Work Unit 26, and Specification 9 tests.

## Promotion state

The currently installed Agent Factory cache
`0.1.0+codex.20260725184616` has no Plugin `hooks/` directory. The guard becomes
operational only after separate Human decisions for Work Unit approval, main
integration, remote marketplace publication, cachebuster update, Plugin reinstall,
hook trust, and verification from a new thread.

## Authoritative Codex behavior

- Hooks manual: https://learn.chatgpt.com/docs/hooks.md
- PreToolUse implementation:
  https://github.com/openai/codex/blob/main/codex-rs/hooks/src/events/pre_tool_use.rs

The implementation source confirms that matcher aliases preserve canonical
`tool_name`, exit code 2 plus non-empty stderr blocks the tool call, and
`permissionDecision: "ask"` is unsupported and fails open.
