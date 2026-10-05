# Theme

- Design and theme consistency are mandatory for every UI creation or modification,
  including small layout fixes. Preserve the product's established theme and design
  system; this baseline does not authorize restyling unrelated surfaces.
- Product and technical Design Specifications belong to the [Document contract](../../document/SKILL.md); this reference
  owns visual and interface presentation.

<a id="interfaces"></a>

## 1. Interfaces

- Use semantic HTML, clear hierarchy, keyboard access, visible focus, readable contrast
  and responsive layout.
- Keep essential content readable without JavaScript; progressively enhance interaction.
  Portable browser documents use local, relative dependencies.
- Use visuals only when they clarify relationships. For diagrams, read `diagrams.md`; keep
  maintained source and rendered views aligned.
- Match language and detail to the reader. Follow the project's own layout and navigation
  conventions.
- Keep borders consistent with the established theme. Do not highlight individual elements
  by changing border color or thickness, or adding a colored accent to one edge.
  Use typography, spacing or established surface treatments for emphasis; preserve
  accessible keyboard focus indicators.

<a id="design-consistency"></a>

### 1.1. Design and theme consistency

- Before editing, inspect the accepted design, neighboring surfaces, shared components
  and theme tokens. Use them as the baseline, not an isolated screenshot or personal taste.
- Reuse existing components and semantic theme tokens for colors, typography, spacing,
  control sizes, borders, radii, icons and interaction states. Match equivalent controls
  across tabs and screens; do not introduce local approximations or fixed colors that
  bypass the active theme.
- Preserve the design in every supported theme, including light, dark and high-contrast
  variants where available. Include hover, focus, selected, disabled and error states.
- A requested spacing or height adjustment does not authorize a new visual style.
  Follow an explicit Human-requested design change within its scope and keep all other
  surfaces consistent; do not invent exceptions for convenience.

<a id="tabbed-layout"></a>

### 1.2. Tabbed layout

- At the same viewport size and zoom, a tabbed window or panel MUST keep the same outer
  height and stable header, tab strip and footer positions when switching tabs.
  Never resize the container to each tab's content length.
- Resolve unused space inside that fixed container through row/card heights, spacing
  and layout appropriate to the existing design. Do not shrink the whole window to
  remove blank space or distort controls, text and icons to fill it.
- Adapt the shared outer height to available viewport space when the viewport or zoom
  changes; apply the same rule to every tab. Keep minimum usable control sizes and
  scroll overflowing content inside the panel without clipping or hiding functionality.
- Loading, empty, populated and error content must preserve the same tab geometry.
  Change this contract only when the Human explicitly requests different tab geometry.

<a id="visual-acceptance"></a>

### 1.3. Visual acceptance

- Before reporting a UI change complete, compare it with neighboring components and
  the accepted design in the rendered interface. Source inspection or passing logic
  tests alone does not establish visual consistency.
- For tabbed UI, switch through every tab at a fixed viewport and zoom. Compare outer
  bounds and header/tab/footer positions; inspect row heights, spacing and overflow.
- Check supported themes and relevant interaction/content states, plus narrow or short
  viewports and enlarged text. Preserve keyboard access, visible focus and scrolling.
- Correct in-scope mismatches before completion. Report which rendered environment and
  states were checked, and explicitly identify anything unavailable or unverified.
  A browser fixture is not evidence of a check in the actual host application.

<a id="svg-icons"></a>

## 2. SVG icons

- Every user-facing icon must render actual SVG: inline markup, a component, referenced
  `.svg`/`use` asset or compatible SVG library. Prefer existing project
  patterns; otherwise use inline SVG for compact controls.
- No emoji, Unicode/icon glyphs, icon fonts, text posing as icons, CSS-only geometry or
  raster icons. Keep visible labels separate.
- Inspect touched icon areas, including chevrons, ellipsis buttons, pseudo-elements and
  masks; replace non-SVG icons unless the Human excludes icon work. Verify actual SVG
  output in source/DOM.
- Put accessible names on interactive elements. Decorative SVG uses `aria-hidden="true"` and
  `focusable="false"`.
- Reuse project assets first; record external source/license where required.

<a id="sources"></a>

## 3. Sources

- [WCAG 2.2](https://www.w3.org/TR/wcag/)
- [WAI: Accessibility principles](https://www.w3.org/WAI/fundamentals/accessibility-principles/)
- [W3C: Progressive enhancement](https://www.w3.org/wiki/Graceful_degradation_versus_progressive_enhancement)
