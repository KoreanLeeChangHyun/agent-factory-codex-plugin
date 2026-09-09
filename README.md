# Agent Factory for Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!WARNING]
> This plugin is under active development. Its skills, artifact formats, and
> workflows may change without notice.

Agent Factory is a Codex plugin for Human-directed software delivery. Main is
the Human-facing Interview, orchestration, and integration layer; it routes
bounded tasks, including research and implementation, to Work and independent
checking to Verification unless the Human skips it. The plugin supports
evidence exploration and applies shared project conventions. Document,
Gather, Tool, and Workspace capabilities are provided by the resolved Agent
Factory MCP application rather than by plugin Skills.

## Included skills

The plugin exposes exactly two public skills:

- `agent`: Run the exact `Main -> Work -> Verification` graph through managed
  sessions. Main orchestrates, Work performs the bounded task, and Verification
  independently returns pass or fail unless the Human skips it.
- `convention`: Own and apply the Agent Factory core model plus directory,
  development, library, design, annotation, Document-type, authority, and
  cross-cutting integration conventions.

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
remain Original or Processed Documents. The MCP application owns external
collection and Document operations. The conceptual ordering does not imply
completeness, maturity, a required transition, or automatic promotion;
Original is source-faithful evidence and is authority-neutral: its type alone
does not decide authority or trust. Processed remains non-authoritative working
knowledge. No mandatory
Original-to-Processed-to-Specification pipeline exists. Operational Agent sessions
and temporary exploration workspaces remain operational, while Original,
Processed, and Human-facing Specifications occupy distinct logical roles.
AI-facing Specifications remain in Skills. MCP integration capabilities manage
connections without exposing credentials or taking over external provider
authority. Agent retains capability binding, execution authority, and receipts.
Refined is not a fourth active
Document type.

Each of the two plugin Skills keeps its entry contract in `SKILL.md`, UI metadata in
`agents/openai.yaml`, and detailed capability guidance in `references/`.
New domain implementations, schemas and runtime tests belong to the cloud application. Only local exec/loop and minimum support remain runtime dependencies of the plugin; local domain executables, catalog/sync schemas and provider dependencies are retired.

## Cloud domains and local execution

The Human-selected Agent Factory MCP application owns new Document persistence,
search and publication; connections, authentication and bounded
collection; shared reporting; and the Workspace implementation. Read its
advertised authenticated tool schemas and guides before invoking domain tools.
Missing tools, connection, tenant or scope must be reported honestly. Do not
substitute retained local scripts, create new local domain configuration or add
a local MCP/provider service.

The plugin retains two Skills, the three role prompts, local `exec.py`/`loop.py`
and minimum runtime dependencies. The extension discovers runtime locations through the machine contract. Local sessions, process/run facts, graph transitions,
receipts, reporting outbox and recovery remain under
`~/.agent-factory/projects/<project-id>/agents/<agent-id>/`. Cloud reports never launch, resume, cancel
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

Git maintains Agent instructions under `skills/<id>/`. Human-facing Document
publication belongs to the MCP application and follows its current authenticated
schema while preserving actual provenance.

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

## Workspace control tower

The Workspace domain belongs to the separate `agent-factory-mcp` application,
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

Install test dependencies with `python3 -m pip install -r requirements.txt`.

Tests are grouped by purpose: `tests/contracts/` for package and reference
contracts, `tests/runtime/` for runtime behavior, and `tests/integration/` for
installation and cross-component scenarios. Keep test filenames as
`test_<name>.py`; shared helpers belong in `tests/support/` and standalone
performance tools in `tests/benchmarks/`. Run the relevant files with pytest
from the repository root; `pytest.ini` provides the shared import paths.

```bash
python3 -m pytest tests/contracts/test_convention_skill_metadata.py tests/integration/test_distribution.py
```

These checks cover Skill metadata, routed references, and isolated installation.

When a full suite is requested, run it in parallel with bounded worker count:

```bash
python3 -m pytest tests -n auto --maxprocesses=4 --dist=worksteal
```

Small focused runs stay serial to avoid worker startup overhead. Use `-n 0`
for serial comparison or diagnosis. Each worker gets a temporary runtime home;
fixtures own their temporary files and dynamically allocated ports. Installed
Codex permission tests remain opt-in with `AF_VERIFY_LOCAL_CODEX=1`.

Native local execution guidance lives in
[`skills/agent/references/native-fast-goal.md`](skills/agent/references/native-fast-goal.md).

Use `skills/agent/scripts/exec.py init --project-root /absolute/project` for explicit setup. `AGENT_FACTORY_HOME` selects an alternate private home without changing Codex home. Installation limits and the gated physical-migration procedure are in [`skills/agent/references/home-runtime.md`](skills/agent/references/home-runtime.md). No physical cutover is implied by the source change.

The project-specialized Work direction and its unresolved design choices live in
[`skills/agent/references/project-specialist.md`](skills/agent/references/project-specialist.md).
