---
name: diagram
description: Use when creating, updating, reviewing, or choosing diagrams, diagram data models, JavaScript diagram renderers, architecture diagrams, class diagrams, sequence diagrams, ERDs, workflow diagrams, state diagrams, deployment diagrams, data-flow diagrams, UI-flow diagrams, or traceability graphs.
---

# Diagram Convention

Use this skill for Agent Factory diagram work.

This skill owns diagram-specific conventions. Critical thinking and yes-man
prevention belong to `agent-rule`; apply that skill when the requested diagram is
misleading, underspecified, or contradicted by evidence.

## Diagram Types

Choose the diagram type from the purpose and audience:

- System architecture: system boundaries, containers, components, external
  systems, and ownership.
- Class diagram: domain types, attributes, methods when relevant, inheritance,
  composition, and associations.
- Sequence diagram: actor/system interactions over time, calls, responses,
  async boundaries, retries, and failures.
- ERD: entities, columns when known, primary keys, foreign keys, cardinality,
  and ownership boundaries.
- Workflow diagram: lifecycle steps, decision points, approval boundaries, and
  rework loops.
- State diagram: states, transitions, guards, terminal states, and invalid
  transitions.
- Deployment diagram: runtime nodes, processes, networks, storage, and
  operational boundaries.
- Data-flow diagram: sources, sinks, transformations, stores, trust or privacy
  boundaries.
- UI-flow diagram: screens, user actions, navigation, modal or error flows.
- Traceability graph: design sections, decisions, Work Units, outputs,
  tests, review evidence, and customer deliverables.

If one diagram would mix unrelated concerns, split it into multiple diagrams.

## Rendering Model

Prefer JavaScript libraries for Human-facing rendered diagrams in Agent Factory
reports and UI surfaces. The source data should remain structured and
versionable; the JavaScript renderer turns that source into the visual view.

Default JavaScript rendering stack:

- Primary interactive diagram stack: React Flow + ELK.js.
- Report visualization stack: Apache ECharts with SVG renderer.
- Graph exploration stack: Cytoscape.js.
- Custom sequence or timeline stack: D3.js or a focused custom SVG renderer.

Use React Flow + ELK.js by default for editable or inspectable node-edge
diagrams, including:

- System architecture diagrams.
- Class diagrams.
- ERDs.
- Workflow diagrams.
- State diagrams.
- Deployment diagrams.
- UI-flow diagrams.

Use Apache ECharts with SVG renderer for read-only Design Report and dashboard
visualizations where the diagram behaves more like a chart, timeline, summary
graph, or report visual.

Use Cytoscape.js for graph exploration, dependency graphs, traceability graphs,
and larger interactive networks where graph traversal, filtering, selection,
or layout exploration matters.

Use D3.js or a focused custom SVG renderer for sequence diagrams and other
timeline-like diagrams where the layout is not a generic node-edge graph and
message ordering, lifelines, time, or custom annotation placement matters.

Use Mermaid only for updating existing Mermaid artifacts, preserving historical
output, or when the Human explicitly asks for Mermaid.

Do not use GoJS as the default Agent Factory diagram library because the
official license model is commercial and not open-source.

Do not make a JavaScript rendering library the hidden source of truth. Keep the
diagram model as JSON, DSL text, or another inspectable source artifact.

## Library Selection

Use this default mapping unless repository evidence or an explicit Human
decision overrides it:

| Diagram need | Default renderer |
| --- | --- |
| Class diagram | React Flow + ELK.js |
| ERD | React Flow + ELK.js |
| System architecture | React Flow + ELK.js |
| Workflow | React Flow + ELK.js |
| State diagram | React Flow + ELK.js |
| Deployment | React Flow + ELK.js |
| UI flow | React Flow + ELK.js |
| Sequence diagram | D3.js or custom SVG |
| Traceability graph | Cytoscape.js |
| Dependency graph | Cytoscape.js |
| Report visualization | Apache ECharts SVG renderer |

## Source Model

Use AI-readable and versionable source material.

Allowed source models:

- Structured JSON for Agent Factory-managed diagrams and JavaScript renderers.
- PlantUML for UML-oriented source when a renderer/gateway expects it.
- Graphviz DOT for graph layout source when it is the better interchange model.
- Structurizr DSL for C4 and architecture model views.
- DBML for ERD and database schema diagrams.

draw.io may be used for human-polished customer-facing diagrams when visual
editing is required. Treat draw.io files as optional presentation or editing
artifacts, not as the primary AI-readable source.

## Storage Rules

For Design Documents:

- Store diagram source and diagram artifacts under
  `<project-root>/.agent-factory/specifications/<specification-id>/blocks/diagram/`
  and register each canonical block in the Specification block index.
- Do not create `INDEX.md` files for diagrams.
- Store diagram metadata in Design Document source data or in the diagram
  artifact's own metadata.
- Keep diagrams traceable to related design sections, Work Units, and customer
  deliverables when those relationships exist.

Do not store reusable diagram convention inside project Work Unit packages.
Work Unit packages may reference diagrams as project-specific evidence or
review material.

## Rendering And Export

Diagram rendering and export should use a product-owned rendering gateway or
frontend rendering boundary. The boundary owns renderer adapter details,
preview rendering, SVG/PNG/PDF export, error normalization, timeouts, logs, and
cache policy.

When a renderer/export path is unspecified, record it as unresolved rather than
inventing a toolchain.

## Review Checklist

Before reporting diagram work as complete, verify:

- The diagram type matches the purpose and audience.
- Every node and edge is backed by explicit basis material.
- Important boundaries and ownership are visible.
- The diagram is not overloaded with unrelated concerns.
- The selected source model and JavaScript renderer match the diagram type.
- Missing or uncertain relationships are recorded instead of guessed.
- The source is inspectable and versionable.
- The storage path follows this skill's storage rules.
