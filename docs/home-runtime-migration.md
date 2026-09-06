# Home runtime setup and physical migration handoff

Implementation is subject to independent Verification. This document is a procedure, not evidence that migration, retirement, installation or deployment occurred.

The executing host defaults to `~/.agent-factory`. Set an absolute `AGENT_FACTORY_HOME` for an alternate private runtime home. Never set `HOME` or `CODEX_HOME` to redirect Agent Factory. The latter remains Codex's own authority. Use the installed entry point from any code directory:

```sh
python3 /absolute/plugin/skills/agent/scripts/exec.py init --project-root /absolute/project
python3 /absolute/plugin/skills/agent/scripts/exec.py location --project-root /absolute/project
python3 /absolute/plugin/skills/agent/scripts/exec.py projects --project-root /absolute/project
```

`init` is the supported explicit setup entry for an authorized managed installation workflow. First managed submit and VS Code workspace-host connection use the same helper. A stock marketplace install does not execute an arbitrary post-install script; this change adds no hook, cachebuster or reinstall. Existing configured installations remain in place until independently validated replacement.

Read-only managed roles select a generated Codex named permission profile that reads the filesystem, disables network for sandboxed tools, and writes only their exact run directory. They do not pass a workspace sandbox mode. The same profile is supplied to native app-server turns through its `permissions` field. This follows the installed schema and the official [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). On Linux, Codex's [sandbox backend contract](https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md) routes this split policy to bubblewrap: it cannot round-trip through the wider legacy Landlock workspace policy while keeping the code root read-only. A host that denies bubblewrap user-namespace setup therefore fails closed before the filesystem operation. Do not switch to danger-full-access or a workspace-write fallback.

`location` returns schema version 1, `kind: runtime-location`, the canonical `projectRoot`, `home`, stable `projectId`, separate `runtimeRoot`, `agentsRoot` and `registered`. Missing registration returns null identity/runtime paths and performs no initialization. `projects` reports the private registry; `list` returns no sessions for an uninitialized code root. Runtime commands accept explicit `--runtime-home HOME --project-id ID` to retain the resolved binding across subprocesses. The extension validates and caches that contract on the workspace host, including remote hosts.

## Preconditions for later physical Work

1. Main obtains independent Verification of this implementation before delegating physical migration. Keep `/tmp/af-home-migration-20260906/bootstrap-agent/scripts/exec.py` and its runtime dependencies unchanged for recovery. The active run `home-runtime-work-20260906/run-20260906T090947805468Z-fa3870a8` is still in the old parent runtime; it must remain readable through the pinned old executable until Main has moved control.
2. Finish/reconcile all old runs and loops and stop submitting through the old runtime before inventory. Migration refuses active run states, held legacy locks, live recorded process identities, unsafe links/special files, source changes or destination conflicts. Do not fabricate terminal status to bypass these gates. Archive-only malformed inactive records require independent review; they are not semantically completed sessions.
3. Select a private independent backup directory outside every source project and outside the runtime home. Do not use Git, a runtime subdirectory or a symlink. Keep credential stores with their existing authority; do not add raw runtime, untracked Documents, database bytes or credentials to Git. Tracked publication source was moved to `plugin/docs/specifications`; tracked historical Processed packages were moved byte-for-byte to `plugin/docs/archive/processed`.
4. Start the physical copy Work in a home-managed control project outside the sources being migrated, or keep a clearly separated pinned bootstrap control run. That copy Work request must include the exact plan ID. Its request/result/receipt and the subsequent independent Verification evidence must survive source retirement. Do not include active control runtime records in a supposedly quiescent source inventory.

## Inventory, plan and copy

Use the new installed or verified source `skills/agent/runtime/migration.py`. These commands execute no model or network request. Pass the parent, plugin, extension and MCP roots separately. Inventory requires that the selected root actually has a legacy `.agent-factory`; omit a root with no legacy data instead of creating an empty legacy directory.

```sh
python3 /absolute/plugin/skills/agent/runtime/migration.py inventory \
  --project-root /home/deus/workspace/agent-factory \
  --project-root /home/deus/workspace/agent-factory/plugin \
  --project-root /home/deus/workspace/agent-factory/extension \
  --project-root /home/deus/workspace/agent-factory/mcp

python3 /absolute/plugin/skills/agent/runtime/migration.py plan \
  --runtime-home /absolute/private/runtime-home \
  --project-root /home/deus/workspace/agent-factory \
  --project-root /home/deus/workspace/agent-factory/plugin \
  --project-root /home/deus/workspace/agent-factory/extension \
  --project-root /home/deus/workspace/agent-factory/mcp \
  --plan /absolute/private/control/plan.json

python3 /absolute/plugin/skills/agent/runtime/migration.py copy \
  --plan /absolute/private/control/plan.json \
  --backup /absolute/independent/backup
```

Before delegating that copy Work, generate its exact machine request with the same backup path:

```sh
python3 /absolute/plugin/skills/agent/runtime/migration.py copy-request \
  --plan /absolute/private/control/plan.json \
  --backup /absolute/independent/backup
```

The Work request is exactly the emitted `migration-copy-request`. Its result is the same object with `kind` changed to `migration-copy-result`. Both bind the plan, home, backup, full source inventory hash, and exact source-to-destination projection hash.

The plan includes the exact canonical root/ID bindings, file hashes/sizes, directory inventory, source-to-operational mapping and archive-only records. Inventory and plan contents are local sensitive evidence, never Git additions. Preserve the plan ID and exact plan bytes for every retry. A changed source needs a newly reviewed plan; do not rewrite a prior identity or historical request hashes. Copy retries use the original backup binding and preserve a journal below `HOME/migrations/PLAN_ID/`.

Copy produces an immutable historical `archive/PROJECT_ID/...`, an independent `BACKUP/PLAN_ID/PROJECT_ID/...`, and a separate `projection/PROJECT_ID/agent/...`. Request/result/receipt/event bytes remain exact. Legacy Documents/SQLite remain archive-only rather than becoming a local domain service. The operational JSON overlay maps exact filesystem locators; original report recipient fields, dispatch hashes, outbox payloads, run IDs and session IDs remain unchanged. Historical text links remain historical text. Use the complete manifest to resolve evidence across projects; do not rewrite archived Markdown or receipt bodies.

## Independent verification and activation

After copy Work finishes, Verification runs deterministic byte eligibility and independent semantic/runtime checks:

```sh
python3 /absolute/plugin/skills/agent/runtime/migration.py verify-eligible \
  --plan /absolute/private/control/plan.json
```

This command is not an independent pass. Verification must inspect the archive-only classifications and full cross-project map, validate migrated valid and invalid receipts, assess exact-session resume and loop fail/pass/Human-skip recovery, check native Fast/Goal continuation with the owned local mock, and confirm pending reports retain their original recipient and idempotency keys. Never use a paid provider for this validation. Use an isolated disposable home/projection for behavioral checks so the production source inventory and staged publication remain unchanged.

Verification supplies the following private JSON evidence, with actual values from the plan-specific physical copy Work and its independent Verification. No placeholders, invented pass or Work-authored attestation may activate migration:

```json
{
  "schemaVersion": 2,
  "kind": "migration-verification",
  "workStatePath": "/absolute/home/projects/project-id/agents/copy-work/runs/run-id/state.json",
  "verificationStatePath": "/absolute/home/projects/project-id/agents/copy-verification/runs/run-id/state.json"
}
```

The gate resolves both paths through the managed runtime and requires canonical completed runs with distinct Work and Verification sessions. It rechecks session ownership, original request hashes, exact response and role receipt schemas, strict receipts, terminal output events, and exact JSON request/result documents without unknown fields. Verification's request, result, and pass receipt must bind the copy Work run, original Work request, result bytes, and the same plan/home/backup/source/projection digest tuple. This local evidence is tamper-evident within the managed contract; it does not claim protection against the account owner forging all local authorities.

```sh
python3 /absolute/plugin/skills/agent/runtime/migration.py activate \
  --plan /absolute/private/control/plan.json \
  --evidence /absolute/private/control/independent-verification.json
```

Activation refuses an occupied destination, publishes from the separate projection, and records per-project pending/complete markers plus a shared journal. Interrupted publication is blocked from runtime use and resumes with the same plan/evidence; retain staging, archive, backup and journal. Do not manually merge conflicting destinations or delete recovery files. New mutable runtime records are separate from the immutable archive. Resume exact IDs through the new `exec.py`; never `resume --last`.

## Authorized retirement and recovery

Main confirms control has left the old runtime and has actual independent validation evidence. The Human has already authorized removal of the old project directories after validation; the later Work should use that exact authority reference rather than ask again.

```sh
python3 /absolute/plugin/skills/agent/runtime/migration.py retire \
  --plan /absolute/private/control/plan.json \
  --evidence /absolute/private/control/independent-verification.json \
  --authority-reference 'exact Human authorization for validated source retirement'
```

Retirement rechecks source/archive/backup/projection evidence, actual process identity and containment emptiness, held writer locks, and the gate on every retry. It atomically renames each exact source to a plan-bound retirement path and persists each file or directory deletion separately with its original device/inode identity. It never recursively removes an unbounded tree. Foreign, replaced, reappearing or symlink content in the source or tombstone stops the retry without deleting that content. The home archive and independent backup remain. Main owns any later verified installation switch, Git integration or publication; this procedure does not authorize deployment, restart, cloud changes or credential duplication.

## Focused verification commands

Work did not run these commands. From the corresponding owning repository, Verification can select:

```sh
# plugin: all runtime homes are isolated by the test fixtures
python3 -m unittest discover -s tests -p 'test_home_runtime.py'
python3 -m unittest discover -s tests -p 'test_migrated_graph.py'
python3 -m unittest discover -s tests -p 'test_capability_cache.py'
python3 -m unittest discover -s tests -p 'test_agent_exec.py'
python3 -m unittest discover -s tests -p 'test_agent_loop.py'
python3 -m unittest discover -s tests -p 'test_agent_cloud_reporting.py'
python3 -m unittest discover -s tests -p 'test_native_codex.py'
python3 -m unittest discover -s tests -p 'test_native_transport.py'
python3 -m unittest discover -s tests -p 'test_distribution.py'
python3 -m unittest discover -s tests -p 'test_document_contracts.py'
python3 -m unittest discover -s tests -p 'test_specification_coverage.py'
python3 -m unittest discover -s tests -p 'test_convention_skill_metadata.py'
# Explicit opt-in: real installed native host, owned loopback mock provider only
AF_VERIFY_LOCAL_CODEX=1 python3 -m unittest discover -s tests -p 'test_home_runtime.py'
AF_VERIFY_LOCAL_CODEX=1 python3 -m unittest discover -s tests -p 'test_installed_native_scheduler.py'
# extension
node --test test/unit/runtime-adapter.test.mjs
```

The paired specification coverage tests require the existing explicit MCP development dependency described in `tests/mcp_dependency.py`. Hash coverage does not establish Korean semantic equivalence; independently review the changed complete pairs. No full-suite result is claimed.
