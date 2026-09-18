# Theme

- Preserve the product's established theme and design system; this baseline does not
  authorize restyling unrelated surfaces.
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
