# Agent Factory for Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for Human-directed software delivery. Main is
the Human-facing Interview, orchestration, and integration layer; it routes
research to Explorer, bounded implementation to Work and independent Review,
and Human-authorized checks to Verification. The plugin supports resumable evidence exploration, maintains refined project
Specifications, and gathers distributed source material without promoting it
to trusted truth.

## Included skills

The plugin exposes exactly six public skills:

- `agent`: Use Main for Human conversation, adaptive Interview, orchestration,
  and result integration, and run Work, Review, Explorer, and Verification Exec
  Agents through the managed session runtime. Main performs no executable task
  work itself.
- `convention`: Own and apply the Agent Factory core model, three-stage
  information lifecycle, Skill ownership and naming, storage-independent
  document rules, annotations, and SVG-only user-interface conventions.
- `explorer`: Explore evidence across web, code, documents, and supplied
  material in a resumable workspace. Explorer may preserve original information
  and produce processed information but never accepts refined project truth.
- `interview`: Reduce material AI-Human information gaps through an adaptive,
  Human-facing Main Agent conversation that produces processed information
  without independently promoting it to refined project truth.
- `specification`: Maintain one refined body of trusted project knowledge with
  paired Korean Human-readable HTML/CSS/JavaScript Specifications and
  AI-readable Skill views. Project Skills use the lowercase hyphen-case name
  `<category>-<name>`; their directory and `SKILL.md` frontmatter
  `name` match exactly, and they live below `.codex/skills/` in the owning
  project.
- `gather`: Locate, import, refresh, or mirror distributed sources while
  preserving fidelity, provenance, identity, and resolved destinations.

This plugin repository stores its distributed Skills below `skills/` and does
not mirror them into a repository-local `.codex/`. A separate project that uses
the plugin stores its own Project Skills below `.codex/skills/` in that project.

Gathered collections remain original-information evidence, and Work's
exploration results remain original or processed information. Neither Gather
nor evidence exploration reconciles or promotes its output into trusted project
truth; Specification alone reconciles accepted inputs into refined project
knowledge. Operational Agent sessions and temporary exploration workspaces
remain operational, while original, processed, and Human refined documents
occupy distinct information lifecycle roles. AI-facing refined knowledge
remains in Skills.

Each plugin skill keeps its entry contract in `SKILL.md`, UI metadata in
`agents/openai.yaml`, and detailed capability guidance in `references/`.
Executable managers, schemas, assets, and tests remain inside the owning skill
when that domain needs them.

## Project-local Agent Factory data

Agent Factory uses this project-local structure as its current/default adapter:

```text
.agent-factory/
├── agent/
│   └── <agent-id>/
│       ├── session.json
│       └── runs/<run-id>/
├── explorer/<exploration-id>/
├── information/
│   ├── original/
│   ├── processed/
│   └── refined/
│       └── human/
├── specification/
│   ├── common/
│   ├── explorer/
│   └── skills/
└── sync.json
```

`agent/` contains managed Codex session and run state. `explorer/` contains
temporary evidence-exploration workspaces used by Work. `information/` contains original,
processed, and refined documents; locally materialized Human refined documents
live below `information/refined/human/`, and preserved legacy Inquery material
lives below `information/processed/legacy-inquery/`. `specification/` contains
the shared browser shell and Activity-owned UI: `common/` is the shared shell,
`explorer/` owns the project tree, and `skills/` owns Skill navigation.
Planning reads Human refined documents from the information tree. The Agent
Factory core Human document is paired with `skills/convention/`; consumer
project documents pair with Project Skills below that project's `.codex/skills/`.

The information roots are logical roles. A project may explicitly resolve them
to a project server or other external backend without weakening provenance,
authority, isolation, semantic alignment, accessibility, or security. Agent
Factory does not silently select a backend or claim a remote implementation.
`sync.json` contains Gather destination configuration, and gathered source
collections remain at their resolved destinations outside `.agent-factory/`.

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

## Local Specification browser

Resolve the installed Specification Skill directory, then install the reusable
Specification browser shell and project launcher for the target Git root:

```bash
python3 <installed-specification-skill>/scripts/serve.py \
  --project-root <project-root> init
```

Initialization copies the packaged `skills/specification/assets/spec.sh`
project template to `<project-root>/spec.sh` once; it is an asset rather than a
Skill script to run in place. An existing root launcher is never changed, even
by `init --force`; force is limited to differing common browser assets. For
normal use, serve the existing Specification tree on loopback and open
`/common/` in the default browser:

```bash
<project-root>/spec.sh
# or, from the project root
./spec.sh --port 9000
```

The self-contained launcher derives the project root from its own location and
serves only the allowlisted local UI root plus
`.agent-factory/information/refined/human/`, so
`<project-root>/spec.sh` works from any current directory. `--port <port>` or
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
