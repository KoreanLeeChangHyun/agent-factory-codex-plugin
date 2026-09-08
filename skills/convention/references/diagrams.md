# Diagrams

## Shared rules

- Maintain Mermaid source; render SVG with Mermaid.js under `libraries.md`.
- Ground labels and relationships in inspected code, schemas or accepted
  Specifications. Diagrams establish no runtime behavior, authority or completion.
- Include `accTitle`, `accDescr` and readable fallback meaning independent of
  color/geometry. Keep source readable and labels stable/domain-specific.
- Choose the form by the main relationship; split mixed models when reading
  direction becomes unclear. Agent Factory concepts come from
  `agent-factory-core.md`, not a separately maintained example catalog.

## ERD — data structure

- Use `erDiagram`; distinguish conceptual, logical and physical models.
- Use singular domain entity names, explicit cardinality/optionality, meaningful
  relationship labels and keys that clarify identity/joins.
- Include only relevant attributes unless a complete physical schema is required.
  Never infer tables, keys or constraints from naming alone.
- Preserve derivation provenance; schemas, migrations and accepted Specifications
  remain authoritative over the diagram.

## Behavior — game decisions

- Use `stateDiagram-v2` for FSM states, events, guards, transitions and boss phases.
- Use `flowchart` for Behavior Trees with identified Root, Selector, Sequence,
  Condition, Action and relevant Success/Failure/Running semantics. An ordinary
  flowchart is not automatically a Behavior Tree; name boundaries when mixing FSM/BT.
- Use domain states/actions; label causal events/guards. Distinguish conditions
  from actions and interrupts from transitions; show meaningful loops/end states.
- Separate observed, intended and unresolved behavior. Never invent thresholds,
  probabilities, cooldowns, priorities or phase conditions.
- Mermaid renders documentation only. Runtime equivalence needs separate evidence;
  node editing, simulation, tracing and code generation require separate tool decisions.

## Sequence — ordered interaction

- Use `sequenceDiagram` with stable participants and chronological messages;
  distinguish calls, responses and asynchronous signals where relevant.
- Use grounded `alt`, `opt`, `loop` and parallel fragments. Show activation only
  when it clarifies responsibility/lifetime.
- Keep state changes in labels or linked behavior diagrams. Use behavior diagrams
  for one actor's decisions; sequence diagrams for exchanges among actors/systems.
- Never invent timing guarantees, retries, concurrency, ownership or failure handling.

## Syntax references

- [ERD](https://mermaid.js.org/syntax/entityRelationshipDiagram)
- [State](https://mermaid.js.org/syntax/stateDiagram)
- [Flowchart](https://mermaid.js.org/syntax/flowchart)
- [Sequence](https://mermaid.js.org/syntax/sequenceDiagram)
