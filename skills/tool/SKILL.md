---
name: tool
description: Discover and manage the lifecycle of Agent-usable external tools and connectors without taking over their authoritative host, plugin, MCP, project manifest, credentials, or execution authority.
metadata:
  specification-id: tool
  human-entry: .agent-factory/document/specification/tool/index.html
  ai-root: skills/tool/
---

# Agent Factory Tool

## Entry contract

Use this Skill when the Human or an Agent needs one control contract for
Agent-usable external tools and connectors such as Playwright, pytest, Office,
Google Drive, or OneDrive. Tool owns logical discovery and catalog metadata,
install/update/remove routing, connection and authentication lifecycle,
credential references, requested and granted permission scopes,
availability and health, enable/disable state, and capability metadata.

Tool does not make itself the authoritative package manager, plugin manager,
MCP registry, project dependency manifest, credential store, or execution
runtime. Resolve and preserve the actual authority for each integration: its
host, plugin, MCP server, project manifest, or other explicitly selected
provider. Never claim an installation, connection, health check, registry, or
state backend that has not been implemented and inspected.

Credentials and tokens are never Tool metadata. Record only an opaque
credential reference suitable for the owning provider, and never write secret
material into a repository, Specification, receipt, or catalog. Do not invent
`.agent-factory/tool/` or select a Tool registry/state backend implicitly.

Agent owns Work/Verification capability binding, execution authority, and
execution receipts. Convention owns cross-cutting safety, least privilege, and
approval rules. Workspace may project Tool state or route an authorized
control, but it does not own Tool lifecycle state and Tool does not add a
Workspace Activity.

Gather remains the owner of source selection, destination, bounded read-only
synchronization, fidelity, identity, provenance, and Original Document output.
For a connector-backed sync, Gather declares the needed capability, minimum
scope, whether Human approval is required, and selection bounds; Tool resolves
or prepares a matching connection and reports the actually granted scope.
Tool must not widen scope on its own.

## Reference routing

- `references/lifecycle.md`: Read before designing, changing, or operating a
  Tool catalog entry, installation, connection, permission, health, or
  enablement lifecycle, and when integrating Tool with Gather or Agent.
- `references/git.md`: Read for discovery, install, update, remove, connection,
  authentication, or health requests involving Git, GitHub CLI (`gh`), or Git
  LFS, and before binding one of their capabilities to Agent execution.
- `references/playwright.md`: Read for discovery, install, update, removal,
  browser/runtime readiness, or health requests involving Playwright, and
  before binding its browser capability to Agent execution.

## Stateless adapter

`scripts/tool.py` is the current bounded implementation for the Git, GitHub
CLI, Git LFS, and Playwright profiles. It emits one JSON document for
`discover`, `inspect`, or `health`, and emits a non-executing provider route for
state-changing lifecycle verbs. It never installs, updates, removes, connects,
authenticates, enables, disables, runs a domain task, creates a Tool registry,
or stores credentials.

Every invocation requires one stable profile and preserves an explicit
authority kind/reference plus exact project target. Native executable and
project-CLI adapters may inspect only bounded provider-reported facts. Plugin,
MCP, and host capabilities remain `unknown` until their selected authority has
a concrete adapter; their availability is never inferred from a project
package. Machine output separates observed facts from the lifecycle route and
records `secretMaterialStored: false`.

GitHub CLI executable availability and authentication are independent facts.
The adapter uses the provider-supported non-secret command `gh auth status
--hostname HOST --json hosts` and bounds its hosts/account projection.
Structured authentication inspection reports `inspectionSupport` separately:
unsupported or unparseable behavior leaves authentication `unknown`,
while a supported structured response can report actual unauthenticated state
as `unavailable`. The adapter never treats an older or unsupported CLI
interface as proof that authentication is unavailable.
