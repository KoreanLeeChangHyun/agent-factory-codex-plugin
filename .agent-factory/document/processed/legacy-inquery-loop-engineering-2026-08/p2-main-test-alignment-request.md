# P2 Main-test contract alignment

Main executed the focused suite after the P2 revision. All runtime and loop
tests passed except one fixture assertion:

```text
test_aggregate_event_and_stderr_caps_never_grow_past_limit
AssertionError: expected stderr_path not to exist
```

`append_bounded` safely opens the regular file, checks the aggregate cap before
writing, rejects the oversized first chunk, and leaves a 0-byte file. The
documented/requested security property is that disk growth never exceeds the
cap, not that the path is absent after rejection.

After the current managed loop is terminal, make the smallest correction in
`tests/test_agent_exec.py`: assert that the overflowed `stderr.log` exists only
at size 0 (or equivalently has empty bytes), while retaining the overflow event
assertion. Do not change runtime behavior merely to satisfy the over-specific
fixture. Do not run tests; Main will rerun them. Report the exact changed path.
