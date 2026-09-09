# Testing Convention

Use this reference when organizing, selecting, or running tests.

## Source organization

### Layout rules

- Use `tests/` as the test root.
- Group tests into meaningful subdirectories by purpose or owning component.
- Do not accumulate tests directly under `tests/` or classify them only by filename prefixes.
- Keep runner configuration and shared discovery hooks at the root when the framework requires it.
- Extend an existing category before creating another.
- Update collection and imports when moving files.

### Plugin directories

- `tests/contracts/`: package structure, metadata, reference routing, and static
  public contracts;
- `tests/runtime/`: local Agent runtime behavior;
- `tests/integration/`: installation and cross-component behavior;
- `tests/support/`: shared fixtures and helpers that are not tests; and
- `tests/benchmarks/`: explicitly invoked performance harnesses, not ordinary
  test collection.

### Collection

- Name collected tests `test_<name>.py`; keep helpers outside collected modules.
- Configure shared import paths once; avoid duplicated path/bootstrap code.
- Remove tests for retired domains/deleted Human document packages.
- Test maintained ownership and observable behavior, not generated prose wording.

## Focused execution

- Run only the smallest relevant test set for the owning component and affected
  contract.
- Resolve it from the project's established runner and current test layout; do
  not treat one framework or command as universal.
- Broaden only when focused evidence demonstrates cross-domain impact or the
  Human explicitly requests broader coverage.
- Run a full suite only on explicit Human request.

## Parallel execution and speed

- For an authorized full suite, prefer the runner's process-based parallel
  execution after checking that tests isolate mutable state. Keep small focused
  runs serial when worker startup would cost more than it saves.
- Isolate runtime homes, temporary files, databases, ports, and subprocess
  ownership per worker or test. Sequence cases that must share an external
  resource; do not remove assertions or hide failures to make parallel runs pass.
- Bound worker count to the available CPU, memory, and child-process load.
  Compare elapsed time and outcomes on the same suite and environment before
  claiming a speedup; preserve a serial command for diagnosis.
- This plugin uses `pytest-xdist` from root `requirements-test.txt`. Its full
  suite command is `python3 -m pytest tests -n auto --maxprocesses=4 --dist=worksteal`;
  `-n 0` selects serial execution. Shared fixtures live in `tests/support/`.
  See the [runner's scheduling options](https://pytest-xdist.readthedocs.io/en/stable/distribution.html).
- Parallel execution does not expand test authorization or enable opt-in
  external integrations automatically.

## Agent graph boundary

- Organizing/authoring tests grants no execution authority; Main/Work run no
  verification commands.
- Verification independently checks exact Work with the smallest authorized tests.
- Report skipped/unrun tests honestly, never as passes.
