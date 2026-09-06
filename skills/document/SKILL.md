---
name: document
description: Define, create, edit, inspect, or maintain Agent Factory Original, Processed, and Specification Documents while preserving loose provenance relationships and type-specific authority.
metadata:
  specification-id: document
  human-entry: docs/specifications/document/index.html
  ai-root: skills/document/
---

# Agent Factory Document

## Entry contract

Define, author, inspect and maintain exactly three logical Document types: Original (원본 문서), source-faithful evidence; Processed (가공 문서), transformed non-authoritative working knowledge; Specification (명세 문서), accepted and reconciled knowledge with one faithful Korean Human browser representation and one AI Skill under one stable identity. Never introduce a fourth type or retired role.

`Original -> Processed -> Specification` expresses possible evidence/derivation only, not a required pipeline, promotion, maturity, completeness or one-to-one mapping. Relationships may be absent or many-to-many. Preserve inspectable provenance for actual relationships. Human-owned priority, dates, owner, acceptance, completion and risk acceptance require explicit decisions.

## Reference routing

Read each applicable reference completely:

- `references/original.md`: source fidelity, identity and collection context.
- `references/processed.md`: transformation, browser representation and non-authority.
- `references/specification.md`: complete Korean/AI pair, source inventory, identity and publication.
- `references/adapter.md`: cloud persistence, import, search, delivery, physical migration and recovery.

## Ownership and execution

The selected authenticated cloud MCP application owns new Document persistence, revision publication, indexing/search and document configuration. Read its advertised schemas and guides before using `document_import`, `document_read`, `document_write`, `document_search`, `document_index`, `document_prepare_upload` or `document_finalize_upload`. Resolve the actual authorized tenant and target; missing tools, connection or rights fail honestly without a local-backend fallback. Development implementation guides at `../mcp/docs/cloud-documents.md` are source-checkout locators, not installation requirements.

Gather owns external selection and collection through cloud integrations; Document owns work on resolved Document targets. Explorer is a Convention-owned Work capability and may produce Original or Processed evidence without accepting Specification truth. Tool resolves capability/connection lifecycle; Agent owns execution authority, local sessions, graph and receipts. Workspace presents owner-backed state and never becomes an independent Document store.

## Publication source and completion

Git owns distributable Skill authoring source. This plugin keeps its six stable pairs at `skills/<id>/` and `docs/specifications/<id>/`; the version-controlled Korean HTML is publication source. These package-relative reciprocal locators are not consumer runtime paths or an independently editable second cloud truth. A published snapshot binds the Git repository, exact commit, content inventory and both representation hashes; cloud owns the accepted immutable published revision.

Keep exactly one AI Skill and one Korean HTML/CSS/JavaScript representation per identity. Translate the complete AI instruction inventory in source order and hierarchy with exact source/line hashes. Hash coverage cannot prove meaning; obtain independent semantic review and preserve its authority evidence. A one-sided, partial, stale, reordered, duplicated, summarized or mistranslated pair is incomplete and must not be reported completed.

Local execution-only evidence, run records, outbox and recovery remain local. Upload required durable evidence through authorized cloud Document tools. Preserve legacy local Documents, `db.sqlite` and sync configuration until inventoried, backed up and independently verified imported; code retirement grants no data-deletion permission. This contract does not claim registration, configured accounts, deployment or full migration completion.
