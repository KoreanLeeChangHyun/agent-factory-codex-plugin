# P2 continuation: bootstrap cleanup and Main fixture alignment

Continue the exact P2 Work Agent session after the bounded loop stopped at its
revision budget. Address the remaining Review finding `REV-P2-004` and the
directly observed Main-test fixture mismatch. Do not run tests; Main owns them.

## REV-P2-004

The startup gate prevents the real target from executing before identity is
durable, but readiness timeout and pre-release abort close the gate and suppress
a bounded `wait()` timeout. A stopped or non-exiting bootstrap may therefore
remain as an untracked process group.

Required:

- Capture and verify the isolated bootstrap leader's immutable Linux identity
  immediately after `Popen`, retaining it through readiness/release.
- On every readiness timeout or pre-release abort, close the gate; if the
  bootstrap does not promptly exit, apply verified whole-group TERM, bounded
  wait, and KILL using that exact identity. Never signal an unverified or
  mismatched group.
- Add deterministic live-bootstrap coverage for readiness timeout and
  pre-release abort, proving no group member survives and no unrelated group is
  signalled.

## Main-test alignment

The focused suite otherwise passes, but
`test_aggregate_event_and_stderr_caps_never_grow_past_limit` expects an
overflowed `stderr.log` path not to exist. `append_bounded` safely creates a
regular file, rejects the first oversized chunk before writing, and leaves it
at 0 bytes. The contract is bounded disk growth, not path absence. Change only
that assertion to require empty bytes/size zero; do not alter safe runtime
behavior to satisfy the over-specific fixture.

Keep the original P2 scope and constraints. Report exact changed paths and
addressed finding IDs.
