# Processed research: visual taxonomy for refined Specifications

Date of research: 2026-08-28  
Information stage: **processed information**  
Authority: Explorer evidence, not an accepted Specification, Project Skill, implementation decision, or completion claim

## Investigated question and boundary

This exploration asks which conventional visual grammar should be selected when
authoring Agent Factory refined Specifications. “Visual-first” is interpreted as
**answer-first**: choose the smallest conventional visual form whose semantics
directly answer the Human's question. It does not mean adding charts to every
section, replacing prose with pictures, or making a rendering library the source
of project truth.

The report consolidates the earlier read-only processed report at
`.agent-factory/inquery/specification-visualization-libraries-20260828/report.md`
and adds a usable taxonomy and routing policy. Existing legacy Inquery data was
not modified. No renderer, browser, validator, build, test, or prototype was run;
the findings are based on repository inspection and primary documentation.

This Explorer output can inform a later Human decision. It cannot accept the
policy as refined project knowledge or edit either member of a paired
Specification/Project Skill.

## Consolidated conclusion

Retain the earlier **static-first progressive-disclosure** conclusion and add a
question-led visual taxonomy:

1. Begin with the semantic question, not a favored library.
2. Use native HTML, CSS, and curated SVG for compact bespoke explanations and
   use native tables for exact row/column relationships.
3. Use Mermaid as the ordinary text source for the conventional families it
   actually supports well: flow/workflow, sequence, state, class, ER, journey,
   Gantt, timeline, requirement, and small graphs. Render pinned Mermaid to a
   checked-in static SVG; do not require Mermaid in the browser.
4. Do not treat Mermaid flowcharts as standards-compliant UML activity, DFD, or
   BPMN merely because similar boxes and arrows can be drawn.
5. Add a specialist only when the semantics require it: PlantUML for fuller UML
   and text-authored wireframes; C4-PlantUML or another C4-aware tool for stable
   C4 views; bpmn-js for real BPMN; Graphviz for dense dependency/DAG layouts;
   Vega-Lite/Vega for quantitative evidence and Sankey; Cytoscape.js for genuine
   interactive networks.
6. Published/browser dependencies remain **zero by default**. Every generated or
   interactive visual needs a nearby semantic list, table, or prose equivalent.

The taxonomy is intentionally not a popularity ranking. UML and BPMN are
standards-backed, C4 is an established domain model with official guidance, and
the remaining families are admitted where official tooling or established
domain practice makes their use defensible. Where frequency could not be
established from primary evidence, this report makes no frequency claim.

## Evidence basis: families are semantic, not interchangeable

UML 2.5.1 organizes modeling concepts into structure, behavior, interaction,
use-case, deployment, and information-flow areas, and its diagram annex treats
diagrams as views of model elements rather than arbitrary pictures
([OMG UML 2.5.1](https://www.omg.org/spec/UML/)). OMG's own overview groups the
standard diagram types into structure, behavior, and interaction families and
lists class, object, component, package, deployment, use-case, activity, state
machine, sequence, communication, timing, and interaction-overview forms
([OMG UML overview](https://www.omg.org/uml/what-is-uml.htm)). This supports
grouping the long UML catalog by the question answered rather than exposing all
diagram names as equal defaults.

The C4 model similarly uses levels of zoom—system context, container, component,
and code—and adds landscape, dynamic, and deployment diagrams. Its own guidance
says teams need only the views that add value and that context plus container
are sufficient for many teams
([C4 diagrams](https://c4model.com/diagrams)). This is evidence for progressive
disclosure, not evidence that every Specification needs four architecture
diagrams.

BPMN is different from a generic workflow. OMG defines BPMN as graphical
notation for specifying business processes in a Business Process Diagram, with
precision sufficient for translation into software process components
([OMG BPMN overview](https://www.omg.org/bpmn/),
[BPMN 2.0.2 specification](https://www.omg.org/spec/BPMN/)). Therefore a simple
flowchart is appropriate for explanatory workflow, while a process whose pools,
events, gateways, messages, and executable interchange semantics matter should
use BPMN.

For decisions, DMN 1.4 formally includes decision tables; a decision table
arranges rule inputs and outputs in cells, while a decision requirements graph
shows dependency among decisions and input data
([OMG DMN 1.4](https://www.omg.org/spec/DMN/1.4/PDF)). A free-form decision tree
is useful for a small branch path, but it is not a substitute for a complete
rule table when combinations and coverage matter.

Requirements traceability is primarily relational, so a matrix is normally the
more honest baseline. NASA guidance describes bidirectional traceability and
records links among higher-level requirements, design, code, tests, validation
methods, and results in a requirements traceability matrix
([NASA software requirements validation guidance](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695440/SWE-055%2B-%2BRequirements%2BValidation),
[NASA Systems Engineering Handbook appendix](https://www.nasa.gov/reference/system-engineering-handbook-appendix/)).

## Small default visual taxonomy: route by the Human's question

These are the small default families. The labels are families, not mandatory
artifacts.

| Human question | Default family | What it makes explicit | Do not substitute |
| --- | --- | --- | --- |
| **What is in scope, who owns it, and how is it arranged?** | Context / architecture / hierarchy | Boundary, responsibility, containment, dependency | A sequence diagram, which answers order rather than scope |
| **What can the system or actor do?** | Capability / use-case map | Actor-to-goal or capability relationships | A screen list that accidentally implies requirements coverage |
| **How does behavior change or proceed?** | State machine for event-driven modes; activity/workflow for work progression | States and transitions, or actions and control/data flow | A flowchart that conflates persistent state with steps |
| **Who interacts, in what order?** | Sequence / interaction diagram | Ordered messages, participants, alternatives | An architecture map with numbered arrows |
| **What is the structure of concepts, software, or stored data?** | Class/concept model or ERD/schema | Types/entities, properties, relationships, cardinality | A mind map, which does not carry schema constraints |
| **Where does information move or transform?** | Data-flow / lineage view; Sankey only when magnitude is central | Sources, sinks, transformations, custody; optionally quantity | An ERD, which describes stored structure rather than movement |
| **What differs, is covered, or drives a decision?** | Semantic table/matrix; quantitative chart only for numerical pattern | Exact comparison, mapping, coverage, evidence, distribution | Decorative bars that duplicate a short table |
| **What happens when?** | Timeline for events; Gantt for scheduled work and dependencies; roadmap lanes for intent | Chronology, duration, milestones, dependency, confidence | A Gantt chart for unscheduled aspirations |
| **What does the Human experience or navigate?** | User journey, screen flow, or wireframe | Steps, actors, touchpoints, screens, transitions, interface hierarchy | A polished mockup when only navigation or requirements are known |

### Fast discriminator for easily confused families

- **State vs activity:** state asks “what mode is the subject in after an
  event?” Activity asks “what work/control/data proceeds next?” Game and
  interactive behavior often needs both: a state machine for modes and an
  activity or sequence view for one scenario.
- **Sequence vs data flow:** sequence orders interactions in time. DFD/lineage
  follows information through stores and transformations even when exact call
  order is irrelevant.
- **Architecture vs deployment:** architecture identifies responsibilities and
  relationships; deployment maps runtime instances to infrastructure in a
  specific environment. C4 describes deployment nodes and deployed system or
  container instances explicitly
  ([C4 deployment](https://c4model.com/diagrams/deployment)).
- **ERD vs class diagram:** ERD is preferred for persisted entities,
  relationships, and cardinality; class diagrams are preferred for software or
  domain types, attributes, operations, inheritance, and associations.
- **Mind map vs concept map vs knowledge graph:** a mind map is a radial
  hierarchy for ideation; a concept map uses labeled propositions among concepts
  to express understanding; a knowledge graph is an explicit graph data model.
  IHMC describes concept maps as tools for organizing and representing knowledge
  and supports them with CmapTools
  ([IHMC Cmap](https://cmap.ihmc.us/)). RDF, by contrast, defines graphs as sets
  of subject-predicate-object triples that can be visualized as labeled directed
  arcs ([W3C RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/)).
- **Timeline vs Gantt vs roadmap:** a timeline reports chronology; Gantt encodes
  tasks against time and can encode dependencies; a roadmap communicates
  directional intent, horizons, themes, and uncertainty. A roadmap should not
  gain false precision by being rendered as a schedule.

## Optional domain-specific extensions

### Software and systems

Use the small core plus bounded UML or C4 views:

- **Use-case:** actor/goals and externally visible capability. Use PlantUML when
  conventional UML notation matters; use a small native capability map when it
  does not.
- **Class and object:** class for types and relationships; object for one
  illustrative runtime snapshot. Object diagrams are examples, not architecture
  inventories.
- **Component and package:** component for replaceable/responsible software
  units and interfaces; package for namespace/model organization and dependency.
  Group them under “static software structure” rather than making both default.
- **Deployment:** runtime instances, nodes, networks, and environment. Keep
  environment identity explicit.
- **C4:** context for system boundary and people/external systems; container for
  deployable/runnable units and data stores; component only where an internal
  container needs explanation; code view only when it adds information beyond
  the paired Skill/code. The C4 site's official catalog is the authority for
  the view meanings ([C4 diagrams](https://c4model.com/diagrams)).
- **Dependency/DAG:** Graphviz `dot` is an established static specialist for
  layered directed graphs and attempts to reduce crossings and edge length
  ([Graphviz dot](https://graphviz.org/docs/layouts/dot/)). Preserve the actual
  nodes and edges in a table/list.

### Games and interactive systems

- Use **state machines** for game modes, entity lifecycle, AI modes, animation
  states, or UI modes.
- Use **activity/workflow** for a gameplay loop or quest procedure where the
  steps rather than persistent modes are central.
- Use **sequence** for one multiplayer/network/service interaction scenario.
- Use a **decision tree/table** for bounded branching logic; use a table when
  combinations, priority, or rule completeness matter.
- Use a **map/spatial view** only when location or traversal is itself refined
  knowledge. This is a domain-specific extension, normally native SVG rather
  than a universal diagram grammar.

### Data

- **ERD/schema:** persisted data structure and cardinality.
- **DFD:** logical movement among external actors, processes, stores, and flows.
  Neither Mermaid nor PlantUML documents a dedicated standards-aware DFD parser;
  both can draw a constrained approximation. If DFD notation carries formal
  meaning, use a DFD-capable specialist and retain an adjacent flow inventory.
- **Data lineage:** datasets plus producing/consuming jobs and transformations.
  OpenLineage explicitly models Jobs and Datasets and says a lineage graph can
  be woven from their input/output observations
  ([OpenLineage object model](https://openlineage.io/docs/next/spec/object-model/)).
  Use Graphviz for static lineage and Cytoscape.js only for interactive tracing.
- **Sankey:** use only when edge width truthfully encodes conserved or comparable
  quantity across flows. Mermaid documents a dedicated but experimental Sankey
  syntax ([Mermaid Sankey](https://mermaid.js.org/syntax/sankey.html)); Vega is
  preferred when data validation, quantitative encoding, and publication control
  matter.
- **Knowledge graph:** use a labeled node-edge view for selected relationships,
  never an unreadable dump of the whole graph. Pair it with a triple/edge table.

### Process and operations

- Use a **plain workflow/activity** for a comprehensible explanatory process.
- Escalate to **BPMN** only when standardized process semantics—events, gateways,
  pools/lanes, message flows, transactions, or exchange—are required. bpmn-js is
  an official open BPMN 2.0 rendering/modeling toolkit whose metamodel supports
  valid BPMN document import/export
  ([bpmn-js walkthrough](https://bpmn.io/toolkit/bpmn-js/walkthrough/)).
- Use **swimlanes** only when responsibility/handoff is part of the question;
  otherwise lanes add width without meaning.
- Use **decision tables** beside the process when branching is rule-driven and
  a gateway label would hide the rules.

### Planning

- **Timeline:** dated/ordered events and milestones. Mermaid's dedicated timeline
  syntax is currently documented as experimental
  ([Mermaid timeline](https://mermaid.js.org/syntax/timeline.html)).
- **Gantt:** scheduled tasks, spans, and dependencies. Mermaid natively renders
  Gantt and documents tasks against a time axis
  ([Mermaid Gantt](https://mermaid.js.org/syntax/gantt.html)).
- **Roadmap:** themes/outcomes by horizon, with confidence or commitment encoded
  explicitly. Prefer semantic HTML lanes or native SVG; do not use a Gantt unless
  dates and task dependencies are accepted refined facts.
- **Dependency graph:** use Mermaid for a small plan and Graphviz for a dense DAG.
  Do not imply priority from layout unless priority is encoded and accepted.

### UX

- **User journey:** actors, task steps, touchpoints, experience/evidence; Mermaid
  has dedicated journey syntax with sections, tasks, actors, and scores
  ([Mermaid user journey](https://mermaid.js.org/syntax/userJourney)). Scores are
  data claims and require provenance, not aesthetic invention.
- **Screen flow:** screen/page states and navigation transitions. Use a flowchart
  with stable screen IDs and a companion transition table. Embedded thumbnails
  are optional and must not be the only readable labels.
- **Wireframe:** layout, controls, hierarchy, and states without pretending the
  visual design is final. PlantUML Salt explicitly targets graphical-interface
  wireframes/page schematics
  ([PlantUML Salt](https://plantuml.com/en/salt)); native HTML/CSS/SVG is often a
  clearer static publication baseline.
- Keep journey, screen flow, and wireframe separate: experience, navigation, and
  interface composition answer different questions.

### Quantitative evidence

- Use **bars/dots** for magnitude comparison, **lines** for change over an
  ordered continuum, **scatterplots** for association, **histograms/density/box
  plots** for distributions, and **small multiples** for comparable groups.
- Prefer a semantic table when exact lookup, requirements, status, or category
  membership is the question. Add a chart only when shape, trend, distribution,
  or outlier becomes materially easier to see.
- Vega-Lite's official gallery includes bars, histograms, scatterplots, lines,
  areas, table-based plots, error bands, box plots, faceting, and interactive
  multiviews ([Vega-Lite examples](https://vega.github.io/vega-lite/examples/)).
  Vega can render static SVG server-side and provides a `vg2svg` CLI
  ([Vega usage](https://vega.github.io/vega/usage/)). This preserves the earlier
  conclusion that Vega-Lite/Vega is the first optional quantitative source.
- Never use a pie/donut, gauge, 3-D effect, dual axis, or color gradient merely
  because a tool supports it. The encoding must match the analytical question,
  and the underlying data plus written conclusion must remain available.

## Routing matrix

“Mermaid native” below means a dedicated documented Mermaid syntax, not formal
conformance to UML, BPMN, SysML, or another standard. “Approximation” means the
tool can draw similar shapes/edges but does not preserve the full notation's
semantics. Every row assumes checked-in static output; the fallback is required,
not optional.

| Information type | Semantic question | Preferred visual form | Source / rendering tool | Required fallback |
| --- | --- | --- | --- | --- |
| Scope, actors, external systems | What is inside/outside and who depends on it? | Context diagram | Native HTML/SVG for small maps; C4 context via pinned C4-PlantUML; Mermaid C4 is dedicated but experimental | Boundary/responsibility list with relationship table |
| Overall software system | What are the major responsibilities and connections? | C4 container or curated architecture diagram | C4-PlantUML; native SVG; Mermaid `architecture-beta` or flowchart only when its reduced grammar suffices | Component/responsibility/relationship table |
| Actor goals/capabilities | Who needs what behavior? | UML use-case or capability map | PlantUML use-case; Mermaid flowchart is only an approximation | Actor -> goal table with exclusions |
| Domain/software types | What types, properties, operations, and associations exist? | UML class diagram | Mermaid class native; PlantUML class native | Class/type definitions and association table |
| Runtime example | What objects/instances and links exist in this example? | UML object diagram | PlantUML object native; Mermaid class/flowchart approximation | Instance/property/link table; label as example |
| Software units/interfaces | Which units provide/require interfaces? | UML component diagram | PlantUML component native; Mermaid block/flowchart approximation | Component/interface/responsibility table |
| Namespace/model organization | How are elements grouped and which packages depend? | UML package diagram | PlantUML package constructs; Mermaid subgraphs approximation; Graphviz for dense package DAG | Package membership and dependency table |
| Runtime infrastructure | Where do instances run in this environment? | C4 or UML deployment | PlantUML deployment/C4 deployment; Mermaid C4 deployment experimental; Mermaid architecture approximation | Environment/node/instance/network table |
| Feature/service scenario | Who sends what, and in what order? | Sequence diagram | Mermaid sequence native; PlantUML sequence native | Ordered numbered event list including branches/errors |
| Event-driven behavior | Which state follows which event/guard/action? | State-machine diagram | Mermaid state native; PlantUML state native | State-transition table with initial/final/error states |
| General workflow | What work/control proceeds next? | Activity/workflow, optionally swimlanes | Mermaid flowchart/swimlanes for explanatory flow; PlantUML activity for UML semantics | Ordered steps, decision conditions, and owners |
| Business process semantics | How do events, gateways, participants, and messages compose? | BPMN process/collaboration | bpmn-js / BPMN XML specialist; Mermaid and PlantUML are approximations, not default | Process step/event/gateway/message table plus BPMN source |
| Stored relational data | What entities, keys, attributes, and cardinalities exist? | ERD | Mermaid ER native; PlantUML IE/ER; database-schema specialist when executable fidelity matters | Schema/data dictionary with keys and constraints |
| Logical data movement | Where does data enter, transform, persist, and exit? | DFD | Native SVG or constrained Mermaid/PlantUML/Graphviz approximation; specialist if formal DFD notation matters | Flow inventory: source, transform, store, sink, classification |
| Data provenance/impact | Which jobs produce or consume which datasets? | Data-lineage graph | Graphviz static; Cytoscape.js interactive; OpenLineage-shaped data when applicable | Dataset/job/edge table with direction and provenance |
| Quantified flow | Where does a comparable amount move? | Sankey | Vega/Vega-Lite specialist; Mermaid Sankey dedicated but experimental | Source-target-value table and conservation/normalization note |
| Requirements relationships | What derives, satisfies, verifies, or traces what? | Requirement graph for overview | Mermaid requirement native (SysML-inspired); PlantUML/SysML-capable tooling where rigor is required | Requirements traceability matrix is authoritative fallback |
| Requirements/test coverage | Is every relationship covered and inspectable? | Traceability matrix | Native HTML `<table>`; optional heatmap as redundant encoding | The same accessible table with IDs, headers, and explicit gaps |
| Small branching choice | What outcome follows each answer? | Decision tree | Mermaid/Graphviz flow; native SVG | Ordered rules and outcomes |
| Complete rule logic | Which input combinations yield which outputs? | DMN-style decision table | Native HTML table; DMN specialist if executable/interchange semantics matter | Accessible table plus priority/hit policy and uncovered cases |
| Ideation hierarchy | What ideas branch from a central theme? | Mind map | Mermaid mindmap dedicated but experimental; PlantUML mindmap | Nested semantic list |
| Conceptual understanding | Which concepts form labeled propositions? | Concept map | CmapTools or native SVG; Graphviz for static layout | Concept-relation-concept proposition table |
| Formal semantic relationships | Which subject-predicate-object facts form a graph? | Knowledge-graph view | Graphviz static; Cytoscape.js interactive; native SVG for a curated subset | Triple/edge table and selection/filter statement |
| Chronology | What occurred or is expected in order? | Timeline | Mermaid timeline dedicated but experimental; native HTML/SVG | Ordered dated list, with unknown/approximate dates marked |
| Accepted schedule | When do tasks start/end and depend on one another? | Gantt | Mermaid Gantt native; PlantUML Gantt; Vega-Lite ranged bars for evidence-heavy schedules | Task table with dates, dependency, owner/status epistemic labels |
| Directional plan | Which outcomes/themes belong to which horizon? | Roadmap lanes | Native semantic HTML/SVG; Mermaid timeline/Gantt only if their semantics truthfully fit | Theme/outcome/horizon table with confidence/commitment status |
| Plan/module dependency | What must precede or depend on what? | Dependency DAG | Mermaid flowchart small; Graphviz `dot` dense | Dependency edge table and cycle list |
| User experience | What steps/touchpoints does an actor experience? | User journey | Mermaid journey native; native HTML/SVG | Step/actor/evidence/pain-point table; provenance for scores |
| Navigation | Which screen can transition to which? | Screen-flow diagram | Mermaid/Graphviz flow with screen IDs; native SVG/HTML | Screen-transition-condition table |
| Interface composition | What controls/content/states occupy a screen? | Wireframe | PlantUML Salt; native HTML/CSS/SVG; a design tool only if its exported artifact/source is locally governed | Screen inventory with control, state, behavior, accessibility notes |
| Numeric comparison/trend/distribution | What magnitude, change, association, or distribution is evidenced? | Bars/dots, line, scatter, histogram/box plot, small multiples | Vega-Lite/Vega -> static SVG; native SVG for tiny stable cases | Source data table, units, method, sample/uncertainty, written conclusion |
| Exact comparison/responsibility/status | Which row-column relationships are true? | Semantic table/matrix | Native HTML only; optional redundant glyph/heatmap | The accessible table itself; never a canvas-only grid |

## Mermaid, PlantUML, and specialist boundary

### Mermaid: default only where the dedicated grammar fits

Mermaid's official syntax catalog documents dedicated flowchart, swimlane,
sequence, class, state, ER, user-journey, Gantt, requirement, mind-map,
timeline, Sankey, C4, block, architecture, and quantitative chart types
([Mermaid syntax reference](https://mermaid.js.org/intro/syntax-reference.html)).
Dedicated syntax improves diffability and AI readability, but it is not proof of
standards conformance. In particular:

- use-case, object, UML component/package/deployment, DFD, BPMN, concept map,
  knowledge graph, wireframe, screen flow, roadmap, decision tree/table, and
  traceability matrix have no dedicated, stable standards-aware Mermaid grammar;
  they require a constrained flow/block/table approximation or a specialist;
- Mermaid C4 supports context, container, component, dynamic, and deployment
  forms but is explicitly experimental and documents unfinished features and
  layout limits ([Mermaid C4](https://mermaid.js.org/syntax/c4.html));
- mind map, timeline, and Sankey are also documented as experimental, so checked-
  in static artifacts and pinned versions are especially important;
- Mermaid requirement diagrams follow SysML-style requirement relations and can
  show `contains`, `derives`, `satisfies`, `verifies`, `refines`, and `traces`
  ([Mermaid requirement diagram](https://mermaid.js.org/syntax/requirementDiagram)),
  but an accessible traceability matrix remains the reliable coverage view.

### PlantUML assessment under the same publication constraints

PlantUML materially broadens text-authored coverage. Its official catalog lists
sequence, use-case, class, object, activity, component, deployment, state, and
timing UML diagrams, plus wireframe/Salt, Gantt, chronology, mind map, WBS,
network, ArchiMate, and Information Engineering forms
([PlantUML diagram catalog](https://plantuml.com/)). Its official standard
library includes C4-PlantUML, so a pinned local C4 include can work without a
network fetch
([PlantUML standard library](https://github.com/plantuml/plantuml-stdlib)).

That breadth does **not** make PlantUML a universal default:

- **Local/offline static SVG:** supported. The CLI runs locally and can emit SVG
  from files or stdin (`--svg`, `--format svg`)
  ([PlantUML command line](https://plantuml.com/command-line)). The official
  quick start recommends Java 11 or later for the JAR
  ([PlantUML quick start](https://plantuml.com/en/starting)). Some automatically
  laid-out diagrams bring Graphviz/layout dependencies or bundled equivalents,
  so the authoring surface is heavier than native HTML/SVG and different from
  Mermaid's Node/CLI stack.
- **Coverage:** strong for fuller UML and useful for Salt wireframes, Gantt,
  mind maps, ER/IE, and C4 through the standard library. DFD can be drawn but has
  no documented dedicated DFD semantics. BPMN-like diagrams can be approximated,
  but real BPMN should use BPMN XML and a BPMN-aware renderer. A broad catalog is
  not a reason to force unlike questions into one syntax.
- **Accessibility:** text source is inspectable, but no official evidence was
  found that generic PlantUML SVG output supplies a complete semantic reading
  order or diagram-specific accessible alternative. Treat the SVG as visual
  output: add a curated accessible name/description and an adjacent list/table.
  Do not expose dense element-by-element SVG narration as the only alternative.
- **Security:** PlantUML can preprocess includes and access resources. Its
  official security documentation states that `UNSECURE` and current `LEGACY`
  profiles can access local files and URLs, while `ALLOWLIST` blocks both except
  explicit allowlists and `SANDBOX` blocks both even when allowlists exist
  ([PlantUML security](https://plantuml.com/security)). Agent Factory authoring
  should use a pinned local distribution in a disposable network-disabled
  process, `SANDBOX` for self-contained inputs (or the narrowest allowlist when
  reviewed local includes are indispensable), input/output/time/memory limits,
  and SVG sanitization. Never use remote `!include` during deterministic
  publication.
- **License:** the official repository says the default distribution is
  GPL-3.0-or-later but the same source is available in several alternative
  flavors including Apache-2.0, BSD-3-Clause, and MIT; generated images belong
  to the source author and are not covered by the GPL
  ([PlantUML licensing](https://github.com/plantuml/plantuml/blob/master/LICENSES.md)).
  A later implementation must deliberately select, pin, and record the chosen
  distribution and transitive components rather than citing “PlantUML” alone.
- **Toolchain cost:** a pinned JAR/runtime plus possible layout engine, themes,
  standard-library includes, fonts, and sanitization is additional authoring
  infrastructure. It is justified when its fuller UML or Salt/C4 grammar avoids
  misleading approximations, not merely to replace Mermaid.

PlantUML is therefore a **bounded static specialist**, especially for UML forms
Mermaid lacks. Mermaid remains the smaller ordinary text source where its native
grammar is sufficient. Neither belongs in the default browser runtime.

### Other specialists

- **BPMN:** bpmn-js is BPMN-aware and based on the BPMN metamodel, but is a
  browser toolkit and therefore adds a substantial authoring/runtime surface.
  Author/export BPMN XML and static SVG outside the published Planning page;
  check in the static artifact and semantic process table. Its license requires
  the bpmn.io watermark to remain visible when the software is used in a site or
  application ([bpmn-js license](https://github.com/bpmn-io/bpmn-js/blob/develop/LICENSE)).
- **Graphviz:** use DOT for dense static directed graphs. It reads text and emits
  SVG, but its generated SVG still needs semantic fallback and sanitization.
  The earlier report's 2026 Graphviz EPL-2.0 distribution concern remains; a
  later implementation needs license review.
- **Vega-Lite/Vega:** first quantitative specialist and a better controlled
  Sankey route than an experimental general diagram syntax. Keep the JSON spec,
  data, checked-in SVG, and data table.
- **Cytoscape.js:** only for complex network exploration where selection,
  traversal, filtering, or graph analysis materially improves understanding.
  Preserve a separately authored static overview and edge table because the
  published Specification must remain complete without JavaScript.
- **Native HTML/SVG:** remains the best source/rendering route for compact
  bespoke lifecycle, roadmap, screen-flow, matrices, and curated architecture
  maps when library grammar would obscure meaning.

## Selection rules: prevent decorative, redundant, and misleading visuals

Apply these rules in order:

1. **State the semantic question in one sentence.** If the intended visual does
   not answer it, do not create the visual.
2. **Choose the information relationship before the notation:** boundary,
   hierarchy, chronology, ordered interaction, state transition, process flow,
   schema/cardinality, quantified flow, comparison, distribution, navigation,
   or spatial composition.
3. **Use the most conventional adequate grammar.** Standards-aware semantics
   win when they matter; otherwise use the simpler explanatory family.
4. **One visual, one main claim.** Split views when a diagram simultaneously
   attempts structure, sequence, state, schedule, and status.
5. **Do not duplicate prose without improving inference.** A diagram must reveal
   a relationship, pattern, boundary, path, or exception faster or more reliably
   than the adjacent text. Decorative icon grids and chart-shaped lists fail.
6. **Do not invent precision.** No dates, quantities, rankings, journey scores,
   confidence, priority, status, topology, or causal direction may be inferred
   from layout or decoration. Mark unknown, approximate, proposed, observed,
   accepted, and unresolved information distinctly.
7. **Do not mix epistemic categories silently.** Accepted decisions, observed
   implementation evidence, hypotheses, and unresolved questions need explicit
   visual keys or separate views.
8. **Prefer a table when lookup or coverage is the task.** Requirements,
   responsibilities, permissions, status, comparisons, and decision rules are
   usually tables first. A heatmap/glyph may supplement, never replace, values.
9. **Escalate by demonstrated need:** semantic HTML/SVG -> Mermaid or PlantUML
   static source -> standards/domain specialist -> interactive runtime. Record
   why the prior tier failed.
10. **Cap density and provide progressive disclosure.** Start with a context or
    summary view; link to detailed views. Do not shrink text or hide essential
    labels to fit a catalog-sized graph.
11. **Provide semantic recovery.** Every figure needs stable ID, title, concise
    takeaway, provenance, and an adjacent prose/list/table sufficient to recover
    all essential facts without color, hover, JavaScript, or the image.
12. **Preserve direction, units, cardinality, legend, and scope.** Unlabeled
    arrows, ambiguous arrow direction, missing units, absent time zone, or a
    legend that changes by figure are defects, not style choices.
13. **Use motion and interaction only when they answer a question.** No essential
    information may exist only in hover, animation, filter state, zoom, or drag.
14. **Stop when prose is clearer.** Visual-first explicitly permits no diagram.

## Implications for the Specification authoring contract

The earlier proposal remains sound and should be extended with taxonomy routing.
These are recommendations for Human acceptance, not current project rules.

### 1. Add a required question-and-family declaration

For each meaningful visual, record:

- stable `visual-*` ID;
- information type and one-sentence semantic question;
- selected visual family and why a simpler form was insufficient;
- scope/audience and epistemic categories shown;
- AI-readable source, checked-in Human artifact, renderer/version/configuration;
- provenance/source data and units where applicable;
- fallback list/table/prose and paired Project Skill section;
- known omissions, filters, aggregation, uncertainty, and unresolved decisions.

The mapping is a synchronization aid, not a third authority.

### 2. Keep one semantic body and two faithful projections

The accepted Agent Factory model requires a Human-facing browser projection and
an English AI-facing Project Skill to contain the same decisions,
relationships, observations, and unresolved questions. The Human projection may
use richer visual grammar, Korean labels, layout, color, and interaction. The
Project Skill should preserve the visual's semantics through Mermaid/DOT/other
textual sources where useful and through explicit relational prose/tables.

Alignment is semantic, not pixel-identical. Compare:

- node/entity/state/task/screen identity;
- edges, direction, order, guards, cardinality, units, and quantities;
- boundaries, containment, environment, and time basis;
- accepted/observed/hypothetical/unresolved status;
- filters, exclusions, aggregation, and uncertainty;
- the figure takeaway and the Skill's English conclusion.

Generated SVG is not the sole Human truth; diagram source is not the sole AI
truth. Both project from the same refined body and can drift, so stable IDs and
alignment review remain necessary.

### 3. Preserve the static publication contract

- Publish checked-in semantic HTML/static SVG with local relative assets and no
  required visualization runtime.
- Keep native `<table>` semantics for matrices; keep actual SVG icons for
  controls and user-facing icons.
- Pin renderers, transitive dependencies, fonts, locale, ordering, dimensions,
  theme, and configuration. Render in an explicit later authoring step only.
- Sanitize generated SVG and disallow remote fonts, scripts, data, includes, or
  images. Optional JavaScript may enhance, never supply, refined meaning.
- Maintain an accessible figure title/takeaway and semantic equivalent. Generated
  ARIA attributes are helpful evidence, never acceptance by themselves.

### 4. Add routing guardrails to Project Skill instructions

If accepted later, the paired English Project Skill should tell an Agent to:

- identify the semantic question before proposing a diagram;
- route through the matrix rather than defaulting to Mermaid;
- distinguish native grammar, approximation, and specialist notation;
- never infer Human-owned direction, priority, date, risk, approval, or status;
- update Human and AI projections together when visual semantics change;
- preserve provenance and information-stage/epistemic labels;
- decline a visual when it would be decorative, redundant, too dense, or less
  accurate than prose/table.

The Korean Human-facing authoring guidance should express the same rules in a
more visual, task-oriented way; it must not privately introduce a different
default tool or acceptance threshold.

## Retained library and publication conclusions from the prior report

The following earlier findings remain incorporated:

- **Zero visualization runtime is the default.** Static SVG/HTML is the baseline.
- **Native HTML/CSS/SVG is Tier 0.** It is preferred for small flows, curated
  architecture maps, cards, matrices, and icons.
- **Mermaid and Vega-Lite are bounded declarative Tier 1 sources**, rendered at
  authoring/build time to checked-in SVG.
- **Graphviz, Observable Plot, and D3 are Tier 2 specialists**: Graphviz for dense
  static graph layout, Plot for a justified code-authored chart, D3 only for a
  bespoke visual grammar.
- **Cytoscape.js and ECharts are Tier 3 interactive specialists**, each requiring
  a complete static/semantic baseline and custom accessibility behavior.
- **Tables remain native HTML.** A matrix does not become a chart merely because
  cells have color.
- **Security and licensing remain explicit publication concerns.** Renderer
  inputs are code-adjacent; run authoring in containment, sanitize SVG, and keep
  third-party/version/license records.
- The current `agent-factory-core` paired projections already resemble Tier 0/1:
  semantic Human HTML/inline SVG plus AI-readable Mermaid definitions. A later
  migration should map stable visual IDs and review semantic alignment, not
  mechanically replace good Human diagrams with runtime Mermaid.

## Contradictions, limitations, and cautions

- **Tool support is not notation conformance.** A flowchart renderer can draw
  circles, diamonds, and arrows without implementing BPMN, UML activity, or DFD
  semantics.
- **The taxonomy is evidence-based but not a popularity ranking.** No comparable
  primary-source usage dataset was found across all diagram families.
- **Experimental grammars can drift.** Mermaid marks C4, mind map, timeline, and
  Sankey as experimental. Pinning and checked-in output reduce but do not remove
  maintenance risk.
- **PlantUML breadth conflicts with a small default stack.** It reduces notation
  gaps but adds Java/layout/security/license choices. This supports selective use,
  not universal installation.
- **BPMN fidelity conflicts with authoring simplicity.** A real BPMN toolchain is
  heavier than Mermaid; use it only when BPMN semantics are refined knowledge.
- **Accessibility remains authored work.** No diagram engine can decide the best
  reading order, takeaway, alternative table, keyboard model, or appropriate
  level of detail for the Human.
- **Static export loses interaction state.** Filters, selections, zoom, and
  animation are not refined facts unless their conclusions are also stated.
- **Multiple projections can drift.** Source, SVG, fallback, Korean document, and
  English Skill increase synchronization surfaces; stable IDs help but do not
  replace review.
- **No experiment was authorized or performed.** No claim is made about actual
  output determinism, accessible trees, installation size, render time, or
  repository compatibility for a selected version.
- **Specialist selection remains contextual.** This report does not select a
  universal BPMN, DFD, design, or roadmap authoring product beyond the evidenced
  candidates and boundaries above.

## Unresolved Human decisions

1. Whether to accept “semantic question first” and the small default taxonomy as
   a project-wide refined authoring policy.
2. Whether Mermaid remains the ordinary diagram source and PlantUML becomes a
   bounded UML/wireframe specialist, or whether the project prefers to support
   only one of those authoring toolchains.
3. Whether real BPMN is permitted in Planning documents and, if so, whether
   BPMN XML plus bpmn-js/static SVG is an acceptable governed source/artifact
   pair.
4. Which experimental Mermaid grammars, if any, may be used before they become
   stable; the conservative alternative is native HTML/SVG or another specialist.
5. Whether renderer mapping should be Markdown or a structured manifest, and
   what later tooling may enforce it.
6. Whether pinned Java and Node authoring environments are both acceptable.
7. Which PlantUML distribution/license flavor and Graphviz distribution terms
   fit planned plugin distribution; legal acceptance remains Human-owned.
8. The minimum Human accessibility and visual-review procedure for generated
   SVG and interactive enhancements.
9. Whether interactive visualizations are permitted at all in Planning
   documents, and the required CSP, vendoring, keyboard, and fallback policy.
10. Who owns acceptance of dates, roadmap commitment, journey scores,
    quantitative methods, and other facts that a visual can make falsely precise.

## Smallest useful next step

The smallest next step is **Human review of the policy, not a renderer test**:
accept, revise, or reject (a) the nine-question default taxonomy, (b) the
Mermaid-default/PlantUML-specialist split, and (c) the rule that standards-aware
BPMN requires a BPMN specialist.

If those decisions are accepted, a later separately authorized Work request can
update the Specification authoring contract and paired Project Skill together.
Only after that policy exists would a bounded non-canonical prototype be useful:
one Mermaid-native diagram, one PlantUML-only UML diagram, and one native table,
rendered to static SVG/HTML under pinned offline settings and inspected for
semantic alignment, sanitization, no-JS behavior, responsiveness, and
accessibility. That prototype would require explicit experiment authorization.
