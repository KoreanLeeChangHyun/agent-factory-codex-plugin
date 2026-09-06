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
- `document`: Define and maintain Original (원본 문서), Processed (가공 문서),
  and Specification (명세 문서) Documents. The conceptual ordering
  `Original -> Processed -> Specification` expresses only possible derivation
  or evidence relationships; relationships may be absent, one-to-many,
  many-to-one, or many-to-many. A Specification is accepted and reconciled
  project knowledge and uses paired Korean
  Human-readable HTML/CSS/JavaScript and AI-readable Skill views. Consumer Project Skill/Specification pairs preserve the exact lowercase hyphen-case identity `<category>-<title>` in Skill name and reciprocal publication metadata; installed and cloud locators are resolved separately. This plugin's six accepted single-name distributed pairs are the
  explicit exception.
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
New domain implementations, schemas and runtime tests belong to the cloud application. Only local exec/loop and minimum support remain runtime dependencies of the plugin; local domain executables, catalog/sync schemas and provider dependencies are retired.

## Cloud domains and local execution

The Human-selected Agent Factory MCP application owns new Document persistence,
search and complete-pair publication; connections, authentication and bounded
collection; shared reporting; and the Workspace implementation. Read its
advertised authenticated tool schemas and guides before invoking domain tools.
Missing tools, connection, tenant or scope must be reported honestly. Do not
substitute retained local scripts, create new local domain configuration or add
a local MCP/provider service.

The plugin retains six Skills, the three role prompts, local `exec.py`/`loop.py`
and minimum runtime dependencies. Existing extension command paths and layouts
remain compatible. Local sessions, process/run facts, graph transitions,
receipts, reporting outbox and recovery remain under
`.agent-factory/agent/<agent-id>/`. Cloud reports never launch, resume, cancel
or finish local runs; process exit and stale reporting do not imply semantic
completion or graph END. Use existing shell/file tools for bounded local Git
and tool inspection, and authorized Document tools to upload required evidence.

Document tools include `document_import`, `document_read`, `document_write`,
`document_search`, `document_index`, `document_prepare_upload` and
`document_finalize_upload`; package members and isolated Human previews use
revision-scoped authenticated delivery routes. Connections and bounded Gather
collections follow `agent-factory://integrations/guide`; shared reporting uses
`reporting_read`, `reporting_write`, `reporting_search` and
`agent-factory://reporting/cloud-guide`. Development planning follows the
Workspace planning contract and `agent-factory://planning/import-guide`,
separately from background jobs and runtime reporting.

Git owns distributable Skill authoring. This plugin's `skills/<id>/` and
`.agent-factory/document/specification/<id>/` are reciprocal publication-source
packages. The Korean HTML is version-controlled publication source, not a
consumer local backend or a second independently editable cloud truth. Exactly
one complete Korean Human representation pairs with exactly one AI Skill under
the same stable identity. Preserve complete source-order translation and source
hash coverage; publish a reviewed snapshot bound to Git repository, exact
commit, full content inventory and both representation hashes. Cloud owns its
accepted immutable published revision. Source-package, installed Skill and
cloud revision locators are distinct and must be resolved explicitly.

New catalog/search and document/sync configuration are cloud-owned. Retained
local `db.sqlite`, old Document roots, `document/sync.json` and gathered collections
are migration inputs until import is independently verified. Preserve source data until inventoried, independently
backed up and verified imported. Code retirement never authorizes deletion of
Human data, source, credentials or backups. Actual tenant/account IDs and
credential authority are never silently selected. Contract/source availability
does not establish registration, configured accounts, deployment or
completion of the active migration steps 1–13.

Managed Agent runs accept a strict binding file on `exec.py submit`/`send`.
The graph launcher accepts separate role-scoped binding files on `loop.py
start`:

```json
{
  "schemaVersion": "0.1.0",
  "bindings": [{
    "capabilityId": "playwright.browser.execute",
    "authority": {"kind": "project-cli", "reference": "package-lock.json#playwright"},
    "invocationRoute": "node_modules/.bin/playwright",
    "exactTarget": "https://example.invalid/health",
    "allowedEffects": ["navigate"],
    "allowedScopes": ["network:https://example.invalid"],
    "approvalReference": "human-request-1"
  }]
}
```

Pass it with `exec.py --capability-binding-file <path>`, or use
`loop.py start --work-capability-binding-file <path>` and/or
`--verification-capability-binding-file <path>`. A loop never forwards one
role's binding to the other. The runtime validates and
copies the canonical document into the managed run, binds its hash into the
dispatch tuple, and requires one exact `capabilityOutcomes` receipt entry per
binding. Binding and receipt fields contain no credentials or tokens.

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

Convention retains `assets/AGENTS.md` as a copy-once project instruction template.
Use existing file tools only for an authorized absent target; preserve any
existing project `AGENTS.md`. The bootstrap manager and local domain scripts are retired. New Specification
authoring uses the authenticated MCP `document_template` manifest and bounded
version-bound member delivery, preserving all template bytes and licenses.
The six existing Human packages retain their standalone representation assets.

## Workspace control tower

The Workspace Skill and Human Specification remain in this plugin. The
executable Workspace has moved to the separate `agent-factory-mcp` application,
which owns the FastAPI host, `/mcp` transport, discovery API, canonical browser
assets, deployment adapters, and runtime tests. Resolve the authenticated organization/Workspace in that application and open its `/workspace/` route. No browser-shell copy
or root `workspace.sh` is installed into consumer projects.

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

Development checks for final pairs use the owning `agent-factory-mcp` Python
package, not a plugin validator copy. Independent Verification can use the MCP
development environment and run `python -m pytest ../plugin/tests` from the MCP
checkout, with `AGENT_FACTORY_MCP_SOURCE` set to that checkout when it is not the
usual sibling. An installed MCP development dependency also works. Missing
required dependencies fail explicitly. The distribution and test migration map
is maintained in [cloud-retirement.md](docs/cloud-retirement.md).

Native local execution: [Fast and Goal runtime guide](docs/native-fast-goal.md)
explains installed-backend detection, exact-session settings, Goal lifecycle,
and recovery limits.
