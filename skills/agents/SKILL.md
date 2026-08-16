---
name: agents
description: Run the Human-facing Main Agent or a bounded Work, Recording, Intake, Workflow, Test, Documentation, or Review Agent role.
---

# Agent Factory Agents

## Entry contract

Use this skill for Agent Factory role behavior. Read the complete reference for
the active role before acting. Do not combine role ownership or transfer a
Human-facing decision into the Intake Agent or Workflow Agent.

## Reference routing

- `references/main-agent.md`: Collect Human feedback, dispatch fast Work Agents, return results, and start post-feedback Recording Agents.
- `references/work-agent.md`: Implement one bounded task directly in the current Git workspace and return a compact receipt.
- `references/recording-agent.md`: Record accepted decisions and completed work after Human feedback without blocking delivery.
- `references/intake-agent.md`: Run delegated Intake research through codex exec while preserving Main Agent decisions and single-writer canonical Intake ownership.
- `references/workflow-agent.md`: Execute an explicitly requested named Work Unit through the optional advanced lifecycle.
- `references/test-agent.md`: Run only Human-authorized bounded verification commands without modifying implementation artifacts.
- `references/documentation-agent.md`: Update affected documents inside an explicitly selected advanced route.
- `references/review-agent.md`: Perform optional independent static review inside an explicitly selected advanced route.

## Assets and tests

Role contract regression tests live in `tests/`. Run them only when the Human
explicitly requests testing; use an exact supplied command unchanged or select
the smallest bounded command from repository evidence.
