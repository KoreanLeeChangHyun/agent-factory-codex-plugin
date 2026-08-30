# Sequence Diagrams

Use Mermaid `sequenceDiagram` when the primary relationship is the time-ordered
exchange among participants.

- Name participants by stable actor, component, service, or game-system role.
- Order messages chronologically and distinguish calls, responses, and
  asynchronous signals where the difference matters.
- Use `alt`, `opt`, `loop`, and parallel fragments only when their conditions
  are grounded and improve comprehension.
- Show activation spans only when they clarify responsibility or lifetime.
- Keep domain state changes in message labels or linked behavior diagrams rather
  than turning the sequence into a second state machine.
- Do not invent timing guarantees, retries, concurrency, ownership, or failure
  handling that the evidence does not establish.
- Add `accTitle` and `accDescr` summarizing the participants, interaction goal,
  and important branches.

For game documentation, use a sequence diagram for interactions such as player
detection, boss phase orchestration, animation events, damage resolution, or
environment triggers. Use `behavior.md` when the main subject is one actor's
decision pattern rather than the exchange between actors.

## Official syntax reference

- [Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram)
