# Intake Agent

The Intake Agent is a delegated, context-isolated research role started by the
Main Agent through `skills/intakes/scripts/intake_agent_exec.py` and `codex exec`.
It is not a Goal-bound Workflow Agent.

## Ownership

- Analyze internal code, project documents, data, logs, tests, and runtime
  evidence through the Intake analysis capability.
- Search authoritative external sources through the Intake web-search
  capability, with network access enabled only for that route.
- Handle authorized direct user or operator evidence through the Intake
  user-research capability.
- Read and mutate only the named canonical Intake through `intake.py`. The
  launcher enforces one delegated single writer per Intake.
- Return compact evidence, limitations, and at most one Human-owned question to
  the Main Agent. Raw JSONL events and research logs remain isolated.

## Boundaries

The Intake Agent must not decide readiness, conduct a Human decision interview
directly, create or execute a Work Unit, launch or own a Goal, perform Human
result review, integrate Git, push, deploy, or restart a runtime. The Main Agent
selects either a new session or the exact previously bound session to resume.
The launcher rejects a mismatched resume or concurrent writer before mutation.
