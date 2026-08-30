# Agent Factory for Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for Human-directed software delivery. Main is
the Human-facing Interview, orchestration, and integration layer; it routes
bounded tasks, including research and implementation, to Work and independent
checking to Verification unless the Human skips it. The plugin supports
evidence exploration, defines three Document types, maintains paired
Specifications, gathers distributed source material without promoting it to
trusted truth, and provides a logical lifecycle contract for Agent-usable
external tools and connectors.

## Included skills

The plugin exposes exactly six public skills:

- `agent`: Run the exact `Main -> Work -> Verification` graph through managed
  sessions. Main orchestrates, Work performs the bounded task, and Verification
  independently returns pass or fail unless the Human skips it.
- `convention`: Own and apply the Agent Factory core model plus directory,
  development, library, design, annotation, and document conventions.
- `document`: Define and maintain Original (원본문서), Processed (가공문서),
  and Specification (스펙 문서) Documents. The conceptual ordering
  `Original -> Processed -> Specification` expresses only possible derivation
  or evidence relationships; relationships may be absent, one-to-many,
  many-to-one, or many-to-many. A Specification is accepted and reconciled
  project knowledge and uses paired Korean
  Human-readable HTML/CSS/JavaScript and AI-readable Skill views. Project
  Skills use the lowercase hyphen-case name
  `<category>-<name>`; their directory and `SKILL.md` frontmatter
  `name` match exactly, and they live below `.codex/skills/` in the owning
  project.
- `gather`: Select and synchronize bounded external sources as Original
  Documents while preserving fidelity, provenance, identity, and resolved
  destinations. It uses connector capability prepared through Tool without
  transferring synchronization ownership.
- `tool`: Provide one logical lifecycle and control contract for Agent-usable
  external tools and connectors: discovery, install/update/remove routing,
  connection/auth lifecycle, opaque credential references, requested/granted
  scopes, health, enablement, and capability metadata. The authoritative host,
  plugin, MCP server, or project manifest remains the source of truth.
- `workspace`: Provide the Human-facing control tower for navigating and
  managing Agents, documents, and project views without replacing their owning
  stores or authority.

Evidence exploration is a capability Work may use while performing its bounded
task, and Interview remains Main's adaptive Human-facing capability. Neither is
a separate Agent role; the only roles are Main, Work, and Verification.

Main is the same graph node when used directly in Codex CLI, hosted through
`codex exec`, or surfaced by a VS Code extension. Codex CLI is the default
entry interface; these hosts do not add Agent roles or graph nodes. Exec-hosted
roles receive their Agent Factory role instructions as a tagged block in the
stdin request rather than as a distinct platform system-channel message.
While delegated work runs, Main continues the Human conversation, preserves
the active session/run state, and connects new input to the existing task; a
redirect is explicit and does not erase prior execution or result state.

This plugin repository stores its distributed Skills below `skills/` and does
not mirror them into a repository-local `.codex/`. A separate project that uses
the plugin stores its own Project Skills below `.codex/skills/` in that project.

Gathered collections remain Original Documents, and Work's exploration results
remain Original or Processed Documents. Gather owns external synchronization;
Document defines all three types. The conceptual ordering does not imply
completeness, maturity, a required transition, or automatic promotion;
Original is source-faithful evidence and is authority-neutral: its type alone
does not decide authority or trust. Processed remains non-authoritative working
knowledge. No mandatory
Original-to-Processed-to-Specification pipeline exists. Operational Agent sessions
and temporary exploration workspaces remain operational, while Original,
Processed, and Human-facing Specifications occupy distinct logical roles.
AI-facing Specifications remain in Skills. Tool manages connector lifecycle
semantics without storing credentials or taking over Gather's source-selection,
destination, sync, or provenance contract. Agent retains capability binding,
execution authority, and receipts. Refined is not a fourth active
Document type.

Each plugin skill keeps its entry contract in `SKILL.md`, UI metadata in
`agents/openai.yaml`, and detailed capability guidance in `references/`.
Executable managers, schemas, assets, and tests remain inside the owning skill
when that domain needs them.

## Project-local Agent Factory data

Agent Factory uses this project-local structure as its current/default adapter:

```text
.agent-factory/
├── db.sqlite
├── agent/
│   └── <agent-id>/
│       ├── session.json
│       └── runs/<run-id>/
├── document/
│   ├── original/
│   ├── processed/
│   ├── specification/
│   │   └── human/
│   └── sync.json
└── workspace/
│   ├── common/
│   ├── explorer/
│   └── skills/
```

The exact `.agent-factory/db.sqlite` path is reserved for a rebuildable,
non-authoritative catalog/read model across Agent execution structure and
Documents. Workspace maintains its schema at
`skills/workspace/assets/schema/catalog.sql`. The current implementation is
schema-only: it does not create or populate a database or implement UI, APIs,
search, scanners, rebuild jobs, or runtime dual writes. Do not commit the
database or its SQLite runtime sidecars.

`agent/` contains managed Codex session and run state.
Temporary execution-only Explorer material stays in the producing managed Agent
run. Durable Explorer evidence is classified as an Original or Processed
Document. `document/` contains
the local roots for Original, Processed, and Specification Documents; locally
materialized Human-facing Specifications
live below `document/specification/human/`, and preserved legacy Inquery material
lives below `document/processed/legacy-inquery/`. Gather configuration is
`document/sync.json`.
`workspace/` contains the shared browser shell and control-tower UI: `common/`
is the shared shell, `.agent-factory/workspace/explorer/` owns an internal
read-only File/Project metadata projection, and `skills/` owns internal
read-only Skill navigation. These stores define neither an Activity nor nesting
under one of the five Activities. The Explorer projection distinguishes the
project tree from classified Document trees without copying or becoming the
canonical owner of either; temporary Explorer material remains in its producing
managed Agent run.
Workspace reads Human-facing Specifications from the Document tree. The
Agent Factory core Specification is paired with `skills/convention/`; consumer
project Specifications pair with Project Skills below that project's
`.codex/skills/`.

The information roots are logical roles. A project may explicitly resolve them
to a project server or other external backend without weakening provenance,
authority, isolation, semantic alignment, accessibility, or security. Agent
Factory does not silently select a backend or claim a remote implementation.
`sync.json` contains Gather destination configuration, and gathered source
collections remain at their resolved destinations outside `.agent-factory/`.
Tool has no `.agent-factory/tool/` directory: its registry/state backend and
concrete provider adapters remain unresolved. Hosts, plugins, MCP servers, and
project manifests remain authoritative, and credentials or tokens never belong
in the repository or Specification. Tool also does not add a sixth Workspace
Activity; the Activity Bar contract remains exactly five items.

## Local installation

Install the GitHub-backed marketplace and the plugin with Codex CLI:

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin add agent-factory@agent-factory
```

To pick up a published update:

```bash
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

The plugin manifest is located at `.codex-plugin/plugin.json`, and reusable
workflows are under `skills/`.

After installing or updating the plugin, start a new Codex thread so newly
loaded skills and tools are available.

Convention bundles `assets/AGENTS.md` and a copy-once project bootstrap:

```bash
python3 <installed-convention-skill>/scripts/init_agents.py \
  --project-root <project-root>
```

The bootstrap refuses to overwrite any existing project-root `AGENTS.md`.
This setup is plugin-provided because the plugin manifest does not inject
project files.

## Local Workspace control tower

Resolve the installed Workspace Skill directory, then install the reusable
Workspace browser shell and project launcher for the target Git root:

```bash
python3 <installed-workspace-skill>/scripts/serve.py \
  --project-root <project-root> init
```

Initialization copies the packaged `skills/workspace/assets/workspace.sh`
project template to `<project-root>/workspace.sh` once; it is an asset rather than a
Skill script to run in place. An existing root launcher is never changed, even
by `init --force`; force is limited to differing common browser assets. For
the browser shell, `index.html`, `styles.css`, and `app.js` are the three core
browser-code files. The packaged `THIRD_PARTY_NOTICES.txt` is a companion
attribution and license asset, not a fourth browser-code file; initialization
installs it with the core files, and packaged and materialized copies remain
byte-identical. For normal use, serve the existing Workspace tree on loopback and open
`/common/` in the default browser:

```bash
<project-root>/workspace.sh
# or, from the project root
./workspace.sh --port 9000
```

The self-contained launcher derives the project root from its own location and
serves only the allowlisted local UI root plus
`.agent-factory/document/specification/human/`, so
`<project-root>/workspace.sh` works from any current directory. `--port <port>` or
`-p <port>` overrides the safe default port `8000`. `serve.py` remains the
internal initializer and advanced safe server; its global `--project-root`
option can target another Git root before the `init` or `serve` subcommand.

## Development

Validate the plugin structure with the bundled Plugin Creator validator:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" .
```

Run no test, smoke, lint, typecheck, build, or other verification command unless
the Human explicitly requests testing or verification. Main preserves that
authorization and dispatches a separate managed Verification Agent. When the
Human supplies a command, Verification runs it unchanged; otherwise it selects
only the smallest bounded command justified by repository evidence. Main and
Work never execute the check. A general request to fix or complete work is not
test authority. Without authorization, report that tests were not run.

## Status

Alpha. Feedback and issue reports are welcome, but production compatibility is
not guaranteed yet.

## License

MIT License. See [LICENSE](LICENSE).
