# Intake Agent sandbox compatibility static review

- Commit: `df1f5d0` (`fix(intakes): allow explicit sandbox mode`)
- Changed paths:
  - `skills/intakes/scripts/intake_agent_exec.py`
  - `skills/intakes/references/intake-management.md`
  - `skills/agents/references/main-agent.md`
  - `skills/agents/references/intake-agent.md`
- `SANDBOXES` restricts values to `read-only`, `workspace-write`, and `danger-full-access`.
- The launcher CLI and internal call path default to `workspace-write`.
- Both new and resume command forms receive `--sandbox <selected-mode>`.
- Capability routing still emits `sandbox_workspace_write.network_access=false` except for `web-search`, which remains `true`.
- `subprocess.Popen` remains an argv call with `shell=False`.
- Documentation reserves `danger-full-access` for caller-authorized use inside an already-isolated environment.
- Static review command: `git diff --check` (pass, no output), followed by manual inspection of the complete scoped diff.
- Tests, lint, typecheck, build, CLI execution, and smoke checks were not run because the Human did not authorize tests.
- Remaining risk: runtime parsing and nested-sandbox behavior are not execution-verified under the explicit no-tests boundary.
