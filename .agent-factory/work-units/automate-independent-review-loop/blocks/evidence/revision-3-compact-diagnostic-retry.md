# Revision 3 compact diagnostic retry

- Classification: transient
- Revision: 3
- The launcher returned `state=refused`, but the terminal JSON was dominated by detailed app-server operations and the surfaced output truncated the top-level error detail.
- Recovery: resume the same revision and filter the single terminal JSON to its state, error, compact receipt, and revision summary for deterministic diagnosis.
- Tests and verification commands: not run.
