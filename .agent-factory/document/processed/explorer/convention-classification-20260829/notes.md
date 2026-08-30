# Convention / Explorer / Interview classification notes

Information stage: processed investigation material.

## Question and boundary

Classify Explorer and Interview relative to Convention using only the accepted
Agent Factory core and the current distributed Skill contracts. This note does
not change the accepted model or choose whether the Human should redesign it.

## Sources inspected

- `skills/convention/SKILL.md`, especially `Entry contract`.
- `skills/convention/references/agent-factory-core.md`, especially `Authority
  and identity`, `Information lifecycle`, `Core capability topology`,
  `Responsibility matrix`, `Observed current implementation`, and
  `Representation-alignment checklist`.
- `skills/convention/references/agent-factory-core-diagrams.md`, especially
  `Core capability topology` and `Current implementation relationships`.
- `skills/explorer/SKILL.md` and `skills/explorer/references/workspace.md`.
- `skills/interview/SKILL.md` and `skills/interview/references/conduct.md`.
- `.codex-plugin/plugin.json` as current public-surface corroboration.

All sources were read from the local repository on 2026-08-29. No tests,
validators, builds, servers, runtime probes, or external research were used.

## Observation

The accepted ontology explicitly has six public distributed Skills. Convention
is a cross-cutting control capability and owns the durable core semantic model;
Explorer and Interview are separate transformation capabilities with distinct
inputs, actors, outputs, and authority boundaries. Their contracts are
normative because every Skill contract tells an Agent how to apply a
capability; that does not make their capability identity Convention.

## Duplication / ambiguity candidates

- `skills/convention/references/agent-factory-core.md` repeats the Explorer and
  Interview summary in `Core capability topology`, `Responsibility matrix`,
  and `Observed current implementation`. This is partly justified by
  Convention's ownership of the complete core ontology, but the operational
  sequencing details under `Interview` and `Observed current implementation`
  overlap the role contracts.
- `skills/interview/SKILL.md` `Entry contract` and
  `skills/interview/references/conduct.md` `Frame the interview` repeat the
  Main-pause/Explorer-resume/no-Human-impersonation rule almost verbatim.
- `skills/explorer/SKILL.md` `Boundaries` and
  `skills/explorer/references/workspace.md` `Authority` repeat the no-testing,
  no-refinement, and legacy-Inquery boundaries. Some entry/reference
  repetition is defensive, but ownership is not sharply factored.
- `skills/convention/references/agent-factory-core.md` `Convention` defines
  Convention broadly as constraints AI must follow. Read without the adjacent
  topology and matrix, this can falsely imply that every normative Skill is
  Convention. The same section immediately narrows it to a cross-cutting
  control layer, while the matrix and diagrams retain separate capabilities.

## Conclusion

Under the accepted model the ontology answer is option 2. At the file-factoring
level there is a limited mixture: Convention properly owns the canonical
cross-capability summaries, while some operational rules are duplicated between
Convention and the capability-specific contracts and within those contracts.
That duplication does not currently reclassify either capability.

