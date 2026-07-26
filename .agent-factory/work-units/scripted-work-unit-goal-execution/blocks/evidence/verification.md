# scripted-work-unit-goal-execution verification

Execution target: `db8fb4d7e1121f181cce22f7055c096b26e86835`

## TDD

- Initial focused run before implementation: failed with 13 errors because
  `skills/work-unit-execution/scripts/app_server_goal.py` did not exist.
- Final focused command:
  `python3 -W error::ResourceWarning skills/work-unit-execution/tests/test_app_server_goal.py`
- Final focused result: 7 tests passed in 1.127 seconds.
- Covered successful Goal admission, Goal completion before and after turn
  completion, CLI JSON/nonzero failure behavior, RPC error, null Goal, thread
  mismatch, objective mismatch, inactive Goal, invalid JSON, EOF, timeout,
  missing Goal notification, and failed turn.

## Regressions

- `python3 -W error::ResourceWarning -m unittest discover -s skills/work-unit-execution/tests -p 'test_*.py'`
  passed: 42 tests in 139.080 seconds.
- `python3 -m unittest discover -s skills/lifecycle/tests -p 'test_*.py'`
  passed: 17 tests in 150.606 seconds.
- `python3 -m unittest skills.lifecycle.tests.test_skill_metadata`
  passed: 5 tests.
- `python3 -m py_compile skills/work-unit-execution/scripts/app_server_goal.py skills/work-unit-execution/tests/test_app_server_goal.py`
  passed.
- `git diff --check` passed.

## Skill validation

- `python3 /home/deus/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/work-unit-execution`
  returned `Skill is valid!`.
- `python3 /home/deus/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/lifecycle`
  returned `Skill is valid!`.

## Installed app-server schema

`codex app-server generate-json-schema` completed successfully with the
installed Codex CLI. The generated request schemas contain `thread/start`,
`thread/goal/set`, `thread/goal/get`, and `turn/start`. Inspection also
confirmed `ThreadGoalStatus` includes `active` and `complete`, and the Goal
set/get response shapes match the launcher.

## AI review

- The launcher validates a full-valid ready Work Unit before starting
  app-server and performs no Git mutation.
- It starts `codex app-server --stdio` with an argument array and
  `shell=False`.
- `turn/start` is impossible until set response, get response, and the matching
  asynchronous Goal update all agree on thread id, objective, and active
  status.
- Errors fail closed with one stable JSON document and a nonzero CLI status.
- Child stdin/stdout/stderr and the child process are closed on success and
  failure; tests run with `ResourceWarning` promoted to an error.
- No private SQLite state or model-authored Goal receipt is used.
- One documentation finding was corrected: the asynchronous Goal notification
  can arrive while a Goal request is in flight, so the contract requires it to
  be observed before `turn/start` without claiming a false wire-order.
- No unresolved implementation finding remains.
