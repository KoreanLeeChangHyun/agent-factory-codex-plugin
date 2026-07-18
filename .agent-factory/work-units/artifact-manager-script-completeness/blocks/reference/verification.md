# Artifact manager script completeness verification

## Scope

- Reviewed the shared sectioned-document engine and the Intake, Specification, and Work Unit adapters.
- Added the missing Specification metadata schema, profile-driven manager, dependency declaration, and regression tests.
- Kept Specification lifecycle deterministic and draft-only; no approval transition was invented.
- Kept the legacy custom manifest explicitly incompatible with the common contract.

## Verification

Executed in `/home/deus/workspace/agent-factory/codex-plugins-worktrees/artifact-manager-script-completeness`:

```text
python3 -m py_compile skills/lifecycle/assets/scripts/sectioned_document.py skills/intake/scripts/intake.py skills/specification/scripts/specification.py skills/work-unit-planner/assets/scripts/work_unit.py
python3 skills/intake/tests/test_intake_manager.py
python3 skills/specification/tests/test_specification_manager.py
python3 skills/work-unit-planner/tests/test_work_unit_manager.py
python3 skills/lifecycle/tests/test_document_profiles.py
python3 skills/lifecycle/tests/test_skill_metadata.py
python3 skills/work-unit-execution/tests/test_worktree.py
python3 skills/intake/scripts/intake.py check-schemas
python3 skills/specification/scripts/specification.py check-schemas
python3 skills/work-unit-planner/assets/scripts/work_unit.py check-schemas
git diff --check
```

Result: all commands exited with status 0. The Specification suite ran 8 tests, and the lifecycle profile suite ran 7 tests.

## Worktree inspection

```json
{"command":"inspect","context":{"branch":"work-unit/artifact-manager-script-completeness","changes":[{"path":"skills/lifecycle/assets/scripts/sectioned_document.py","status":" M"},{"path":"skills/lifecycle/references/common-document-contract.md","status":" M"},{"path":"skills/lifecycle/tests/test_document_profiles.py","status":" M"},{"path":"skills/specification/SKILL.md","status":" M"},{"path":"skills/specification/assets/profiles/api-design.profile.json","status":" M"},{"path":"skills/specification/assets/profiles/class-architecture.profile.json","status":" M"},{"path":"skills/specification/assets/profiles/data-model.profile.json","status":" M"},{"path":"skills/specification/assets/profiles/project-core.profile.json","status":" M"},{"path":"skills/specification/assets/profiles/requirements-specification.profile.json","status":" M"},{"path":"skills/specification/assets/schema/metadata.schema.json","status":"??"},{"path":"skills/specification/scripts/requirements.txt","status":"??"},{"path":"skills/specification/scripts/specification.py","status":"??"},{"path":"skills/specification/tests/test_specification_manager.py","status":"??"}],"dirty":true,"headCommit":"69d30ebadac7382a9a01b76e2c501e87a95c3a20","lockReason":"Agent Factory Work Unit execution: work-unit/artifact-manager-script-completeness","locked":true,"repository":"/home/deus/workspace/agent-factory/codex-plugins","workUnitId":"artifact-manager-script-completeness","worktreePath":"/home/deus/workspace/agent-factory/codex-plugins-worktrees/artifact-manager-script-completeness"},"error":null,"ok":true,"operations":[],"schemaVersion":"1.0.0","state":"dirty"}
```
