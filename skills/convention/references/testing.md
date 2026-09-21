# Testing Convention

- Use this reference when organizing, selecting, or running tests.

<a id="source-organization"></a>

## 1. Source organization

<a id="layout-rules"></a>

### 1.1. Layout rules

- Use `tests/` as the test root.
- Group tests into meaningful subdirectories by purpose or owning component.
- Do not accumulate tests directly under `tests/` or classify them only by filename
  prefixes.
- Keep runner configuration and shared discovery hooks at the root when the framework
  requires it.
- Extend an existing category before creating another.
- Update collection and imports when moving files.

<a id="collection"></a>

### 1.2. Collection

- Follow the project runner’s test naming and discovery rules.
  Keep helpers outside collected test modules.
- Configure shared import paths once; avoid duplicated path/bootstrap code.
- Remove tests for retired domains/deleted Human document packages.
- Test maintained ownership and observable behavior, not generated prose wording.

<a id="focused-execution"></a>

## 2. Focused execution

- Run only the smallest relevant test set for the owning component and affected
  contract.
- Resolve it from the project's established runner and current test layout; do not treat
  one framework or command as universal.
- Treat the interpreter and dependency environment as part of that runner. Before
  execution, inspect repository evidence such as environment directories, tool
  configuration, dependency files and CI setup; do not assume the system-default Python
  contains the project's test dependencies.
- Run an exact Human-supplied command unchanged first.
  - If it fails before collection because its interpreter lacks the runner or
    dependencies, make no installation change unless authorized.
  - Resolve an existing compatible project environment and retry the same test scope and
    options through that environment.
  - Report the initial infrastructure failure separately from the retry result.
- Never encode a development sibling's environment path as a durable repository command.
  An evidenced adjacent shared environment may be used only as a local execution
  fallback when its compatibility is checked for the selected test.
- Broaden only when focused evidence demonstrates cross-domain impact or the Human
  explicitly requests broader coverage.
- Run a full suite only on explicit Human request.

<a id="parallel-execution-and-speed"></a>

## 3. Parallel execution and speed

- For an authorized full suite, prefer the runner's process-based parallel execution
  after checking that tests isolate mutable state. Keep small focused runs serial when
  worker startup would cost more than it saves.
- Isolate runtime homes, temporary files, databases, ports, and subprocess ownership per
  worker or test. Sequence cases that must share an external resource; do not remove
  assertions or hide failures to make parallel runs pass.
- Bound worker count to the available CPU, memory, and child-process load. Compare
  elapsed time and outcomes on the same suite and environment before claiming a speedup;
  preserve a serial command for diagnosis.
- Parallel execution does not expand test authorization or enable opt-in external
  integrations automatically.

<a id="agent-graph-boundary"></a>

## 4. Agent graph boundary

- Organizing/authoring tests grants no execution authority. Within the bounded request,
  Work performs necessary own checks and records commands/results or reasons not run.
  These checks never substitute for independent Verification in verification modes.
  Main performs own checks in direct mode only; for delegated work Main acknowledges
  the bound result/receipt and reports without reviewing implementation or rerunning tests.
  Plan-only returns its plan without implementation or execution checks.
- Verification independently checks exact Work with the smallest authorized tests.
- Report skipped/unrun tests honestly, never as passes.
