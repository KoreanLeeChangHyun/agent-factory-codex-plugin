# Cloud source retirement

The plugin distributes six Skills, three Agent role prompts, `exec.py`, `loop.py`
and `runtime/cloud_reporting.py`. The runtime paths and optional reporting flags
are preserved. Cloud reporting remains explicit and optional. Source retirement
does not change local execution, graph transitions, receipts or extension entry
points. No consumer local service replaces the retired domain executables.

## Implementation and test ownership map

Paths below are relative to the plugin unless linked into the MCP application.
The replacement evidence was independently accepted before this retirement Work:
platform Verification `run-20260905T175343294928Z-6b638ce3` retains 175 domain tests,
installed-wheel, integrated preview and actual worker-kill evidence and adds 14
real PostgreSQL integration, 22 shared and 2 independent race cases. This is
prior evidence, not a pass claim for the retirement changes.

| Retired source / former tests | Final owner and meaningful replacement coverage | Intentionally retired behavior |
| --- | --- | --- |
| `skills/agent/scripts/catalog.py`, `assets/schema/catalog.sql`; `test_agent_catalog_manager.py`, `test_agent_catalog_schema.py` | [Document service tests](../../mcp/tests/test_cloud_documents.py): literal Korean/identifier queries, scoped escaped search, atomic import/replay/conflict, pair binding and old-publication preservation; [reporting tests](../../mcp/tests/test_cloud_reporting.py): Agent/run/task/log/test scoped literal retrieval and immutable binding; [real DB tests](../../mcp/tests/test_cloud_platform_integration.py): RLS, races, binary inventory, search, previous accepted bytes; [legacy importer tests](../../mcp/tests/test_legacy_document_import.py): deterministic recursive package inventory, source untouched and symlink rejection | Local SQLite v1/v2/v3 initialization/migration, FTS5 grammar, project-root resolver, local rebuild/sidecar replacement, SQL index layout and local scan caps. Existing SQLite and sidecars remain untouched. Cloud schema/migrations and bounded package/source identities replace new local catalog creation. |
| `skills/convention/scripts/init_agents.py` | Final metadata tests retain six-Skill routing and `assets/AGENTS.md` equality; authorized file tools copy the text only to an absent target | Local initialization manager; no overwrite/merge authority is added |
| `skills/document/scripts/verify_specification_pair.py`; former `test_specification_coverage.py` loader | Final `test_specification_coverage.py` imports [owning validator](../../mcp/app/modules/document/pair.py), checks all six complete inventories and rejects missing/added/stale/reordered/duplicate sources, gaps, empty translation, placeholders, reciprocal mismatch and stale asset review | Distributed validator executable and separate local parser. Structural fixture review is explicitly synthetic; six-pair independent Korean semantic review remains required |
| `skills/gather/scripts/sync.py`, `assets/schema/sync.schema.json`; `test_gather_sync_manager.py` | [collection tests](../../mcp/tests/test_cloud_integrations_collections.py): independent selection sharing a connection, immutable bounds, persisted cursor/replay, durable results, storage-failure recovery, cross-workspace/requester denial; [real DB integration](../../mcp/tests/test_cloud_platform_integration.py): actual persistence, job authority/cancel/recovery | Local `sync.json` setters, Git-root discovery, destination precedence and local destination directory races. Existing config/source data stays intact; new destination is the resolved cloud Workspace |
| All six `skills/gather/scripts/sync_{discord,gmail,google_drive,notion,onedrive,slack}.py`, `provider_support.py`, `requirements.txt`; `test_gather_provider_scripts.py` | [provider tests](../../mcp/tests/test_cloud_integrations_providers.py): native Drive exports/folder pagination, Gmail raw EML/attachments, Slack private-URL redaction, Notion nested/fresh files, numeric Discord pagination, OneDrive redirects/cursor host restrictions, no credential forwarding, selection and byte limits, Retry-After/cancellation, sanitization/provenance; [collection tests](../../mcp/tests/test_cloud_integrations_collections.py): encrypted refresh, classified health errors, object-readback failure before cursor advance, crash reservation recovery | Project destination resolver, external local secret-file modes/atomic replacement, device-token cache writes and filesystem directory-swap writer. Cloud encryption and object-storage durability replace these implementations; provider fidelity/security cases remain server-owned |
| `skills/tool/scripts/tool.py`; `test_tool_adapters.py` | Final `test_tool_contracts.py` preserves exact host authority, Git/GitHub/LFS/Playwright profiles, unknown/unsupported/unauthenticated distinctions, structured non-secret inspection and readiness/execution separation; [integration collection tests](../../mcp/tests/test_cloud_integrations_collections.py) preserve actual cloud health classification and encrypted credentials | Local JSON adapter registry, subprocess wrappers and route-only mutation wrappers. Existing Agent shell/file tools perform bounded local inspection; cloud owns connection operations |
| Obsolete local ownership assertions in `test_convention_skill_metadata.py` and `test_document_contracts.py` | Final tests retain singular metadata, all six public Skills, role prompts, reference inventory, full reciprocal Korean packages/local dependencies, Document types/authority, exact six Activities, independent testing/Human decisions, source-backed diagrams and MCP ownership | Five-Activity assertions, zero Agent references, local catalog/sync inventory, old plural source-map attributes and exactly-three-template-files claim |

`test_distribution.py` stages the final Skills and six Human packages and exercises
exec/loop imports from an unrelated consumer directory without creating runtime data.
The extension locator remains `skills/agent/scripts/exec.py` in
`extension/src/infrastructure/agent-factory/plugin-locator.ts`; no extension source
was changed.

`test_agent_exec.py`, `test_agent_loop.py` and `test_agent_cloud_reporting.py` are
preserved for actual runtime behavior. No domain code was relabeled as runtime
support. Final Verification should also exercise installed runtime-relative
imports and existing extension script paths against an isolated final source
package. Generated run/outbox/cache state is excluded from distributable source.

## Template resource move

Every original file under `skills/document/assets/document/` moved byte-for-byte
to [MCP packaged resources](../../mcp/app/resources/document_template/), including
`index.html`, `app.js`, `styles.css`, `library.css`, both vendor libraries and all
license notices. The complete byte inventory is
[document_template_inventory.json](../../mcp/app/resources/document_template_inventory.json).
These are reusable authoring baseline resources, not accepted Human/AI pairs or
an authenticated browser shell. The cloud's existing `static/` and
`template/workspace/` continue to own Workspace runtime UI.

`document_template` is discoverable through authenticated MCP tool listing. It
returns the inventory, then version-bound base64 chunks of allowlisted members,
with a 64 KiB response-byte limit. It uses current `document:read` scope and
Workspace authorization. It introduces no static mount or executable HTML
response; uploaded-package attachment/member delivery and isolated preview CSP
are unchanged. See the [delivery guide](../../mcp/docs/cloud-documents.md).

The six existing `docs/specifications/<id>/` packages preserve
all standalone CSS/JS/vendor assets. Their HTML semantic edits match the changed
AI instructions and source maps. No Human package was overwritten with template
bytes, and no hash refresh stands in for independent semantic review.

## Verification handoff

Work did not run checks. Independent Verification owns plugin validation,
focused plugin tests, new MCP template/auth tests, MCP registration and wheel
resource tests, six-pair Korean semantic review and changed-path integration.
Use the MCP development dependencies; `AGENT_FACTORY_MCP_SOURCE` can select a
non-sibling source checkout. Missing dependency is an explicit error, never a
silent skip. The fixture hashes in structural tests are not publication evidence.

If Plugin Creator requires the outer directory to match manifest name, stage
source into a uniquely owned temporary `agent-factory/` directory. Include all
six Human source packages and runtime dependencies; exclude generated data.
Do not rename this repository, reinstall the runtime or edit marketplace config.
Live credentials, deployment, real account trials and data cutover require their
own exact targets and authority; they do not block completion of code retirement.


### Corrective gate handoff (RETIRE-001–004)

The maintained `mcp/tests/test_cloud_platform_integration.py` now selects current
Git-tracked plus nonignored untracked source, excludes Git-confirmed deletions
and generated caches, and uploads exact Document/Agent inventories without a
fabricated root HTML file. Original Git snapshots without a root preview entry
retain authenticated member delivery and explicitly reject a missing preview
entry. Template archives retain their real root entry and isolated preview.
The real packages need only exceed the inline limit; an explicitly synthetic
large archive separately protects capacity above 8 MiB without padding source.
`mcp/tests/test_cloud_document_delivery.py` uses the same inventory contract;
`mcp/tests/test_cloud_source_inventory.py` adds a disposable Git deletion/untracked
regression for independent Verification's focused test selection.

The existing real-DB integration module also discovers and invokes the registered
`document_template` tool with only Workspace/Document read scopes, reconstructs
every manifest-version-bound member, checks original baseline/vendor/license
bytes, and denies unauthenticated, insufficient-scope, wrong-Workspace and
revoked-current-membership requests. Diagnostics use lengths/digests rather than
payloads. These cases run in the existing platform gate/private-DB harness;
rootless isolated PostgreSQL remains an equivalent authorized fixture.

The Workspace Activity heading/navigation is now Korean while preserving the
technical Workspace identity and mapped source order. Placeholder checks inspect
HTML attributes and keep explanatory prose; an actual-attribute negative fixture
and the unchanged server validator preserve rejection coverage. This corrective
Work has not run tests or claimed a pass. All six complete pairs and diagram
relationships still require independent final semantic review.
