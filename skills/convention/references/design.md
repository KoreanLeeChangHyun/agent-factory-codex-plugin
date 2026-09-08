# Design

Preserve the product's established design system; this baseline does not
authorize restyling unrelated surfaces.

## Interfaces

- Use semantic HTML, clear hierarchy, keyboard access, visible focus, readable
  contrast and responsive layout.
- Keep essential content readable without JavaScript; progressively enhance
  interaction. Portable browser documents use local, relative dependencies.
- Use visuals only when they clarify relationships. For diagrams, read
  `diagrams.md`; keep maintained source and rendered views aligned.
- Match language/detail to the reader. Read authenticated MCP Workspace or
  Document guides for those surfaces; do not export their layout/navigation
  conventions to other products without evidence or Human direction.

## SVG icons

- Every user-facing icon must render actual SVG: inline markup, a component,
  referenced `.svg`/`use` asset or compatible SVG library. Prefer existing project
  patterns; otherwise use inline SVG for compact controls.
- No emoji, Unicode/icon glyphs, icon fonts, text posing as icons, CSS-only
  geometry or raster icons. Keep visible labels separate.
- Inspect touched icon areas, including chevrons, ellipsis buttons, pseudo-elements
  and masks; replace non-SVG icons unless the Human excludes icon work. Verify
  actual SVG output in source/DOM.
- Put accessible names on interactive elements. Decorative SVG uses
  `aria-hidden="true"` and `focusable="false"`.
- Reuse project assets first; record external source/license where required.

## Sources

- [WCAG 2.2](https://www.w3.org/TR/wcag/)
- [WAI: Accessibility principles](https://www.w3.org/WAI/fundamentals/accessibility-principles/)
- [W3C: Progressive enhancement](https://www.w3.org/wiki/Graceful_degradation_versus_progressive_enhancement)
