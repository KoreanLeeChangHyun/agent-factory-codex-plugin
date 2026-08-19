---
name: inquery
description: Manage temporary Inquiry Agent workspaces and unrefined Markdown investigation documents. Use when Codex must research, analyze, study, compare evidence, explore hypotheses, or continue an uncertain question across resumable Agent turns without turning the working material into a Human-facing Specification or refined Project Skill.
---

# Agent Factory Inquery

## Entry contract

Use one isolated Inquiry workspace for one uncertain question or topic. Read
`references/workspace.md` completely before creating or updating Inquiry files.

Run the Inquiry through the managed Agent runtime with role `inquery`. Preserve
the exact Codex session identifier and resume that session for follow-up turns
on the same Inquiry. Use a new Inquiry and Agent session for a different topic.

## Inquiry boundary

Store the Inquiry workspace below:

```text
<project-root>/.agent-factory/inquiries/<inquiry-id>/
```

Let the Inquiry Agent freely organize files inside its own workspace. Write
AI-generated investigation documents as unrefined Markdown. Temporary source
material, extracts, experimental files, and intermediate outputs may accompany
the Markdown when the Inquiry needs them.

Treat the workspace as temporary AI working material, not a canonical evidence
ledger, conversation transcript, accepted project fact, refined Project Skill,
or Human-facing Specification. Do not require a fixed document schema or
section template.

## Session separation

Keep managed Codex session identifiers, requests, runs, state, events,
heartbeats, and terminal results below:

```text
<project-root>/.agent-factory/agent/
```

Do not duplicate the session runtime into the Inquiry workspace. The runtime
may associate a session with an Inquiry path, but session state remains owned
by `.agent-factory/agent/`.

## Investigation conduct

- Keep the Human's question, scope, constraints, and completion condition
  unchanged.
- Separate observed facts, source material, analysis, hypotheses, conclusions,
  contradictions, limitations, and unresolved decisions.
- Preserve source locations and enough provenance for another Agent or the
  Human to inspect the basis.
- Treat missing project-specific facts as unknown.
- Do not implement product changes or choose a Human-owned product, priority,
  risk, approval, or acceptance decision.
- Do not run tests or verification based on Agent judgment. Testing remains
  Human-led and requires a separate explicit Human plan.

## Result

Write detailed working material in the Inquiry workspace and publish the
managed run result through the result path declared by the Agent runtime.
Identify the investigated boundary, evidence, conclusions, limitations,
unresolved decisions, and smallest useful follow-up Inquiry.

Do not automatically convert or promote Inquiry material into a Specification
or Project Skill. Perform that work only after a separate explicit Human
request for the target document class.
