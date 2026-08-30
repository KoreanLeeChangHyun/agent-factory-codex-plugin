# Design Convention

Use this reference for Human-facing interfaces and browser documents. Preserve
the owning product's established design system when it exists; these rules are
the Agent Factory baseline, not permission to restyle unrelated surfaces.

## Interface baseline

- Use semantic HTML and a clear information hierarchy.
- Preserve keyboard access, visible focus, readable contrast, and responsive
  behavior.
- Keep essential content readable without JavaScript. Use JavaScript for
  progressive interaction rather than as a prerequisite for comprehension.
- Keep browser-document dependencies local and relative when the artifact must
  remain portable.
- Use visible text for meaning and actual SVG for every user-facing icon. Read
  `svg-icon.md` whenever icons are created, changed, or reviewed.
- Use diagrams, flows, graphs, or tables only when they make relationships
  materially easier to understand. Keep AI-readable Mermaid sources aligned
  with Human-facing visual representations when both exist. Read `diagrams.md`
  whenever ERD, game-behavior, sequence, or Agent Factory core diagrams are
  created, changed, or reviewed.

## Scope-specific design

Workspace's VS Code-shaped `Activity Bar -> Primary Sidebar -> Workspace`
layout is a Workspace interface decision, not a universal design system. Apply
`skills/workspace/references/interface.md` for that surface. Apply
`skills/document/references/specification.md` for Human-facing
Specification documents, including their Korean-language and paired-document
requirements.

Do not copy a shell-specific layout, visual token, or navigation model into a
different product surface without project evidence or Human direction.

## Evidence basis

The accessibility baseline follows WCAG 2.2 and WAI guidance: functionality
must remain keyboard-operable, keyboard focus must be visible, and text and
controls need sufficient contrast. Progressive enhancement starts from usable
baseline content before adding richer behavior:

- [W3C: Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/wcag/)
- [W3C WAI: Accessibility Principles](https://www.w3.org/WAI/fundamentals/accessibility-principles/)
- [W3C: Progressive enhancement](https://www.w3.org/wiki/Graceful_degradation_versus_progressive_enhancement)
