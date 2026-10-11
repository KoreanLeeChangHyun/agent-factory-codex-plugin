# `conductor.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `init`
Required: `--chat-id CHAT_ID`, `--input INPUT`

## `receive`
Required: `--chat-id CHAT_ID`, `--input INPUT`

## `reserve`
Required: `--chat-id CHAT_ID`, `--session-id SESSION_ID`

## `dispatch`
Required: `--chat-id CHAT_ID`, `--run-id RUN_ID`

## `observe`
Required: `--chat-id CHAT_ID`, `--run-id RUN_ID`
- `--input INPUT`: Goal-linked progress evidence bound to managed runId/taskRevision/source; status comes from exec.py

## `decision`
Required: `--chat-id CHAT_ID`, `--input INPUT`, `--run-id RUN_ID`

## `answer`
Required: `--chat-id CHAT_ID`, `--input INPUT`

## `switch-provider`
Required: `--chat-id CHAT_ID`, `--input INPUT`

## `retry`
Required: `--chat-id CHAT_ID`, `--input INPUT`

## `inspect`
Required: `--chat-id CHAT_ID`, `--input INPUT`, `--run-id RUN_ID`

## `reports`
Required: `--chat-id CHAT_ID`, `--consumer CONSUMER`
- `--ack ACK`: Persist last fully applied event sequence; replay uses stable event IDs

## `status`
Required: `--chat-id CHAT_ID`
