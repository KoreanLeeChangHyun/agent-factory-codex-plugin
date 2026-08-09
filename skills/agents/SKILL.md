---
name: agents
description: Run the Human-facing Main Agent or a bounded Intake, Workflow, Test, or Documentation Agent role.
---

# Agent Factory Agents

## Entry contract

Use this skill for Agent Factory role behavior. Read the complete reference for
the active role before acting. Do not combine role ownership or transfer a
Human-facing decision into the Intake Agent or Workflow Agent.

## Reference routing

- `references/main-agent.md`: Manage Intake recording, one-time execution admission, Goal launch, Korean result review, and post-review integration.
- `references/intake-agent.md`: Run delegated Intake research through codex exec while preserving Main Agent decisions and single-writer canonical Intake ownership.
- `references/workflow-agent.md`: Execute only the Plan and implementation Work for a named Goal-bound Work Unit without repeating admission.
- `references/test-agent.md`: Run only exact Human-authorized verification commands without modifying implementation artifacts.
- `references/documentation-agent.md`: Update only directly affected documents after implementation through a mandatory separate Goal.

## Assets and tests

Role contract regression tests live in `tests/`. This skill has no executable
manager; use the lifecycle and domain manager named by the selected reference.
