# Agent Factory engineering research synthesis request

## Human question

에이전트 그래프 엔지니어링, 에이전틱 코딩, 에이전틱 엔지니어링,
루프 엔지니어링, 컨텍스트 엔지니어링, 프롬프트 엔지니어링 조사 자료를
취합하여 현재 Agent Factory 에이전트에 적용 가능한 부분을 찾는다.

## Scope

This is an evidence-backed Inquiry, not an implementation task and not a
Specification or Project Skill authoring task. Analyze the existing research
material and the current repository architecture. Do not edit product code,
Skills, tests, Specifications, or canonical project facts.

Use these primary local research reports and their adjacent source catalogs or
source files when a claim needs provenance:

- `.agent-factory/inquery/agent-graph-engineering/report.md`
- `.agent-factory/inquery/graph-engineering/report.md`
- `.agent-factory/inquery/graph-engineering/ai-non-rag-report.md`
- `.agent-factory/inquery/graph-engineering/ai-latest-report.md`
- `.agent-factory/inquery/agentic-coding-20260828/report.md`
- `.agent-factory/inquery/agentic-engineering-20260828/report.md`
- `.agent-factory/inquery/loop-engineering-20260828/evidence-and-observations.md`
- `.agent-factory/inquery/prompt-context-engineering-20260828/report-ko.md`

Inspect the current Agent Factory implementation and contracts, especially:

- `skills/agent/SKILL.md` and `skills/agent/references/*.md`
- `skills/agent/scripts/agent_exec.py`
- `skills/agent/scripts/agent_loop.py`
- `skills/inquery/SKILL.md` and its workspace reference
- the other distributed Skills where relevant
- `.codex-plugin/plugin.json`, repository `AGENTS.md`, and tests only as static
  architecture evidence

Preserve the current explicit architectural constraints, including managed
addressable `codex exec` sessions rather than platform sub-agents, Human-led
test authorization, separation of runtime/Inquiry/Specification/Project Skill
state, independent Review, async dispatch, exact-session resume, atomic file
handoff, heartbeat/timeout/reconcile, and bounded finite loops. If a research
recommendation conflicts with one of these constraints, identify the conflict
instead of silently overriding the project decision.

## Questions to answer

1. Normalize the six overlapping terms and identify the distinct design
   concern each contributes to Agent Factory.
2. Produce a current-state map: which researched practices are already fully
   present, partially present, or absent, with exact repository evidence.
3. Identify concrete adoption candidates at the Agent behavior, runtime,
   loop/graph orchestration, context/prompt construction, evaluation, safety,
   and observability layers.
4. For each candidate, state the problem it solves, evidence/rationale,
   smallest compatible change surface, dependencies, risks, measurable
   validation signal, and whether it is reversible.
5. Prioritize into:
   - keep/standardize now (already present and worth preserving),
   - small next experiments,
   - later conditional investments,
   - reject/defer for Agent Factory.
6. Distinguish facts observed in the repository, source-backed conclusions,
   and hypotheses requiring an experiment. Do not represent speculative graph
   or memory systems as established improvements.
7. Recommend the smallest coherent next implementation slice, but leave the
   product priority and authorization decision to the Human.

## Expected output

Write a detailed Korean Markdown synthesis to
`.agent-factory/inquery/agent-factory-engineering-synthesis-20260828/synthesis.md`
and publish the managed run result through the declared result path. The
synthesis should be decision-useful and concise enough to review, include a
traceability table with source and repository paths, contradictions and
limitations, and the smallest useful follow-up Inquiry. Do not run tests or
verification commands.
