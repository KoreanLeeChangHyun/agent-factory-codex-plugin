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

## Cloud connections and local inspection

New provider connection/authentication work uses advertised tools on the resolved authenticated cloud MCP application. Read `agent-factory://integrations/guide`, current schemas and `references/lifecycle.md`. Cloud owns encrypted connection credentials and integration configuration; Tool keeps logical control semantics and opaque references. Missing capability, permission, account or connection remains unresolved/unavailable. Never fabricate live health or substitute a legacy provider script.

For local Git, GitHub CLI, Git LFS and Playwright inspection, use the Agent's existing shell/file tools against an explicit target and the selected authority. Follow the profile references for bounded non-secret facts. Do not create a local Tool MCP/provider service. The local Tool adapter executable is retired after independently verified replacement; this grants no permission to delete user data.
