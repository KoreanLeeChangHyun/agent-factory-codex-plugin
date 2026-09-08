---
name: convention
description: Apply Agent Factory's core model and cross-cutting conventions for project structure, development, testing, libraries, design, annotations, Document types, and Skill ownership.
metadata:
  specification-id: convention
---

# Agent Factory Convention

## Entry contract

Apply this Skill to Agent Factory core concepts and cross-cutting project structure, development, testing, libraries, design, annotations, Document types, authority and Skill ownership. Read every applicable reference before acting.

Exactly two public distributed Skills remain: `agent` and `convention`. Document, Gather, Tool, and Workspace are Agent Factory MCP application domains, not plugin Skills. Explorer and Interview are Convention-owned capabilities applied by Agent roles, not extra public Skills or roles. Main orchestrates, Work performs bounded work without self-verification or commit, and Verification independently checks without repair. Only independent pass or evidenced Human skip applied after Work completion reaches END. Main alone integrates an authorized ordinary Git commit for the exact verified/skipped paths; this never grants push, amend, history rewrite or unrelated mutation.

Exactly three storage-independent Document types remain Original, Processed and Specification. Their conceptual ordering expresses possible derivation/evidence only, never a pipeline, maturity scale, required transition, completeness or automatic promotion. Relationships may be absent or any cardinality; preserve actual provenance. Original preserves native/source-appropriate fidelity and identity. Processed is non-authoritative transformed working knowledge, with the accepted portable HTML/CSS/JavaScript package. Legacy Inquery packages remain inactive Processed evidence, not another type or an active format precedent.

Specifications contain accepted project knowledge. AI Skills provide Agent instructions; Korean documents are independently maintained references. The MCP Document domain owns publication and migration.

## Cloud and local ownership

The Human-selected cloud MCP application owns new Document persistence/search/publication, connection/authentication/collection configuration, shared reporting and Workspace implementation. New domain work reads advertised authenticated tool schemas/guides and uses those tools. Missing capability, connection, tenant or scope fails honestly; do not fall back to old local scripts, invent account IDs, or create a local MCP/provider service.

Local `exec.py`, `loop.py`, role prompts and minimum runtime dependencies remain authoritative for local sessions, process/run facts, graph transitions and receipts. Local run, outbox and recovery state remains local. Use existing shell/file tools for bounded local Git/tool inspection and upload required evidence through authorized cloud Document tools. Shared reports never launch or finish local execution. Planning task state remains separate from background jobs and runtime observations.

Git owns distributable Skill authoring source under `skills/<id>/`. This plugin distributes `agent` and `convention`; preserve their names and metadata identities and do not mirror them into this repository's `.codex/`. Consumer Project Skills preserve the Human-resolved `<category>-<title>` name. Distinguish source-package, installed Skill and cloud revision locators; cloud owns its accepted immutable revisions.

Cloud owns new catalog/search and document/sync configuration. Retained `.agent-factory/db.sqlite`, legacy local Documents and sync config are migration inputs until import is independently verified. Local domain executables are retired; reusable Document authoring resources belong to the MCP package. Preserve data until inventoried, independently backed up and verified imported; code retirement is never deletion authority. Do not claim registration, configured accounts, deployment or full migration completion from a contract change.

The MCP application owns the Document, Gather, Tool, and Workspace domain guides, schemas, live state, and operations. Workspace remains the Human control tower with exactly six ordered Activities: 일정, 에이전트, 문서, 외부연동, 로그, 테스트. Actual hosts and providers retain their authority, cloud credential storage remains separate, readiness grants no Agent execution authority, and no integration may widen scope automatically. Do not copy the MCP Workspace runtime or domain state into consumer projects.

## Reference routing

- `references/agent-factory-core.md`: core roles, authority, Documents, engineering layers and accepted decisions.
- `references/directory-structure.md`: source, installed, local runtime and cloud ownership paths.
- `references/development.md`: bounded changes and Main-owned Git publication.
- `references/testing.md`: focused test scope and independent Verification.
- `references/explicit-human-input.md`: required missing Human decisions and role boundaries.
- `references/libraries.md`: dependency selection and renderer boundaries.
- `references/design.md`: Human interface and document design.
- `references/annotation.md`: comments, documentation and traceable TODOs.
- `references/svg-icon.md`: actual SVG icons.
- `references/diagrams.md`: source-backed ERD, behavior and sequence diagrams; its nested references are routed there.
- `references/explorer.md`: bounded evidence exploration and provenance.
- `references/interview.md`: Main's adaptive Human elicitation.

## Bootstrap source

`assets/AGENTS.md` remains the project instruction template. Use existing file tools for authorized copy-once installation into an absent project `AGENTS.md`; preserve an existing file. The local initialization manager is retired. The plugin manifest does not itself inject project files.
