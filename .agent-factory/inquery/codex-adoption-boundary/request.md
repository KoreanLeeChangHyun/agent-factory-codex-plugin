# Inquiry request: Codex adoption boundary

## Human question

"코덱스에서 무엇을 가져가고 무엇을 버릴것인가"

Interpret this as: for the Agent Factory Codex plugin in the current repository,
which concepts and mechanisms should be retained or adopted from native Codex,
and which Agent Factory mechanisms should be removed, avoided, or delegated back
to Codex?

## Scope

- Inspect the current working tree without modifying canonical project files.
- Treat the large existing dirty-tree deletion/refactor as Human-owned work and do
  not alter, restore, or clean it.
- Use the current repository files, recent Git history, and the fresh official
  Codex manual at `/tmp/openai-docs-cache/codex-manual.md` as evidence.
- Focus on product architecture and ownership boundaries: Human interaction,
  agent roles, session/runtime management, context/artifacts, skills/plugins,
  tests/review, safety/permissions, synchronization/connectors, and UI.
- Distinguish three outcomes where useful: keep/adopt, discard/delegate to native
  Codex, and retain only as an optional advanced route.
- Identify contradictions between the README and the current tree if material.
- Do not implement changes, run tests, or make Human-owned product decisions.

## Completion condition

Produce an evidence-backed Korean recommendation that is decisive enough for
the Main Agent to discuss with the Human. Include:

1. A one-sentence thesis.
2. A compact keep/discard/optional matrix with reasons.
3. The smallest coherent Agent Factory core that remains.
4. The top deletion/simplification priorities.
5. Important limitations or decisions the Human still owns.
6. Precise repository paths and official manual sections/URLs supporting the
   conclusions.

Write detailed working notes in this Inquiry workspace and the final detailed
result to the runtime-declared result path.
