---
name: agent
description: Run the Agent Factory Main, Work, and Verification graph from a CLI or hosted interface with managed Codex exec sessions for delegated roles.
metadata:
  specification-id: agent
---

# Agent Factory Agent

## Roles and graph

`Main -> Work -> Verification`; no extra roles, nodes or routes.

- **Main:** converse, delegate, integrate; perform neither child role.
- **Work:** execute; no self-verification or commits.
- **Verification:** independently check the exact completed Work run; no repair.
- **Fail:** return to the same Work session; reuse the Verification session.
- **END:** Verification pass or evidenced Human skip. Record skip before the next
  Verification; apply after initial/revision Work completes, starting no further
  Verification. Intent, failure, cancellation or input requests alone never end the graph.

## Delegation

- Require clear outcome, scope, constraints, completion criteria and explicit
  Human execution instruction. Conversation/task shaping authorizes no dispatch.
- Continue conversation during child work; apply input to the active task.
  Record explicit redirects as control-plane transitions; preserve execution/results.
- CLI (default), exec and VS Code expose the same Main role.
- Parallelize only independent paths, writes and shared resources. Give chains
  distinct Agent/loop/run IDs, bounded inputs, authority and capabilities.
  Main sequences dependencies/integration and owns conflict avoidance.

## Execution and shared contracts

- **Git:** follow [Convention's publication contract](../convention/references/development.md#git-publication).
- **Domains/storage:** read [core model](../convention/references/agent-factory-core.md)
  and [layout](../convention/references/directory-structure.md).

## References

Read before the corresponding operation:

- `references/home-runtime.md`: dispatch, sessions, receipts, prompts, containment, bindings, storage and migration.
- `references/reporting.md`: optional cloud reporting configuration, delivery and evidence.
- `references/native-fast-goal.md`: installed Codex Fast and native Goal.
- `references/project-specialist.md`: project-specialized Work profiles.
