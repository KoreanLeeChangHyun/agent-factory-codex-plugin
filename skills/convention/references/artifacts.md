# Artifacts

## 1. Storage and delivery

- **Mandatory:** never create a directory the Human has not agreed to, anywhere in the
  project, including temporary, scratch, output, backup, test or tool directories. Use
  existing directories, paths the task explicitly names, `docs/artifact/`, or the standard
  Document locations (`docs/progress/`, `docs/lessons-learned/` and the like).
- `docs/artifact/` is the agreed home for generated outputs; use it by default and actively.
- Use `<project-root>/docs/artifact/` for AI-created files outside Document packages:
  HTML previews or interactive explanations, SVG illustrations, screenshots,
  generated images and other task deliverables. Create it when an output is needed.
- `docs/artifact/` is a directory, not a Document type or an active Skill. Files need no
  `SKILL.md`, YAML metadata, document category or mandatory package structure.
- Store each bundle at `docs/artifact/<category>/<task-or-topic>/`, using the purpose
  categories below. Releases use `docs/artifact/release/<version>/`.
- Classify the bundle by its primary purpose, not each file's extension. Keep HTML,
  CSS, scripts, images and supporting files together with working relative links.
  Preserve existing outputs unless replacement is in scope.
- Follow the Human's explicit output location when supplied. Keep application source
  in its owning source tree and canonical Documents in their Document locations.
  Assets owned by a Document remain in that Document's `assets/` directory.
- Keep runtime state, logs and disposable execution scratch files in the producing
  run's storage. Use `docs/artifact/` for outputs intended to be inspected or reused.
- Never create ad-hoc temporary or scratch directories or files in the project root or
  alongside source; use the run's storage or the system temp directory and clean it up.
- Artifact files are not automatically cataloged as Documents, synchronized to
  `.codex/skills/`, `.claude/skills/`, `.agents/skills/`, published or committed. Preserve the task's existing permissions.
- Verify the output using checks appropriate to its format and provide a clickable
  file link in the result. Distinguish a saved file from a rendered or visually checked
  result; do not claim browser or image inspection unless it occurred.

## 2. Purpose and ownership

| Category | Purpose | Examples |
|---|---|---|
| `preview` | Inspect an idea, layout or interaction before or alongside implementation. | HTML demos, interactive explanations, mockups and their supporting files. |
| `evidence` | Preserve inspectable evidence of an implementation, test or experiment. | Screenshots, measurements, selected check logs and reproducible sample inputs. |
| `media` | Reuse a produced visual asset. | Icons, illustrations, generated images and exported variants. |
| `release` | Deliver or reproduce a particular released version. | Packages, checksums and intentionally retained distribution snapshots. |

- Keep mixed-format bundles intact. A demo screenshot can remain with its preview;
  a screenshot used as test evidence belongs with that evidence. Classification
  does not imply approval, correctness, publication or a Verification pass.
- Durable analysis, research and historical reports are canonical Documents; route
  them through the [Document layout](../../document/references/layout.md). Their
  owned attachments belong in the Document's `assets/`. An exported report can remain
  an artifact only as a derived delivery, not a competing editable original.
- Keep active runtime homes, locks, caches, dependency installations and disposable
  raw logs in run storage or system temporary storage. Retain selected evidence in
  `evidence`; a completed experiment does not make its entire runtime a deliverable.
- Historical bundles may contain source snapshots. Preserve their provenance and
  bytes; do not treat them as the application's editable source or execute them
  merely to classify them.

## 3. Authorized reorganization

- Inventory destinations and incoming references before moving existing bundles.
  Back up originals, check collisions and concurrent writes, preserve file content,
  and remove old paths only after checking the copied outputs.
- Update live generators, test output defaults, demos and links together. Preserve
  historical quoted paths as evidence; rewrite actual navigational links when needed.
- Do not follow symlinks into dependencies or runtime data while migrating. Preserve
  the link itself separately when it is execution scaffolding rather than a deliverable.
- Do not delete identical files merely because their hashes match. Separate release
  versions and historical observations can legitimately contain identical assets.
