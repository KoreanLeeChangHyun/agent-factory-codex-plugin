# Processed research: visualization libraries for refined Specifications

Date of research: 2026-08-28  
Status: Inquiry output, not an accepted Specification or implementation decision

## Investigated question and boundary

This Inquiry asks which visualization libraries and authoring approach can make
Agent Factory's Korean Human-facing refined Specifications visual-first without
changing the accepted `original -> processed -> refined` lifecycle or the paired
Human/AI representation contract. It evaluates diagramming, quantitative charts,
complex networks, tables/matrices, and static versus runtime rendering. It does
not modify or accept a library policy, Skill, Specification, runtime, or build
system.

The key constraint is stronger than “works in a browser”: each Specification
must remain useful without JavaScript, use local relative dependencies, be
responsive and accessible, keep user-facing icons as actual SVG, and remain
semantically aligned with an English Project Skill. Consequently, the primary
recommendation is an authoring and publication policy, not a single universal
library.

## Executive conclusion

Adopt **static-first progressive disclosure**:

1. Use semantic HTML, CSS, and hand-authored SVG for simple flows, cards,
   comparison graphics, matrices, and icons.
2. Use **Mermaid as the default AI-readable source for conventional structural
   diagrams**, but render a pinned version to static SVG at authoring/build time.
3. Use **Vega-Lite as the first optional declarative source for non-trivial
   quantitative charts**, likewise exporting static SVG at authoring/build time.
4. Use **Cytoscape.js** only when a complex network actually needs interactive
   exploration or graph analysis. Publish a static overview and an adjacent
   semantic node/edge summary before enhancing it with JavaScript.
5. Use **Graphviz** as the static specialist for dense DAGs, dependency graphs,
   and large automatic layouts. Use **Apache ECharts** only for interaction-rich,
   high-density charts that exceed Vega-Lite's document-oriented needs.
6. Treat **Observable Plot** as an ergonomic code-authored chart alternative and
   **D3** as an escape hatch for bespoke graphics, not default dependencies.
7. Keep tables as native HTML. A visual matrix is still a table when row/column
   meaning matters; a library is not justified merely for sorting or styling a
   small Specification table.

This gives the smallest default browser stack: **zero visualization runtime**.
Generated SVG/HTML is the baseline; optional scripts may enhance it but may not
be the only carrier of meaning.

## Primary-source evidence and maintenance snapshot

The version numbers below are point-in-time evidence of active publication, not
a request to adopt those exact versions. An implementation decision should pin
and review a version in a lockfile and vendor manifest.

| Candidate | Observed maintenance evidence | License / redistribution note |
| --- | --- | --- |
| Mermaid | The official repository showed Mermaid/Tiny 11.16.0 in June 2026, and Mermaid CLI showed 11.15.0 in May 2026. The CLI accepts `.mmd` and emits SVG through a Node API. [Mermaid repository](https://github.com/mermaid-js/mermaid), [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) | MIT; retain the copyright and permission notice when redistributing the library. [Official license](https://github.com/mermaid-js/mermaid/blob/develop/LICENSE) |
| Vega-Lite | The official changelog records 6.4.3 on 2026-04-24. Vega-Lite is a concise JSON grammar compiled to Vega. [Changelog](https://github.com/vega/vega-lite/blob/main/CHANGELOG.md), [overview](https://vega.github.io/vega-lite/docs/) | BSD-3-Clause, including notice and non-endorsement conditions. [Official license](https://github.com/vega/vega-lite/blob/main/LICENSE) |
| Observable Plot | The official package metadata identifies 0.6.17 and ISC; the latest official release was published 2025-02-14. [Package metadata](https://github.com/observablehq/plot/blob/main/package.json), [releases](https://github.com/observablehq/plot/releases) | ISC. Plot is open source and suitable for redistribution with its notice. [Official repository](https://github.com/observablehq/plot) |
| Apache ECharts | The official repository showed 6.1.0 released 2026-05-19. [Official repository](https://github.com/apache/echarts) | Apache-2.0, with a NOTICE/subcomponent review needed when vendoring; its license lists embedded BSD-3-Clause D3 components. [Official license](https://github.com/apache/echarts/blob/master/LICENSE) |
| Cytoscape.js | The official repository showed 3.33.4 released 2026-05-19 and describes frequent feature and patch releases. [Official repository](https://github.com/cytoscape/cytoscape.js/) | MIT in official package metadata. [Package metadata](https://github.com/cytoscape/cytoscape.js/blob/unstable/package.json) |
| D3 | The official release list shows 7.9.0 (2024-03-12); repository activity continued in 2026. D3 is a low-level web-standards toolkit for SVG, Canvas, and HTML. [Releases](https://github.com/d3/d3/releases), [official repository](https://github.com/d3/d3) | ISC. [Official license](https://github.com/d3/d3/blob/main/LICENSE) |
| Graphviz | The official download page listed stable 15.1.1 in 2026. [Official downloads](https://graphviz.org/download/source/) | Current Graphviz changed to EPL-2.0 on 2026-03-07. Vendoring or distributing Graphviz itself therefore needs an EPL source/notice compliance review; do not assume the older CPL terms. [Official license](https://graphviz.org/license/) |

Exact minified/gzipped weights are deliberately omitted: the official sources
do not present a single comparable measurement across full bundles, tree-shaken
builds, renderers, CLI dependencies, and optional extensions. Qualitatively,
native HTML/SVG has no library burden; Mermaid and Vega/Vega-Lite add authoring
toolchains; Plot depends on D3; ECharts and Cytoscape are substantial runtime
systems; and D3's modular packages can be selected but transfer significant
custom implementation responsibility.

## Decision matrix by visualization class

Legend: **Default** = normal first choice; **Bounded** = allowed after the class
and fallback justify it; **Specialist** = exceptional use with explicit rationale;
**Avoid by default** = technically possible but disproportionate.

| Visualization class | Native HTML / SVG | Mermaid | Vega-Lite | Observable Plot | ECharts | Cytoscape.js | D3 | Graphviz | Recommended decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Small flow / lifecycle | **Default**; strongest semantics and styling control | Bounded/default source when nodes or edges change often | Avoid | Avoid | Avoid | Avoid | Avoid | Specialist only if layout is already hard | Native rendering; Mermaid source when it materially reduces authoring drift |
| Sequence | Possible but laborious | **Default source**; direct text notation | Avoid | Avoid | Avoid | Avoid | Avoid | Poor fit | Mermaid -> static SVG + adjacent ordered event list |
| State machine | Possible for very small models | **Default source** | Avoid | Avoid | Avoid | Bounded only if interactive traversal is the actual requirement | Avoid | Specialist for large state topology | Mermaid for ordinary state diagrams; Graphviz/Cytoscape only at demonstrated scale |
| Architecture / responsibility relationship | **Default** for compact, curated maps | **Default source** for conventional boxes/edges | Avoid | Avoid | Avoid | Bounded for exploratory topology | Specialist for bespoke visual grammar | Specialist for dense dependency layout | Native or Mermaid; preserve a responsibility list/table |
| Simple bars, dots, lines, small multiples | Hand SVG only when truly small/stable | Avoid | **Bounded first choice** | Bounded ergonomic alternative | Avoid by default | Avoid | Avoid by default | Avoid | Native for tiny comparison; Vega-Lite for data-driven charts |
| Complex quantitative / interactive dashboard-like chart | Poor fit | Avoid | Bounded while grammar fits | Bounded for code-authored transforms/marks | **Specialist** for rich interaction and many chart types | Avoid | Specialist | Avoid | Vega-Lite first; ECharts only when its richer runtime interaction is required |
| Complex network / Agent graph | Hand SVG only for a small curated overview | Bounded for small conceptual graph | Avoid | Avoid | Has graph series but not the preferred graph-analysis model | **Specialist/default for genuine interactive network** | Specialist for bespoke force/layout UI | **Specialist/default for static dense DAG/dependency layout** | Static overview + table always; Cytoscape for exploration, Graphviz for static layout |
| Tree / hierarchy | Native nested list plus small SVG | Bounded | Bounded only for quantitative hierarchy | Bounded | Specialist | Bounded for graph navigation | Specialist | Specialist | Semantic nested list/table baseline; select only if visual scale requires it |
| Comparison matrix / responsibility matrix | **Default `<table>`** | Avoid | Heatmap only when magnitude/pattern is the message | Cell/waffle marks when truly graphical | Heatmap only at large scale | Avoid | Specialist | Avoid | Native table with scoped headers; chart may supplement, never replace it |
| Large sortable/filterable tabular dataset | Native table with modest progressive enhancement | Avoid | Avoid | Avoid | Avoid | Avoid | Specialist/custom | Avoid | Out of normal Specification scope; do not add a grid library until a real dataset requires it |

### Why these assignments fit the contract

**Mermaid.** Mermaid's Markdown-like definitions cover flowcharts, sequence,
state, class, entity-relationship, architecture, and other diagram types, which
makes them readable and versionable for AI. Mermaid automatically adds an SVG
`aria-roledescription` and can emit author-supplied accessible title and
description, but those attributes do not substitute for a nearby prose/table
equivalent. [Accessibility options](https://mermaid.js.org/config/accessibility.html)
The CLI provides a practical build-time SVG path, so the Human page need not
load Mermaid. [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli)

**Vega-Lite.** A declarative JSON grammar is deterministic, schema-validatable,
diffable, and easier to align with the Project Skill than imperative drawing
code. Vega can render client- or server-side and `view.toSVG()` returns an SVG
string. [Vega View API](https://vega.github.io/vega/docs/api/view/) Vega-Lite's
`description` encoding creates SVG `aria-label` values, and ARIA generation is
enabled by default for SVG marks and guides. [Description channel](https://vega.github.io/vega-lite/docs/encoding.html),
[ARIA configuration](https://vega.github.io/vega-lite/docs/config.html) A static
SVG plus an adjacent data table is therefore a strong quantitative-publication
path. Interaction-dependent interpretations still require explicit written
conclusions because a static export cannot carry every hover/filter state.

**Observable Plot.** Plot is concise for tabular exploratory graphics and
returns an SVG or semantic HTML `<figure>` depending on options. It supports
top-level and mark-level ARIA labels/descriptions. [Plot output](https://observablehq.com/plot/features/plots),
[Plot accessibility](https://observablehq.com/plot/features/accessibility) It
can be vendored as local UMD + D3, and its official Node example uses JSDOM to
serialize SVG. [Getting started and server rendering](https://observablehq.com/plot/getting-started)
Its JavaScript API is less language-neutral than Vega-Lite JSON and the
project's release cadence is less recent than the other preferred candidates,
so it is an alternative for authors who need Plot's marks/transforms, not a
second default chart grammar.

**Apache ECharts.** ECharts offers broad chart coverage, Canvas or SVG browser
renderers, and a zero-dependency server-side SVG-string renderer. The official
guide prefers SVG SSR when applicable and documents loss of interaction unless
client hydration is added. [Server-side rendering](https://echarts.apache.org/handbook/en/how-to/cross-platform/server/)
ARIA support can generate chart descriptions and color-blindness decals, but
the ARIA component must be imported and `aria.show` enabled; it is not a safe
default assumption. [ECharts accessibility](https://echarts.apache.org/handbook/en/best-practices/aria/)
This makes ECharts useful for a genuinely interaction-rich specialist chart,
but disproportionate for normal Specification figures.

**Cytoscape.js.** Cytoscape is specifically a graph-theory model plus optional
interactive renderer and includes headless graph analysis. It can run from a
locally vendored UMD/ES module without a build system or server. [Official
documentation](https://js.cytoscape.org/), [local inclusion](https://github.com/cytoscape/cytoscape.js/blob/unstable/documentation/md/getting-started.md)
Its core visual export is PNG/JPG and cannot export from a headless instance;
core documentation does not provide a static SVG export equivalent. [Image
export API](https://js.cytoscape.org/index.html) Therefore, its non-JS baseline
must be authored separately (static overview SVG plus semantic graph table),
and keyboard/screen-reader behavior for nodes and edges must be implemented as
an adjacent accessible control/list rather than inferred from the canvas.

**D3.** D3's low-level, web-standards approach provides maximal control and can
target HTML, SVG, or Canvas. [Official repository](https://github.com/d3/d3)
That is exactly why it should be an escape hatch: Agent Factory would own
layout, responsive behavior, keyboard operation, ARIA, static serialization,
and every semantic fallback. Prefer Vega-Lite/Plot for ordinary charts and
Cytoscape/Graphviz for ordinary graphs.

**Graphviz.** DOT is compact and AI-readable, multiple layout engines address
dense graph structure, and `-Tsvg` produces a static vector artifact.
[SVG output](https://graphviz.org/docs/outputs/svg/), [output selection](https://graphviz.org/docs/outputs/)
It is a strong build-time specialist for dependency and Agent DAGs, but its
generated SVG should not be assumed to expose a useful screen-reader reading
order. Always preserve the node/edge facts as prose or a table. DOT also permits
SVG hyperlinks and local image paths, so an untrusted input policy must reject
or allowlist those features. [URL attribute](https://www.graphviz.org/docs/attrs/URL/),
[image attribute](https://graphviz.org/docs/attrs/image/)

**Native HTML tables.** Native `<table>`, `<caption>`, `<thead>`, `<tbody>`, and
scoped row/column headers retain relationships without JavaScript and remain
searchable, selectable, printable, and inspectable. A horizontally scrollable
wrapper can be focusable and labelled, as the existing core Specification
already demonstrates. Heatmaps or glyphs should be redundant encodings inside
cells, never the only carrier of the value.

## Recommended tiered policy

### Tier 0 — semantic native baseline (mandatory)

- Use native HTML for structure, lists, definition lists, tables, captions, and
  conclusions.
- Use hand-authored inline or local SVG for small diagrams and every
  user-facing icon. Visualization packages are not icon libraries; controls
  introduced by an interactive visualization must use repository-owned actual
  SVG icons, never an external icon font/library.
- Every figure has a stable visual identifier, Korean title, concise takeaway,
  provenance, and a text/list/table equivalent sufficient to recover its
  decisions and relationships.
- Do not add a library when a few semantic elements and CSS convey the model.

### Tier 1 — bounded declarative authoring (normal escalation)

- Mermaid source for conventional diagrams; Vega-Lite JSON for quantitative
  charts.
- Pin the renderer version and configuration; render static SVG during an
  explicit authoring/build step; check in both source and Human artifact.
- The browser document references only local relative assets and renders the
  checked-in SVG/HTML with no server and no JavaScript.
- Optional JavaScript may reveal details or coordinate highlighting, but the
  same fact must already exist in the baseline.

### Tier 2 — specialist static layout

- Graphviz/DOT for dense dependency/DAG layouts.
- Observable Plot when its code API materially simplifies a chart that is
  awkward in Vega-Lite.
- D3 only for a bespoke visual grammar that no bounded declarative candidate
  expresses.
- Record why Tier 0/1 was insufficient and keep the generated static artifact
  and semantic equivalent.

### Tier 3 — specialist interactive runtime

- Cytoscape.js for complex network exploration; ECharts for interaction-rich
  quantitative graphics.
- Vendor only the required modules/build locally and load scripts with `defer`
  or modules after baseline content.
- Supply keyboard-operable controls, visible focus, reduced-motion behavior,
  programmatic status updates where needed, and a semantic graph/data table.
- If the enhancement fails, the page remains a complete Specification rather
  than an error placeholder.

## Smallest default and optional stacks

### Smallest recommended default stack

**Published/browser dependencies:** none beyond the existing local CSS and
optional document-navigation JavaScript.

**Authoring capabilities:**

- native semantic HTML/CSS/actual SVG;
- pinned Mermaid CLI only when a Specification contains a conventional diagram;
- a deterministic SVG post-processing/sanitization step and a mapping check
  between visual identifiers and paired Project Skill references.

Vega-Lite is the first optional addition, not a universal install: add a pinned
Vega-Lite/Vega renderer only in a project that contains data-driven quantitative
figures. This interpretation keeps “default” genuinely small while establishing
one predictable escalation path.

### Optional specialist stack

- **Vega-Lite + Vega SVG export:** quantitative grammar.
- **Graphviz CLI:** static dense graph layout.
- **Cytoscape.js:** interactive network/Agent graph, accompanied by separately
  generated or hand-authored static fallback.
- **ECharts SVG SSR + selectively vendored runtime:** rich chart interaction.
- **Observable Plot + D3:** concise JS-authored specialist charts.
- **Selected D3 modules:** bespoke visualization only.

Do not install all of these globally or ship them in a shared browser shell.
Each Specification declares only the sources, generated artifacts, renderer
versions, and runtime modules it actually uses.

## Proposed Specification authoring contract

This is a proposal for later Human acceptance, not a current repository rule.

### 1. One semantic body, paired projections, explicit visual mapping

Each meaningful visual receives a stable ID such as `visual-information-lifecycle`.
The Human HTML uses that ID on `<figure>`; the paired Project Skill references
the same ID in an English visual-source index. Both projections must carry the
same nodes, edges, states, quantities, epistemic status, and unresolved
questions. Translation, layout, color, and annotation may differ; facts may not.

A visual mapping entry should record:

- stable visual ID and visualization class;
- Human artifact relative path or inline element ID;
- AI-readable source relative path and format (`mermaid`, `vega-lite`, `dot`, or
  reviewed structured JSON for a network);
- source data path/hash when quantitative;
- renderer name, exact pinned version, configuration/theme identifier, and
  deterministic render command;
- equivalent Human table/list and paired Skill section;
- provenance and epistemic category: accepted decision, observed evidence,
  hypothesis, or unresolved decision.

The mapping is a synchronization aid, not a third authoritative semantic body.

### 2. Separate source from artifact

- **AI-readable source:** concise textual semantics in the paired Project Skill
  directory (`references/` for Mermaid/DOT explanations or `assets/` for JSON
  data/specifications, following the Project Skill contract). It is reviewed for
  relationship and data semantics.
- **Human-rendered artifact:** checked-in SVG/semantic HTML below the paired
  Planning document. It is reviewed for Korean comprehension, responsive layout,
  accessibility, and visual design.
- **Optional enhancement:** local JS/data used only after the static artifact is
  present. Runtime state is not refined information and may not be the sole place
  a decision or relationship exists.

Generated SVG must not be the only AI-readable source. Conversely, Mermaid,
Vega-Lite, DOT, or network JSON must not be embedded as the only Human fallback.

### 3. Static publication and deterministic rendering

- Pin renderer and transitive dependencies in the project's authoring lockfile;
  vendor browser dependencies locally if Tier 3 is used.
- Disable animation for checked-in artifacts unless motion conveys essential
  state; respect `prefers-reduced-motion` for enhancement.
- Fix locale, fonts, dimensions/viewBox policy, data ordering, seeds/layout
  positions where supported, theme tokens, and renderer configuration.
- Never fetch remote fonts, scripts, icons, data, or images at render/view time.
- Re-rendering is an explicit implementation/verification activity outside this
  Inquiry; generated diffs require semantic and visual review.

### 4. Accessibility and no-JavaScript requirements

Every visual must have:

- a `<figure>` and `<figcaption>` with a meaningful Korean title and takeaway;
- a concise accessible name/description on SVG when useful;
- an adjacent semantic list/table that communicates all essential facts, not
  merely “a chart is shown”;
- color-independent encoding, sufficient contrast, legible zoom, and responsive
  overflow/viewBox behavior;
- no essential hover-only content;
- keyboard-operable controls and visible focus for every interactive action;
- reduced-motion handling and status announcements for changing views when
  applicable.

Generated SVG ARIA is helpful but is not proof of accessibility. Dense SVG
element-by-element narration is often worse than a curated summary and table.

### 5. Security contract

- Treat diagram text, JSON, labels, URLs, HTML-like labels, format strings, and
  transforms as code-adjacent untrusted input unless they come from reviewed
  refined sources.
- Render in a disposable, network-disabled process with time, memory, input-size,
  node/edge, and output-size limits. Never allow source-controlled render input
  to read arbitrary filesystem paths.
- For Mermaid keep the default `securityLevel: "strict"`, retain protected
  configuration keys, and cap `maxTextSize`/`maxEdges`; do not use `loose` or
  `antiscript` for untrusted material. Mermaid documents that strict encodes HTML
  and disables clicks, while sandbox isolates rendering in an iframe.
  [Mermaid security levels](https://mermaid.js.org/config/usage), [secure keys](https://mermaid.js.org/config/schema-docs/config-properties-secure.html)
- For ECharts reject external configuration that can supply arbitrary regex or
  HTML. The official security guidance warns that malicious regex transforms can
  freeze the browser or block the Node event loop during SSR. [ECharts security
  guidance](https://echarts.apache.org/handbook/en/best-practices/security/)
- For Graphviz reject/allowlist `URL`/`href`, `image`, `imagepath`, stylesheet,
  and HTML-like label features; run the native binary with OS-level containment.
- Sanitize generated SVG before publication: strip scripts, event-handler
  attributes, `foreignObject` unless explicitly reviewed, remote references,
  unsafe URI schemes, and unexpected embedded resources. Preserve required ARIA
  and internal fragment references.
- Use a restrictive document CSP as defense in depth. Do not assign untrusted
  content through `innerHTML`.

### 6. Licensing and dependency record

Maintain a local third-party notice/manifest for every vendored renderer and its
transitive redistributed components. MIT, ISC, BSD-3-Clause, and Apache-2.0 are
generally compatible with commercial redistribution when their notice and other
conditions are followed, but this is not legal advice. Graphviz's current
EPL-2.0 obligations are materially different and require a project/legal review
before distributing the program. Generated artifacts and source/data may have
separate copyright or data-license obligations.

## Build-time versus browser-runtime decision

| Concern | Build-time static SVG/HTML | Browser runtime |
| --- | --- | --- |
| No-JS readability | Complete by construction | Requires a separately authored fallback |
| Local/offline viewing | Direct file opening works when assets are relative | ES modules/fetch/CORS behavior may require a server; UMD can work locally but still depends on JS |
| Accessibility | Stable markup can be reviewed and supplemented | Dynamic focus, status, keyboard, and canvas alternatives require custom work |
| Determinism/versioning | Renderer/version/config and artifact can be pinned and diffed | Browser, viewport, timing, random layout, and interaction introduce variability |
| Security | Risk concentrated in controlled authoring process; artifact can be sanitized | Untrusted input is processed on every view and expands browser attack/availability surface |
| Interaction | Static overview only | Filtering, zoom, selection, linked views, live data |
| Maintenance | Authoring toolchain plus checked-in output | Authoring toolchain, vendored runtime, compatibility, fallback, interaction, and accessibility code |

Therefore build-time static SVG/HTML is the default. Runtime rendering is
justified only when interaction changes the Human's ability to understand a
complex model, not merely because the library offers animation or tooltips.

## Migration implications for `agent-factory-core`

Observed repository evidence:

- The current Korean `index.html` already uses semantic sections, a native
  responsibility table with scoped headers, actual inline SVG icons, curated
  semantic HTML visual maps, and ARIA labels.
- Its `app.js` only enhances section navigation; core content remains readable
  without JavaScript.
- The paired Project Skill already has five Mermaid definitions in
  `.codex/skills/agent-factory-core/references/diagrams.md`, explicitly described
  as AI-readable equivalents of the Human semantic HTML/inline SVG.

This is already close to the recommended Tier 0/Tier 1 contract. A migration
does **not** justify replacing the current curated Human diagrams wholesale with
runtime Mermaid.

Smallest proposed migration, subject to a later accepted Work request:

1. Preserve current semantic HTML, native table, inline SVG icons, CSS, and
   no-JS behavior.
2. Assign stable visual IDs to the five important relationships and add explicit
   mapping metadata in the paired AI diagram reference.
3. Compare each Mermaid graph's nodes/edges/status labels with its Korean Human
   equivalent; correct semantic drift in both projections together.
4. Only render Mermaid to checked-in static SVG where automatic layout improves
   the Human result. Keep the bespoke system map, lifecycle cards, engineering
   stack, and alignment map as semantic HTML when they are clearer and more
   accessible than generated SVG.
5. Add concise figure captions/takeaways and adjacent relationship lists where a
   `role="img"` summary is currently the sole nonvisual equivalent.
6. Do not add Vega-Lite, Cytoscape, ECharts, Plot, D3, or Graphviz unless future
   core content introduces actual quantitative data or a graph too complex for
   the current representations.

Migration risk is primarily churn: mechanically converting good semantic HTML
to library-generated SVG could reduce responsiveness/accessibility, create noisy
diffs, and falsely imply that Mermaid source is the singular semantic authority.

## Risks, limitations, and contradictions

- **No library guarantees comprehension.** Visual-first still needs information
  design, written takeaways, careful density, and Human review.
- **ARIA is partial.** Mermaid, Vega-Lite, Plot, and ECharts expose useful ARIA
  features, but generated per-mark narration can overwhelm users; Cytoscape's
  canvas and Graphviz SVG need separately designed alternatives.
- **Static export loses interaction.** Tooltips, selections, zoom state, and
  animation do not survive as equivalent refined meaning. Essential conclusions
  must be stated outside interaction.
- **Determinism has limits.** Fonts, renderer changes, force layouts, locale, and
  browser engines can change geometry. Pinning and checked-in output reduce but
  do not eliminate this.
- **Duplicate representation can drift.** Source, generated SVG, fallback table,
  Korean HTML, and English Skill create more synchronization surfaces. Stable IDs
  and a mapping check reduce this; review remains necessary.
- **License suitability is conditional.** The listed licenses permit broad use
  under conditions, but transitive components, data, fonts, and generated asset
  inputs require their own review. Graphviz's 2026 EPL change deserves special
  attention.
- **Package-size comparison is inconclusive.** No fair official cross-library
  measure was found, so this report avoids misleading byte rankings.
- **No experiment was performed.** The Inquiry did not install packages, render
  sample diagrams, test accessibility trees, measure bundles, or run repository
  tests, consistent with its authority. Conclusions are documentation- and
  code-evidence-based.

## Unresolved Human decisions

1. Whether to accept the tiered policy and “zero visualization runtime” as the
   project-wide default.
2. Whether renderer source/artifact mapping should be a lightweight Markdown
   index, structured manifest, or convention enforced by later tooling.
3. Whether a pinned Node authoring toolchain is acceptable for Mermaid and
   Vega-Lite, or whether the project requires a different reproducible build
   environment.
4. Whether Graphviz's EPL-2.0 obligations fit planned plugin distribution.
5. The minimum accessibility acceptance procedure for generated and interactive
   visuals, including keyboard and screen-reader review ownership.
6. Whether interactive visualizations are permitted inside Planning documents
   at all, and if so which CSP and vendoring policy they must satisfy.

## Smallest useful follow-up Inquiry

If the Human accepts the direction, the smallest evidence-producing follow-up
is a **non-canonical prototype comparison** inside a fresh Inquiry workspace:
render one existing core Mermaid diagram and one small Vega-Lite chart to static
SVG with pinned candidates, then inspect output determinism, sanitized SVG,
offline/no-JS behavior, responsive layout, and browser accessibility trees
against the proposed contract. It should not edit the existing Specification or
Project Skill and should report the actual vendored/build sizes observed under
one declared configuration.

