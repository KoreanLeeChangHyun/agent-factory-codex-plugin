# Diagrams

<a id="document-assets"></a>

## 1. Document assets

- Processed and Specification packages store each diagram or structured system
  architecture, database/ERD or API design model as a separate JSON file under
  `assets/`. At the relevant location, `SKILL.md` uses a descriptive relative Markdown
  link to that file; it does not embed the JSON object or a fenced JSON copy. Follow
  [Documents](../../document/SKILL.md#document-package) for the single-source package.
- Use stable, descriptive kebab-case filenames such as `system-architecture.json`,
  `database-erd.json` and `api-design.json`. Keep critical meaning in nearby readable
  text; the linked JSON carries the structured representation.
- Use an available, documented Archify schema; do not invent one or claim rendering
  support without an available renderer.
- Preserve existing diagrams when no supported conversion is available.

- Ground labels and relationships in inspected code, schemas or accepted Specifications.
  Diagrams establish no runtime behavior, authority or completion.
- Keep critical meaning explicit in nearby text and readable without color or geometry.
  Keep labels stable and domain-specific; split mixed models when their reading
  direction becomes unclear.

<a id="erd--data-structure"></a>

## 2. ERD — data structure

- Distinguish conceptual, logical and physical models.
- Use singular domain entity names, explicit cardinality/optionality, meaningful
  relationship labels and keys that clarify identity/joins.
- Include only relevant attributes unless a complete physical schema is required. Never
  infer tables, keys or constraints from naming alone.
- Preserve derivation provenance; schemas, migrations and accepted Specifications remain
  authoritative over the diagram. These semantics do not claim ERD rendering support.

<a id="behavior--game-decisions"></a>

## 3. Behavior — game decisions

- Identify FSM states, events, guards, transitions and boss phases explicitly.
- For Behavior Trees identify Root, Selector, Sequence, Condition, Action and relevant
  Success/Failure/Running semantics. An ordinary flowchart is not automatically a
  Behavior Tree; name boundaries when mixing FSM/BT.
- Use domain states/actions; distinguish conditions from actions and interrupts from
  transitions; show meaningful loops/end states.
- Separate observed, intended and unresolved behavior. Never invent thresholds,
  probabilities, cooldowns, priorities or phase conditions.
- Runtime equivalence needs separate evidence; node editing, simulation, tracing and
  code generation require separate tool decisions.

<a id="sequence--ordered-interaction"></a>

## 4. Sequence — ordered interaction

- Use stable participants and chronological messages; distinguish calls, responses and
  asynchronous signals where relevant.
- Show grounded alternatives, optional exchanges, loops and parallel interactions. Show
  activation only when it clarifies responsibility/lifetime.
- Keep state changes in labels or linked behavior diagrams. Use behavior diagrams for
  one actor's decisions; sequence diagrams for exchanges among actors/systems.
- Never invent timing guarantees, retries, concurrency, ownership or failure handling.

<a id="existing-mermaid-contexts"></a>

## 5. Existing Mermaid contexts

- Preserve existing Mermaid diagrams. For separately authorized Mermaid work outside the
  Document package contract, follow [Libraries](libraries.md#mermaid-integration).
- Use `accTitle`, `accDescr` and readable fallback meaning. Mermaid source types
  include `erDiagram`, `stateDiagram-v2`, `flowchart` and `sequenceDiagram`. Their availability does
  not establish Archify or Document viewer support.
