# Processed Document layout migration

The Human-approved local-adapter root migration first moved retained bundles
from `.agent-factory/explorer/<document-id>/` to
`.agent-factory/document/processed/explorer/<document-id>/`. The Human's
2026-08-31 flat-layout decision then moved each bundle directly to
`.agent-factory/document/processed/<document-id>/`.

All retained bundles were classified as Processed Documents because they are
analysis, research reports, conclusions, or the delegated request context that
preserves the scope and provenance of that analysis:

- `.agent-factory/document/processed/convention-classification-20260829/`;
- `.agent-factory/document/processed/specification-visual-taxonomy-20260828/`;
- `.agent-factory/document/processed/trusted-executor-cross-platform-20260828/`.

No retained artifact was classified as Original: the tree contains no
source-faithful collection whose identity and native form can be separated from
the analysis bundle. Temporary execution-only material is not materialized in
this Document directory; future temporary Explorer material belongs to its
producing managed Agent run.

The second move only changed physical locators. Each bundle remains one
Processed Document package with the same stable identity, and package-internal
content was preserved except for explicit current-locator/provenance repairs.
There is no `explorer/` producer wrapper in the current Processed root.

Migration authority:
`.agent-factory/agent/document-root-migration-work/runs/run-20260830T085419496276Z-66baeaeb/request.md`.
