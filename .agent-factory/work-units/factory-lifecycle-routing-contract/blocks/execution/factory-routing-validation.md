# Factory lifecycle routing validation evidence

## Canonical artifact validation

- `python3 skills/intake/scripts/intake.py validate .agent-factory/intakes/factory-control-plane --full`
  - `valid: true`
  - `schemaVersion: 2.0.0`
  - `profile: intake@2.0.0`
  - `id: factory-control-plane`
  - `status: ready`
  - `sectionCount: 7`
  - `validationMode: full`

- `python3 skills/work-unit-planner/assets/scripts/work_unit.py validate .agent-factory/work-units/factory-lifecycle-routing-contract --full`
  - `valid: true`
  - `schemaVersion: 4.0.0`
  - `profile: work-unit@4.0.0`
  - `id: factory-lifecycle-routing-contract`
  - `status: working`
  - `sectionCount: 9`
  - `validationMode: full`

## Active contract search

`rg -n '\bmain\b' skills/lifecycle skills/intake skills/work-unit-planner skills/work-unit-execution --glob '*.md' --glob '!**/tests/**'`

Only two active Markdown matches remain. Both explicitly state that Agent Factory does not infer `main`, `dev`, `staging`, `prod`, or another promotion target. No active Markdown instructs Intake checkpoint, Work Unit checkpoint, or Work Unit integration to use `main`.

## Specification

Specification remained optional/reference-only. No Specification package was created or modified.
