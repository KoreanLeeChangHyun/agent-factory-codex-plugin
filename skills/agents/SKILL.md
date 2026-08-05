---
name: agents
description: Run the Human-facing Main Agent, delegated Intake Agent, or Goal-bound Workflow Agent role.
---

# Agent Factory Agents

## Entry contract

Use this skill for Agent Factory role behavior. Read the complete reference for
the active role before acting. Do not combine role ownership or transfer a
Human-facing decision into the Intake Agent or Workflow Agent.

## Reference routing

- `references/main-agent.md`: Manage Intake recording, one-time execution admission, Goal launch, Korean result review, and post-review integration.
- `references/intake-agent.md`: Run delegated Intake research through codex exec while preserving Main Agent decisions and single-writer canonical Intake ownership.
- `references/workflow-agent.md`: Execute a named Goal-bound Work Unit through Plan, Work, AI Review, and Report without repeating admission.

## Assets and tests

Role contract regression tests live in `tests/`. This skill has no executable
manager; use the lifecycle and domain manager named by the selected reference.
