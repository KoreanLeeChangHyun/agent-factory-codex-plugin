# Local Project Viewer

## Boundary

The local Viewer is the Human-facing projection of the target Project Skill,
Git status, progress, decisions, and diagram sources. HTML, CSS, and JavaScript
own presentation only. They are never the project source of truth.

Run:

```text
python3 <plugin-root>/skills/projects/scripts/viewer.py --project-root <project-root>
```

The server binds to `127.0.0.1` by default and accepts only an expected Host
header. A non-loopback bind requires both an explicit Human request and the
`--allow-non-loopback` flag. Automatic browser opening, restart, deployment, or
external transmission also requires an explicit Human request.

## Data sources

The Viewer reads only:

- `.agent-factory/skills/project/SKILL.md`;
- that Project Skill's `references/` and `diagrams/` trees;
- read-only Git branch, HEAD, and status output.

The JSON API and static assets expose no write method. Do not read environment
variables, credentials, arbitrary repository files, ignored files, or file
content outside the Project Skill.

Project Skill reads are descriptor-anchored, never follow symlinks, and reject
multiply linked files. The API skips non-UTF-8 sources, individual files over
512 KiB, content beyond a 2 MiB request budget, and files after the 200-file
limit for each source tree. Git queries run without system/global configuration,
optional locks, filesystem monitoring, or the untracked cache.

## Diagrams

Prefer inspectable JSON or DSL sources. The bundled browser view renders the
simple JSON node-edge shape below with local JavaScript and shows other sources
as text without changing them:

```json
{
  "nodes": [{"id": "main", "label": "Main Agent"}],
  "edges": [{"source": "main", "target": "work", "label": "delegates"}]
}
```

Keep richer renderer selection in the `specifications` diagram convention.
The Viewer may later add React Flow, ECharts, Cytoscape, or D3 as a presentation
dependency without moving canonical ownership out of the Project Skill.
