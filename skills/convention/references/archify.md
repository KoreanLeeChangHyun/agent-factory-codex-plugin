# Archify diagrams

## 1. Renderer and source

- Use `python3 <plugin-root>/scripts/archify.py` for architecture and sequence JSON assets.
- This boundary supports `architecture` and `sequence`. Official Archify also defines
  workflow, dataflow and lifecycle; they are outside this minimal integration. ERD is unsupported.
- The renderer is [tt-a1i/archify v3.0.1](https://github.com/tt-a1i/archify/tree/2ab3cae7ac2c2a55d7386ca789d03c4fcd31816c),
  pinned to commit `2ab3cae7ac2c2a55d7386ca789d03c4fcd31816c` in
  `<plugin-root>/runtime/system/archify-lock.json`. It is MIT licensed and requires Node.js >=18.
- `install` verifies the archive SHA-256 and extracted file tree. Every validation/render
  checks the installed file tree before executing the official `bin/archify.mjs`.
- The official package is private; do not substitute the unrelated npm `archify` package.
  Generated validators and viewer resources are already shipped; no global or npm install is needed.
- Obtain the pinned schemas from `<tool-dir>/schemas/architecture.schema.json`,
  `sequence.schema.json` and `common.schema.json`. `schema_version: 1` is the input format version,
  distinct from renderer version 3.0.1. Use the actual schema instead of inventing fields.
- Treat the lock as reviewed source. To update it, inspect the official tag/commit, recalculate
  archive/tree hashes with this install layout, and run real schema, delivery and browser checks.

## 2. Validate, render and open

- With the matching Agent Factory extension, `*.archify.json`, `*.architecture.json`
  and `*.sequence.json` open directly as a validated diagram. Ordinary `*.json` files
  remain text. The supported `diagram_type` in the content selects the renderer.
- The editor's source button opens the original JSON beside the view; saving refreshes
  it. Errors preserve source access. The first preview prepares the pinned renderer
  automatically in system temp, using the matching plugin and Python/Node on the workspace
  host. It creates no project output. A trusted workspace and network access for initial
  preparation are required; no standalone desktop browser is needed for the editor.
- The editor receives SVG/CSS from `preview --tool-dir <tool-dir>` via stdin JSON.
  It isolates the SVG in a data image and runs only extension-local UI scripts. The
  standalone HTML's scripts are not injected into chat or the file editor.
- Store JSON once in a Document package's `assets/`, linked from its `SKILL.md` or reachable
  reference. Preserve readable meaning near the link; follow [Diagrams](diagrams.md#document-assets).
- Use existing or agreed paths for dependencies. `install --tool-dir <run-or-agreed-runtime-directory>/archify-3.0.1`
  prepares a new directory outside the project checkout; its parent must exist. Existing targets are never replaced.
- Read [CLI arguments](../../tool/references/usage/archify.md) before execution. Paths inside
  `--project-root` may be absolute or project-relative. `--tool-dir` is an explicit installed directory.

```sh
python3 <plugin-root>/scripts/archify.py install --tool-dir <run-directory>/archify-3.0.1
python3 <plugin-root>/scripts/archify.py validate --project-root <project-root> --tool-dir <tool-dir> docs/skills/<package>/assets/system.architecture.json
python3 <plugin-root>/scripts/archify.py render --project-root <project-root> --tool-dir <tool-dir> docs/skills/<package>/assets/system.architecture.json --output docs/artifact/preview/<topic>/architecture.html --open
python3 <plugin-root>/scripts/archify.py open --project-root <project-root> docs/artifact/preview/<topic>/architecture.html
```

- Prepare the output parent using the agreed [Artifacts](artifacts.md) locations. The tool
  does not create project directories. Use a new output filename on rerender.
- `render` calls official `validate` and `deliver --json` on an immutable input snapshot in
  system temporary storage, then exclusively creates the requested HTML. The official delivery
  report describes this staged output; scratch sidecars are not published as final artifact provenance.
- The response includes the original input path/hash, HTML path/hash, file URI, pinned version/commit,
  and official validation/delivery diagnostics. Link the generated artifact beside the JSON source.
- `meta.output` remains required and officially validated, but does not select the public write
  destination. Only `--output` selects a new `docs/artifact/<category>/<topic>/*.html` file.
- `--open` or `open` uses the OS browser (`xdg-open`, macOS `open`, Windows file association),
  with an argument array and no shell. It runs on the machine hosting the CLI/files.
- Existing Agent Factory local Markdown links open files in VS Code. For interactive HTML,
  run `open` or open the generated file in an external browser. Do not inject HTML into chat.
- In remote/headless environments, GUI opening may be unavailable; use the reported path/URI
  on a desktop with access to the files. Do not claim a GUI check from successful file generation.

## 3. Failure handling

- Failures return `ok: false`, a diagnostic, and exit code 1. Correct the reported issue and retry.
- Invalid JSON/schema and unsupported types fail before publishing HTML. The input remains unchanged.
- In architecture grid layouts, give nodes explicit `row`/`col` or `pos`; omitted coordinates
  can overlap nodes and cause the pinned renderer to report `internal/unclassified` during routing.
- Missing renderer: run `install` into a new agreed directory. Integrity mismatch: inspect the
  changed installation and prepare a new pinned directory; the tool never repairs it in place.
- Missing or older Node.js: provide Node.js >=18 on PATH. No provider configuration is changed.
- Missing output parent, path traversal, symlinks, and existing output files are rejected.
  Choose a permitted path and new filename; do not delete or overwrite another artifact to retry.
- Custom remote brand URLs are unsupported in this local boundary. Use built-in brands/default icons.
- Browser failure after delivery preserves HTML and reports its location; use `open` later.
- Existing Mermaid rendering, chat CSP and local resource roots are unchanged.
