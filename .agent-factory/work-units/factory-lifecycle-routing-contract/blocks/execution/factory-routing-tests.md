# Factory lifecycle routing test evidence

Execution branch: `work-unit/factory-lifecycle-routing-contract`
Implementation commit: `d0eb012`

## TDD red

Command:
`python3 -m pytest -q skills/work-unit-planner/tests/test_work_unit_manager.py::WorkUnitV4ManagerTests::test_admission_accepts_package_from_linked_authoring_worktree skills/work-unit-execution/tests/test_worktree.py::WorktreeCliTest::test_prepare_accepts_checkpointed_package_from_authoring_worktree skills/lifecycle/tests/test_artifact_handoff.py::ArtifactHandoffTests::test_checkpoint_refuses_detached_head_without_mutation`

Result before implementation: `2 failed, 1 passed in 99.28s`.

Expected failures:

- Work Unit manager attempted `package.relative_to(repository)` and could not admit a package in another linked worktree.
- `worktree.py prepare` did not recognize `--package`.

The detached-HEAD refusal test already passed against the approved checkpoint bootstrap.

## Focused green

The expanded five-scenario set passed: `5 passed in 145.96s`.

Covered:

- package from a linked authoring worktree is admitted;
- package from a different Git repository is refused;
- `worktree.py prepare --package` prepares from the authoring package;
- a relative package path is refused before Git mutation;
- a detached checkout is refused before checkpoint mutation.

## Full regression

- `python3 -m pytest -q skills/lifecycle/tests/test_artifact_handoff.py`
  - `6 passed in 281.16s`
- `python3 -m pytest -q skills/work-unit-execution/tests/test_worktree.py`
  - `38 passed in 198.61s`
- `python3 -m pytest -q skills/work-unit-planner/tests/test_work_unit_manager.py`
  - `28 passed in 1072.35s`
- `python3 -m pytest -q skills/work-unit-execution/tests/test_app_server_goal.py`
  - `10 passed, 9 subtests passed in 1.29s`

## Static checks

- `python3 -m py_compile skills/work-unit-planner/assets/scripts/work_unit.py skills/work-unit-execution/scripts/worktree.py skills/work-unit-execution/scripts/app_server_goal.py`
  - exit `0`
- `git diff --check`
  - exit `0`
