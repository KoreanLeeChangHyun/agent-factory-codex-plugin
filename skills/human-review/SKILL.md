---
name: human-review
description: Create Korean Human-facing Agent Factory result review material for rework or complete decisions.
---

# Human Review

Write all Human-facing review material in Korean.

After Work Unit Execution, present:

- delivered scope and exclusions;
- changed paths or updated canonical Specification;
- exact verification commands and results;
- AI review findings;
- remaining risks or failed checks;
- whether the execution mode requires Git integration.

Ask for one review decision:

- `rework`: the Human supplies the exact rework instruction.
- `complete`: the result is accepted as complete; a worktree-mode Work Unit is
  integrated automatically and retained for later batch cleanup.

This is result review, not an approval gate. Do not request a checkpoint,
separate merge approval, or cleanup approval. Do not ask again about decisions
already present in the canonical artifacts.

Push, deployment, branch deletion, and PR promotion are outside this review
unless the Human explicitly adds them.
