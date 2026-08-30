# Testing Convention

Apply this convention whenever implementation, maintenance, or Verification
work selects or runs tests.

## Focused execution

- Minimize test execution. Run the smallest relevant focused test set belonging
  to the owning component and the affected contract.
- Resolve that focused set from the owning project's established test runner,
  framework, component boundaries, and test organization. No particular runner,
  framework, command, or directory layout is universal.
- Broaden beyond the focused set only when its evidence shows cross-domain
  impact or the Human explicitly requests broader coverage.
- Do not run the repository-wide or otherwise full test suite unless the Human
  explicitly requests it.

## Agent graph boundary

Focused test scope does not collapse, replace, or skip Agent Factory's
independent Verification role. Verification independently checks the Work
result and selects the smallest relevant focused tests for the affected
component and contract. Verification broadens that scope under the same rule:
only when focused evidence shows cross-domain impact or the Human explicitly
requests broader coverage, and it runs the full suite only on the Human's
explicit request.
