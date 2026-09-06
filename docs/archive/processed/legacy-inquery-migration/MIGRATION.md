# Legacy Inquery migration

The preserved contents were moved without semantic promotion through these
physical layouts:

1. `.agent-factory/inquery/<legacy-id>/`;
2. `.agent-factory/information/processed/legacy-inquery/<legacy-id>/`;
3. `.agent-factory/document/processed/legacy-inquery/<legacy-id>/`;
4. `.agent-factory/document/processed/legacy-inquery-<legacy-id>/` (current).

The first migration was authorized by the Work request at
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T185448822401Z-ef49909a/request.md`.
The move into `document/processed/` was authorized by
`.agent-factory/agent/document-root-migration-work/runs/run-20260830T085419496276Z-66baeaeb/request.md`.
The Human's 2026-08-31 flat-layout decision removed the legacy wrapper and
assigned explicit `legacy-inquery-<legacy-id>` package identities.

They remain processed historical evidence with their original internal
provenance. `legacy` is status/provenance metadata, not a fourth Document type.
Immutable historical Agent run records and historical content references were
not rewritten. This migration record is itself the
`legacy-inquery-migration` Processed Document package.
