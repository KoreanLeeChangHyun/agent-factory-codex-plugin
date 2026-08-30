# ERD Diagrams

Use Mermaid `erDiagram` when the primary relationship is between data entities.

- Use singular, stable entity names from accepted domain or schema evidence.
- Show primary and foreign keys when they materially clarify identity or joins.
- Label relationships and express cardinality and optionality explicitly.
- Distinguish conceptual, logical, and physical ERDs; do not present an inferred
  conceptual model as an implemented database schema.
- Include only the attributes needed for the diagram's purpose unless a complete
  physical schema is explicitly required.
- Do not invent tables, keys, constraints, or relationships from naming alone.
- Add `accTitle` and `accDescr` summarizing the entities and important
  cardinalities.

Keep migrations, schema files, or accepted Specifications authoritative over
the rendered diagram. Record provenance when the ERD is derived from code or a
database.

## Official syntax reference

- [Mermaid entity relationship diagrams](https://mermaid.js.org/syntax/entityRelationshipDiagram)
