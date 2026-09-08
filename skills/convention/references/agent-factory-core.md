# Agent Factory Core Model

## Identity and ownership

- **Public Skills:** exactly `agent` and `convention`. Explorer/Interview are
  Convention capabilities applied by Agent roles, not extra Skills/nodes.
- **MCP domains:** Document, Gather, Tool and Workspace. Use authenticated
  schemas/guides for domain operations; keep plugin instructions in owning Skills.
- **Publication:** Git owns AI Skill authoring; MCP owns connected Document
  publication and accepted cloud revisions. Keep source, installed and revision locators distinct.
- **Generated documents:** follow [MCP/docs routing](directory-structure.md#ai-generated-documents).

### Project Skill naming

- Use the Human-resolved lowercase `<category>-<title>` identity; do not infer
  components or bulk-rename accepted identities. This plugin's single names are
  the explicit exception.
- Installation and historical source locations follow
  [directory-structure.md](directory-structure.md). Preserve identity and provenance.

## Documents

### Types and relationships

- **Original / 원본 문서:** source-faithful evidence in native/appropriate form.
- **Processed / 가공 문서:** transformed, non-authoritative working knowledge.
- **Specification / 명세 문서:** accepted, reconciled project knowledge.
- These are the only storage-independent types; Refined is not a fourth type.
- `Original -> Processed -> Specification` indicates optional evidence/derivation,
  never a pipeline, state machine, maturity scale, required transition, completion
  or promotion. Relationships may be absent or any cardinality; record actual provenance.
- Active Processed and Human Specifications share `index.html`, `styles.css`,
  `app.js`; shared format grants no shared authority. `legacy-inquery-*` remains
  inactive Processed evidence.

### Storage and migration

- Cloud owns connected persistence/search/publication, connection/authentication,
  collections, reporting and Workspace. Local exec/loop retains session/run/graph
  authority; run/outbox/recovery stays local.
- Inspect locally with shell/file tools; route generated documents through
  [MCP/docs storage](directory-structure.md#ai-generated-documents).
  Report missing capabilities/tenant/scope; never infer accounts or create a
  substitute local MCP/provider service.
- Follow [directory-structure.md](directory-structure.md#legacy-migration) for
  legacy retention and retirement. Retire local domain executables only after
  verified replacement.
- MCP Document owns adapter initialization and physical migration, separately from
  classification/transformation/reconciliation/acceptance. Preserve `documentType`,
  identity, provenance, authority and recorded relationships.
- LLM output may advise/author, never execute. Deterministic managers require a
  closed, versioned, allowlisted plan/IR and revalidated state/Human authority.
- Fail closed on stale plans, path escape, symlinks, conflicts, unsupported operations,
  promotion, unauthorized destruction or integrity mismatch. Publish via current MCP schemas.

## Capabilities

- **Gather:** synchronize bounded sources into Original Documents; preserve fidelity,
  identity, provenance, destination and read-only intent.
- **Tool:** logical discovery/lifecycle, connection, scope, health and metadata;
  host/plugin/MCP/project/provider remains authoritative. No secrets or execution grants.
- **Explorer:** Work's bounded evidence exploration; may produce Original/Processed,
  never interview Humans or accept Specification truth.
- **Interview:** Main's adaptive elicitation; Processed by default, no authority/acceptance grant.
- **Document:** operations on resolved Document targets.
- **Convention:** core model and cross-cutting rules.
- **Agent:** graph, capability bindings, local runtime facts, transitions and receipts.
- **Workspace:** Human control tower projecting owner-backed state.

### Connector requests

- Declare capability, exact source bound, resolved destination, minimum scope and
  required Human/administrator approval. Report actual connection/granted scope;
  never escalate automatically.
- Retire provider executables; legacy tokens stay with credential authority.
  Provider storage boundaries follow [directory-structure.md](directory-structure.md#cloud-domains).

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

## Catalog and Workspace

- Catalog storage follows [directory-structure.md](directory-structure.md#cloud-domains).
  Reporting evidence and its separation from local graph completion follow
  [Agent reporting](../../agent/references/home-runtime.md#optional-cloud-reporting).
- MCP owns FastAPI runtime, transport/discovery, deployment, tests and canonical
  `static/workspace/` assets. Consumer projects receive no Document backend,
  Workspace copy or root launcher.

### Accepted navigation

- **Layout:** 작업 표시줄 → 기본 사이드바 → 작업 영역.
- **Activities, ordered:** 일정, 에이전트, 문서, 외부연동, 로그, 테스트.
- **External groups, ordered:** 웹·리서치, 문서·파일, 메일·메시지, 일정·회의,
  지식·업무관리, 개발·운영, 데이터·비즈니스.
- **Document labels:** 원본 문서, 가공 문서, 명세 문서; no renaming of logical
  types, IDs, metadata or paths.
- Read current authenticated MCP guides for detailed IA, browser behavior,
  publication/security, 작업 terminology and planning import. Cloud dependency
  policy owns browser library selection.

## Decisions and maintenance

### Unresolved authority

- Contract/source availability proves no registration, live accounts, deployment
  or completed migration.
- Apply [explicit-human-input.md](explicit-human-input.md) to Human-owned priority,
  deadlines, owners, acceptance, completion and risk acceptance.
- Tenant/account/credential authority, live connections, cutover/retention/deletion
  and conflict decisions require their owning evidence or Human decision.
- Unresolved Agent/log/test sidebars, overview, external navigation, Original
  source/query behavior, mutation authority and Activity details remain unresolved
  unless current authenticated guidance or later Human decisions settle them.
- Check Skill metadata, routes, owned runtime behavior and authority boundaries;
  keep MCP domain details in their authenticated resources.
