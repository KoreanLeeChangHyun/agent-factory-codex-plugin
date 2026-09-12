# Agent Factory Core Model

## Identity and ownership

- **Public Skills:** exactly `agent` and `convention`. Explorer/Interview are
  Convention capabilities applied by Agent roles, not extra Skills/nodes.
- **MCP domains:** Document, Gather, Tool and Workspace. Use authenticated
  schemas/guides for domain operations; keep plugin instructions in owning Skills.
- **Publication:** Git owns AI Skill authoring; MCP owns connected Document
  publication and accepted cloud revisions. Keep source, installed and revision locators distinct.
- **Documents:** follow the [Document contract](documents.md) for types, authority,
  placement, formats, Specification projections and synchronization.

### Project Skills

- Project Skill identity, categories and representations follow
  [Documents](documents.md#specification-naming). This plugin's `agent` and
  `convention` identities remain explicit Provider exceptions.

## Documents

### Types and relationships

- Original, Processed and Specification are the only storage-independent types;
  follow [Documents](documents.md#types-and-authority) for their definitions and
  authority. Specification subtypes add no top-level type. Refined is not a fourth type.
- `Original -> Processed -> Specification` indicates optional evidence/derivation,
  never a pipeline, state machine, maturity scale, required transition, completion
  or promotion. Relationships may be absent or any cardinality; record actual provenance.

### Storage and migration

- Three product modes are valid: plugin-only is a complete local Agent workflow;
  MCP-only owns its capabilities independently; plugin plus MCP adds only explicitly
  selected, authorized connected capabilities without transferring graph authority.
- The resolved MCP application owns its domain implementations and connected state.
  Local exec/loop retains session/run/graph authority; run/outbox/recovery stays
  local. Consult current authenticated MCP guides and schemas for domain operations.
- Inspect locally with shell/file tools; route generated documents through
  [Document routing](documents.md#routing). MCP
  absence is normal in plugin-only mode; never infer accounts or create a substitute
  local MCP/provider service.
- Follow [directory-structure.md](directory-structure.md#legacy-migration) for
  legacy retention and retirement. Retire local domain executables only after
  verified replacement.
- Classification/transformation/reconciliation/acceptance remain separate from
  physical storage or migration. Preserve `documentType`, identity, provenance,
  authority and recorded relationships.
- LLM output may advise/author, never execute. Deterministic managers require a
  closed, versioned, allowlisted plan/IR and revalidated state/Human authority.
- Fail closed on stale plans, path escape, symlinks, conflicts, unsupported operations,
  promotion, unauthorized destruction or integrity mismatch. Selected connected
  publication uses its current MCP schemas.

## Capabilities

- **Gather:** local files and host-provided tools may gather bounded sources into
  Original Documents. Connected collection is optional; preserve fidelity, identity,
  provenance, destination and read-only intent.
- **Tool:** logical discovery/lifecycle, connection, scope, health and metadata;
  host/plugin/MCP/project/provider remains authoritative. No secrets or execution grants.
- **Explorer:** Work's bounded evidence exploration; may produce Original/Processed,
  never interview Humans or accept Specification truth.
- **Interview:** Main's adaptive elicitation; Processed by default, no authority/acceptance grant.
- **Document:** operations on resolved Document targets.
- **Convention:** core model and cross-cutting rules.
- **Agent:** graph, capability bindings, local runtime facts, transitions and receipts.
- **Workspace:** Human control tower projecting owner-backed state.

### External capability authority

- A capability request does not grant provider, account, credential, connection,
  scope or mutation authority. Use the current authenticated MCP contract and
  preserve the owning Human, administrator, host and provider boundaries.

## Agent graph

- Follow [the Agent Skill](../../agent/SKILL.md#roles-and-graph) for role boundaries,
  Main orchestration, failure routing, and Human-skip timing/evidence through END.
- Follow [Development](development.md#git-publication) for authorized Git publication.

### Engineering scopes

1. **Prompt:** one model interaction.
2. **Context:** bounded evidence and tool context.
3. **Loop:** iteration, feedback, stopping and recovery.
4. **Agent Graph:** Humans, Agents, tasks, tools, state and evidence.
5. **Agentic:** lifecycle, safety, evaluation, observability and governance.

## MCP application boundary

- An MCP application is independently usable without this plugin. Conversely, the
  plugin's local graph and document workflow require no MCP installation or connection.
- Document, Gather, Tool and Workspace implementation details belong to the
  resolved MCP application. Use its advertised authenticated resources and tool
  schemas; do not restate its UI, backend, dependency or operation contracts here.
- Reporting evidence and its separation from local graph completion follow
  [Agent reporting](../../agent/references/home-runtime.md#optional-cloud-reporting).
- Integration requires an available connection, explicit selection and applicable
  Human authority. Availability alone never uploads local documents or reports.

## Decisions and maintenance

### Unresolved authority

- Contract/source availability proves no registration, live accounts, deployment
  or completed migration.
- Apply [explicit-human-input.md](explicit-human-input.md) to Human-owned priority,
  deadlines, owners, acceptance, completion and risk acceptance.
- Tenant/account/credential authority, live connections, cutover/retention/deletion
  and conflict decisions require their owning evidence or Human decision.
- Check Skill metadata, routes, owned runtime behavior and authority boundaries;
  keep MCP domain details in their authenticated resources.
