# Diagrams

<a id="document-assets"></a>

## 1. Document assets

- Processed and Specification packages use Archify-based diagram JSON under `assets/`,
  referenced by relative path where the diagram belongs in `SKILL.md`. Follow
  [Documents](../../document/SKILL.md#document-package) for the single-source package.
- The Human-facing viewer is intended to expand those references inline as part of one
  document. The viewer, Archify rendering integration and ERD support are follow-up
  implementation work, not capabilities delivered by this contract.
- Do not invent an Archify JSON schema, install external Archify tools or convert
  existing diagrams under this guidance. Resolve the supported format in the separately
  authorized implementation work.
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
