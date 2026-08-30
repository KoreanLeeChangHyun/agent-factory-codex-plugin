# Codex exec options inquiry — unrefined working notes

Inquiry boundary: local `codex-cli 0.149.1`, its complete visible exec-family help,
hidden aliases found by parser probes, directly relevant global/config controls,
and the current Agent Factory command builder plus its uncommitted patch. No
product policy chosen. No project tests/builds/linters/type checks run.

## Local binary

- PATH: `/home/deus/.local/bin/codex`
- resolved binary: `/home/deus/.codex/packages/standalone/releases/0.149.1-x86_64-unknown-linux-musl/bin/codex`
- version: `codex-cli 0.149.1`
- package metadata: `/home/deus/.codex/packages/standalone/releases/0.149.1-x86_64-unknown-linux-musl/codex-package.json`

Help inspected: `codex --help`, `codex exec --help`, and full/short help for
`exec resume`, `exec fork`, and `exec review`. Parser-only probes established
that exec-parent-only flags such as `--cd`, `--sandbox`, `--profile`, and
`--approve-for-me` are accepted before `resume`, but rejected after it. Root
`--ask-for-approval` is accepted before `exec`, not after it. Hidden aliases
`--yolo` and `--experimental-json` parse; documented `--full-auto` does not in
this build.

## Strong observations

- New exec takes prompt argument, `-`, or omitted prompt from stdin. If a prompt
  argument and piped stdin both exist, stdin is appended as a `<stdin>` block.
- Resume takes `[SESSION_ID] [PROMPT]`; omitted prompt also reads stdin, as does
  explicit `-`. `--last` silently dominated a supplied non-UUID positional in a
  probe and selected the newest session, which then failed because it already
  had an active writer. Exact IDs must therefore be used without `--last`.
- Fork requires a session ID; omitted prompt means no follow-up prompt, while
  explicit `-` reads stdin.
- Review has a built-in prompt when omitted; explicit `-` reads stdin. The
  target selectors `--uncommitted`, `--base`, and `--commit` are mutually
  exclusive. A custom prompt is also reported by the parser as conflicting
  with a selector.
- Current managed initial command used `--sandbox danger-full-access` (not the
  bypass flag). Its persisted turn context records cwd as the project root,
  `approval_policy: never`, sandbox `danger-full-access`, and model
  `gpt-5.6-sol`; source rollout:
  `/home/deus/.codex/sessions/2026/08/26/rollout-2026-08-26T22-50-23-01a03e56-117e-7232-801a-2ced9ab6bd10.jsonl`.
- Historical Agent runs configured as danger-full-access nevertheless contain
  resumed-turn bubblewrap failures, including
  `.agent-factory/agent/agent-runtime-smoke-20260824/runs/run-20260826T133600390936Z-8b92a458/stderr.log`.
  This is consistent with the old resume command omitting the managed sandbox
  setting and is direct evidence that relying on session history alone did not
  preserve the intended effective sandbox on this host.

## Official sources

- CLI reference: https://developers.openai.com/codex/cli/reference
- Non-interactive mode: https://developers.openai.com/codex/noninteractive
- Config basics and precedence: https://developers.openai.com/codex/config-basic
- Config reference: https://developers.openai.com/codex/config-reference

The live docs say flags/`-c` outrank project config, selected profile, user
config, system config, and built-ins. They describe exec's built-in default as
read-only, `--json` as a JSONL event stream, `--output-schema` as final-output
schema validation, and `--ephemeral` as disabling rollout persistence. The docs
are not version-pinned and already differ from local 0.149.1 on `--full-auto`
and the visibility of aliases, so local help/parser behavior is controlling for
the installed runtime.

## Accidental/limited experiment

A review-option probe went beyond parsing and started one `codex exec review
--uncommitted` run. It printed effective defaults (`approval: never`,
workspace-write sandbox), then was terminated explicitly. It created session
`01a03e58-cd0a-7253-bd6d-86ad0308c557`; no product file change was requested or
observed. No further model-backed matrix was attempted.
