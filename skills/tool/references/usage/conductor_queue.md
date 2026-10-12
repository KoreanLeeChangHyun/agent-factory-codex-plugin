# `conductor_queue.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `responsibility`: Query required tasks, pending instructions and completion blockers
Required: `--request-id REQUEST_ID`

## `register-required`: Atomically register an authorized required-task manifest
Required: `--input-json INPUT_JSON`, `--request-id REQUEST_ID`

## `resume-required`: Reconcile durable required tasks without launching a provider

## `role-pools`: Query canonical area role counts and exact task verification bindings

## `configure-role`: Capture an existing role model and permission setting for an area
Required: `--input-json INPUT_JSON`

## `processing-policy`: Set the processing policy inherited only by newly accepted requests
Required: `--input-json INPUT_JSON`

## `hire-role`: Hire or reuse an attributed role with captured settings; native session starts on assignment
Required: `--input-json INPUT_JSON`

## `enroll-worker`: Adopt an explicitly attributed idle Work session with matching settings
Required: `--input-json INPUT_JSON`

## `pool-config`: Configure captured domain/subdomain employment limits and idle reuse
Required: `--input-json INPUT_JSON`

## `subdomain`: Add an explicit child area under an existing domain
Required: `--input-json INPUT_JSON`

## `init`: Create a chat with its captured policy (idempotent; a different policy conflicts)
Required: `--chat-id CHAT_ID`
- `--policy-json POLICY_JSON`: Captured policy JSON; default is the fake development policy

## `ingest`: Accept one conversation/control/lifecycle/progress input
Required: `--chat-id CHAT_ID`, `--class {control,conversation,lifecycle,progress}`, `--input-json INPUT_JSON`

## `snapshot`: UI projection snapshot with its replay cursor
Required: `--chat-id CHAT_ID`

## `replay`: UI projection rows after a cursor; repeated state collapses to its latest version
Required: `--chat-id CHAT_ID`
- `--after AFTER`

## `metrics`: Measured accept/route/conductor/response/UI latencies and queue depths (ms)
- `--chat-id CHAT_ID`

## `quarantined`: Poison deliveries and inputs kept for operator recovery

## `requeue`: Make one quarantined delivery ready again after a fix
Required: `--subscription {conductor,executor,ui}`, `--event-seq EVENT_SEQ`

## `recover`: Requeue abandoned turns and list uncertain attempts (no worker is started)

## `serve`: Leader/follower runtime with a JSON-lines stdin command channel and stdout feed
- `--chat-id CHAT_ID`
- `--conductor-delay CONDUCTOR_DELAY`: Fake conductor model latency in seconds
- `--checkpoint-tokens CHECKPOINT_TOKENS`
- `--tokens-per-turn TOKENS_PER_TURN`

## `demo`: Run a development scenario with the fake conductor and workers; prints the result
- `--chat-id CHAT_ID`
- `--conductor-delay CONDUCTOR_DELAY`: Fake conductor model latency in seconds
- `--checkpoint-tokens CHECKPOINT_TOKENS`
- `--tokens-per-turn TOKENS_PER_TURN`
- `--burst BURST`: Progress events per worker step in the flood scenario
