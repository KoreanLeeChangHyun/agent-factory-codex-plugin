<INSTRUCTIONS>
<agent-factory>
# Project guidance

- Use the relevant Agent Factory Skills when the task calls for them.
- Detailed contracts live in their owning Skills and are not duplicated here.
- Record every error and observed Human/AI judgment difference using Document
  `references/lessons-learned.md`, including unresolved and recovered errors.
  Follow that guide when consolidating accumulated lessons into Skill rules.

<a id="reference-locations"></a>

## 1. Reference locations

- Resolve the installed Agent Factory `agent`, `convention` and `document` Skills
  from the host's available Skills.
- The following references are relative to their owning installed Skill roots, not to
  this project:

- Managed graph, role boundaries, and project-specialized Work profiles: Agent
  `SKILL.md` and `references/project-specialist.md`
- Shared conventions and task routing: Convention `SKILL.md`
- Standalone HTML, SVG, screenshots and other generated files: Convention `SKILL.md#artifacts`
- Human decisions: Convention `SKILL.md#human-decisions`
- Runtime locations: Agent `references/home-runtime.md`
- Document types, routing and single-source packages: Document `SKILL.md` and its
  type-specific writing guides

<a id="ownership-and-storage"></a>

## 2. Ownership and storage

- This project uses Agent Factory.
- Use `<project-root>/docs/artifact/` for standalone generated outputs outside Document
  packages, following Convention's Artifacts contract. No `SKILL.md` wrapper is required.
- Keep canonical Refined and Human-requested Specification (Skill document) packages below `docs/refined/`
  and `docs/skills/`, using `<category>[-<domain>]-<name>/SKILL.md` in the Human's language plus optional `assets/`
  under the Documents contract.
- Optional `.codex/skills/`, `.claude/skills/` and `.agents/skills/` Specification/Skill exposure derives from that same source, never a
  separate editable original.
- Refined uses `document-type: processed` for compatibility and is not automatically an active Skill or Specification.
- Route Original packages below `docs/original/`.
- Route contract Progress below `docs/progress/<contract-id>/` and Lessons Learned below
  `docs/lessons-learned/`, following their Document type guides.
- Discover Original, Refined, Progress and Lessons Learned packages through the Document Skill's local catalog
  and search commands; they are not part of the Codex Skill catalog.
- Preserve existing Documents without migration or conversion.
- Preserve existing project guidance; do not copy the installed plugin's Skills into
  this project.
- Resolve managed runtime locations through the installed Agent runtime, outside the
  checkout.
</agent-factory>
</INSTRUCTIONS>
