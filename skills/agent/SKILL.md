---
name: agent
description: Dispatch and manage Agent Factory Work and Verification runs, sessions, and execution results. Use for managed execution operations, not greetings or ordinary conversation merely hosted by Agent Factory.
metadata:
  specification-id: agent
---

# Agent Factory Agent

Use this Skill for the managed operation being performed, not just because the
conversation runs in Agent Factory. Reuse instructions already present in context;
read only references required for the next operation.

## Roles and graph

Execution mode is captured per submitted task; conversation always remains Main.
The default for new Main requests is `work`. See [execution modes](references/execution-modes.md).

- **direct:** Main performs bounded work and appropriate own checks directly.
- **work:** Main delegates Work, then performs appropriate own checks and integrates;
  no separate Verification. Report it as not requested, never a pass or Human skip.
- **work-verification:** Main -> Work -> Verification.
- **plan-work-verification:** the same Work session uses actual Codex Plan mode,
  automatically transitions to default execution mode, then separate Verification.
- **Work:** execute; no self-verification, coordination or commits.
- **Verification:** independently check the exact completed Work run; no repair.
- **Fail in verification modes:** return to the same Work and Verification sessions.
- **END:** direct/Work route completion after appropriate Main checks; verification
  routes require pass or evidenced Human skip applied after completed Work.
  Record skip before the next Verification; never equate failure/cancellation/input
  requests with completion. Mode selection is independent of Human approval policy.

## Delegation

- Under every approval policy, Main answers greetings, thanks, casual conversation
  and questions answerable from available context directly, without managed children
  or unnecessary tools. Keep replies proportional and omit execution reports for
  conversation; read the managed request as required; the runtime persists the final response. Preserve active
  authorized work when responding to conversational steering.
- Under the default Human approval policy, require clear outcome, scope, constraints,
  completion criteria and explicit Human execution instruction. Under runtime-injected
  `bypass`, a Human request for work authorizes immediate bounded dispatch without a
  separate plan approval. Conversation alone authorizes no dispatch under either policy.
- Continue conversation during child work; apply input to the active task.
  Record explicit redirects as control-plane transitions; preserve execution/results.
- CLI (default), exec and VS Code expose the same Main role.
- Parallelize only independent paths, writes and shared resources. Give chains
  distinct Agent/loop/run IDs, bounded inputs, authority and capabilities.
  Main sequences dependencies/integration and owns conflict avoidance. Use one
  shared checkout without separate Git worktrees; follow Convention's
  [shared checkout coordination](../convention/references/development.md#shared-checkout-coordination).

## Execution and shared contracts

- **Standalone:** Main, Work, Verification and local exec/loop are complete without
  an MCP package, server, account, tenant, connection or authenticated resource.
  Optional integrations require an available connection plus explicit selection
  and applicable Human authority; discovery alone never transmits local artifacts.
- **Git:** follow [Convention's publication contract](../convention/references/development.md#git-publication).
- **Domains/storage operations:** read [core model](../convention/references/agent-factory-core.md)
  and [layout](../convention/references/directory-structure.md).
- **Human communication:** always follow Convention's mandatory
  [respectful-register contract](../convention/references/communication.md).

## References

Read before the corresponding operation:

- `references/execution-modes.md`: captured execution routes, completion rules, runtime interface and Plan transitions.
- `references/home-runtime.md`: dispatch, sessions, receipts, prompts, containment, bindings, storage and migration.
- `references/reporting.md`: optional cloud reporting configuration, delivery and evidence.
- `references/native-fast-goal.md`: installed Codex Fast and native Goal.
- `references/project-specialist.md`: project-specialized Work profiles.
