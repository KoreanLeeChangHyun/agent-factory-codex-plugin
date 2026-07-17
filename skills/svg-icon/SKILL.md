---
name: svg-icon
description: Enforce SVG-only icon implementation for UI, frontend, design-system, wireframe, shell, sidebar, toolbar, navigation, button, menu, file-tree, and visual-polish work. Use whenever Codex creates, replaces, reviews, or refactors icons, icon buttons, activity bars, explorer trees, status indicators, or icon-like controls.
---

# SVG Icon Only

## Rule

Use SVG for every user-facing icon.

Do not implement icons with:

- Emoji.
- Unicode symbol characters such as chevrons, bullets, triangles, or glyphs.
- Icon fonts.
- Text labels pretending to be icons.
- CSS-only geometric shapes.
- Raster images such as PNG, JPG, GIF, or WebP.

## Acceptable SVG Forms

Use one of these forms:

- Inline `<svg>` markup in HTML.
- A framework component that renders an actual `<svg>` element.
- A referenced `.svg` asset through `<img src="...svg">`, `<use href="...">`,
  or equivalent when the existing codebase already supports that pattern.
- A maintained SVG icon library when it renders SVG output.

Prefer inline SVG for compact application UI controls unless the local codebase
already has a stronger SVG asset or symbol pattern.

## Workflow

1. Inspect the target UI and existing icon patterns before editing.
2. Replace every icon-like glyph or CSS shape in the touched area with SVG.
3. Keep accessible names on the interactive element, not only inside the SVG.
4. Mark decorative SVG icons with `aria-hidden="true"` and `focusable="false"`.
5. Keep visible text separate from icon markup.
6. Verify the final DOM or source contains SVG for the touched icons.

## Frontend Checks

When reviewing or implementing UI, specifically check for:

- Chevron characters such as `›`, `⌄`, `▸`, `▾`, `▲`, `▼`, `←`, `→`.
- Button labels such as `...` used as an icon.
- CSS `::before` or `::after` icons that are not backed by actual SVG output.
- Icon font class names.
- Data URI masks used where an actual inline SVG icon would be clearer and more
  inspectable.

If any of these appear in a touched icon area, replace them with SVG unless the
Human explicitly narrows the task away from icon work.

## Source And Licensing

Use existing project SVGs first. When importing SVG paths from an external icon
set, record the source and license in the relevant project artifact or code
comment when required by the license.
