# Exec performance research

This harness is intended to measure the **installed Codex executable**, driven by the current
`skills/agent/scripts/exec.py` public commands, with a deterministic fake Responses
provider on an owned loopback port. It makes no measured speedup claim. Work did
not execute the harness; independent Verification owns measurements and conclusions.

This revision prepares a new measurement chain bound to Work
`run-20260906T091552601751Z-05bd4c28`. **No successful measurements or speedup
are claimed by Work.** Verification must publish the measured values.

Historical Verification `run-20260906T090626817459Z-e6afbdac` recorded zero
successful turns because `workspace-write` failed with
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. Its original
benchmark JSON and result remain preserved at
`.agent-factory/agent/exec-perf-verify-host-20260906/runs/run-20260906T090626817459Z-e6afbdac/`.
That failure is evidence about sandbox initialization, not latency. The preceding
document and harness are also preserved in this Work run's `before/` directory.

**The new delegated request explicitly authorizes Verification to select
`--sandbox danger-full-access` for this owned deterministic benchmark only.**
No host policy, privileges, installed settings, production defaults, process
identity checks or containment checks are changed by this Work. The harness
default remains `workspace-write`; danger-full-access results must not be
reported as workspace-write success. The private configuration and submit use
the same explicitly chosen supported mode, which is recorded in raw JSON.

Before editing runtime, Work copied the current full `skills/agent` source
(including pre-existing dirty files) into:

```text
/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/exec-speed-work-20260906/runs/run-20260906T091552601751Z-05bd4c28/baseline/skills/agent/
```

The adjacent `baseline-sha256.json` records every copied source file hash;
generated Python caches were excluded. This is the current-source baseline,
not Git HEAD. Both measurements use the revised harness and unchanged shared
`tests/mock_responses_provider.py`, selecting their runtime with `--exec-path`.
The fixture follows the current home registry in its explicit private
`AGENT_FACTORY_HOME`, including cleanup, rather than obsolete checkout paths.

Verification must first inspect isolation and owned cleanup, then run these
bounded commands from `/home/deus/workspace/agent-factory/plugin`. Use a fresh
Verification run directory for `EVIDENCE`; do not overwrite prior JSON.

```sh
WORK_RUN=/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/exec-speed-work-20260906/runs/run-20260906T091552601751Z-05bd4c28
EVIDENCE=/absolute/path/to/this/verification/run
python3 tests/benchmark_exec.py --exec-path "$WORK_RUN/baseline/skills/agent/scripts/exec.py" --codex /home/deus/.local/bin/codex --sandbox danger-full-access --iterations 3 --timeout 90 --poll-interval 0.1 --output "$EVIDENCE/baseline.json"
python3 tests/benchmark_exec.py --exec-path /home/deus/workspace/agent-factory/plugin/skills/agent/scripts/exec.py --codex /home/deus/.local/bin/codex --sandbox danger-full-access --iterations 3 --timeout 90 --poll-interval 0.1 --output "$EVIDENCE/current.json"
PYTHONPATH=tests python3 -m unittest test_capability_cache
```

Record the resolved executable identity/hash before both invocations and ensure
it is unchanged; each invocation gets a fresh private HOME/CODEX_HOME. Check
baseline hashes against the manifest and bind Verification's result to the exact
Work run above. Select additional native regression cases only if inspection or
focused failures show a relevant impact. Work has run no tests or benchmarks.

The optimization is a 60-second successful-protocol cache, bounded to one entry
at `<AGENT_FACTORY_HOME or ~/.agent-factory>/cache/native-capabilities/`.
It keys resolved executable path, device/inode, size, nanosecond mtime/ctime and
resolved CODEX_HOME. It uses the owning `runtime/paths.py` private-path helpers,
atomic publication and a lock with at most 500 ms contention wait before a fresh
probe. Failed or partial probes are never persisted. Invalid, expired, future,
corrupt, unsafe or inaccessible entries trigger probing; setting
`AF_CODEX_CAPABILITY_CACHE=0` disables caching. Model/account Fast-tier
availability remains live `model/list` behavior and is never cached.
Wrappers whose underlying binary changes without changing the wrapper's own
identity can retain support for at most the TTL; this is not a content hash of
arbitrary transitive dependencies. A busy lock can cause duplicate probes.

The raw JSON includes three separate public capability-command durations:
`capabilitySamples[0]` is cold and `[1:]` exercise reuse across processes.
They include process startup, are excluded from turn duration, and warm the
current cache before the initial/resumed samples. Ordinary CLI submit/send in
this fixture do not necessarily call native capability inspection. Consequently
a capability improvement alone does not demonstrate a CLI-turn speedup.
Verification must report initial and resumed terminal median/min/max and sample
counts from `summary`, the three capability timings (plus their median/min/max),
cleanup status and actual completed pairs for each source. Require at least
three initial plus three resumed successes per source. Failed/missing values
are unavailable, never zero. If no improvement is observed, say so and identify
the next bottleneck supported by the raw timing breakdown. Fake-provider and
real tool/process overhead do not measure real LLM generation speed.

Use a new explicit output filename for each invocation; existing files are refused.
`--codex /absolute/path/to/codex` selects an installed executable. Defaults are three
iterations, each containing a fresh Agent `submit` followed by `send` to that
Agent's exact saved session, a 100 ms polling interval, and a 90 second total target.
The harness reserves 25 seconds for cleanup and stops measurements at 65 seconds.
It fails if the budget is insufficient to finish all six turns. There is no warmup
or discarded first sample. Four pairs can be requested with `--iterations 4`.
The fixture's existing 16-request cap bounds accepted request processing, not total
HTTP arrivals (transport retries can exceed it).

Every turn requires two fixture requests: one emits an `exec_command` tool call
that writes the owned run's result and exact Work receipt, and one emits the final
JSON. The call preserves the advertised function name and its separate Responses
namespace, and supplies only advertised arguments. Where supported, it selects
`/bin/sh` without login startup, an explicit owned working directory, and a ten
second tool-output wait. Codex executes that tool under the selected sandbox mode; the harness does not write
the result on its behalf. The public runtime validates result, receipt, sandbox,
containment and session identity using its existing checks. The harness also
requires one completed-turn event, exact final output, two provider requests, and
unchanged session identity on resume. Unsupported tool names, incompatible installed
command arguments, sandbox failures and runtime errors produce nonzero exit and
failure evidence. A deterministic fixture/tool failure emits a failed assistant
response rather than an HTTP 500, and the observer stops at its next status poll.
Bounded advertised tool schema, emitted call, and last tool responses are saved in
`provider.diagnostics`, including rejection text when supplied by the host. If the
tool remains asynchronous after the wait, missing output files fail with those
diagnostics; the fixture does not invent successful tool completion. There is no
direct app-server fallback disguised as exec success.

The JSON includes raw command durations and bounded command output, per-turn
provider arrival times, state and event evidence, initial/resumed median/min/max
summaries, installed version, platform/Python labels, and the source exec.py hash.
Capability inspection uses separately timed public `capabilities` commands, including
process startup and schema generation; it is not an isolated schema-generation
measurement and is excluded from turn durations.

Timing definitions:

- Acceptance: public `submit`/`send` process invocation through returned ACK.
- Worker, thread and assistant: first observer detection of worker identity,
  `thread.started`, and completed assistant-message event. These are upper bounds,
  sampled after status calls; assistant timing is not a token-level first-byte time.
- Provider: fixture callback arrival measured with the same monotonic clock, after
  the request body is read and parsed. It is not socket-first-byte timing.
- Terminal: invocation through first public terminal status observation. Runtime
  `acceptedAt`, `startedAt`, and `finishedAt` remain in raw state as separate wall
  clock evidence. `startedAt` denotes thread acknowledgement, not worker birth.
- Status command time: cumulative process time spent polling that turn; counts are
  included. Result command duration is recorded separately from terminal latency.

A fresh private HOME/CODEX_HOME, temporary Git project, allowlisted child environment,
fixture-only provider configuration, and dummy local token isolate account settings.
Account credentials, inherited provider URLs, proxies, plugins and shell startup
files are not copied. The loopback provider receives all configured model traffic;
request/final/error counts are evidence of that traffic. The JSON deliberately
leaves `externalProviderCalls` null: this harness does not perform a network packet
audit, so configured isolation is not represented as an observed external-call
count. Verification must inspect this boundary before execution. The fixture has no
forwarding or external model client. No paid model is selected.

Cleanup uses Linux subreaper adoption and the runtime's existing process identity
and containment helpers, restricted to children and run states created inside this
invocation. Owned CLI children have private process groups and bounded communicate
timeouts. SIGINT/SIGTERM enter cleanup. Failure to prove cleanup leaves the private
directory path in the JSON and makes the run unsuccessful; no unrelated runtime
state is deleted. Runtime termination/query bounds and OS scheduling can add overhead
to the 90 second target. SIGKILL or machine loss cannot guarantee in-process cleanup.

Prioritized hypotheses to investigate after collecting successful evidence:

1. **Repeated schema generation and process startup.** Compare the capabilities
   cost with turn latency. Compare cold and reused capability samples from the implemented short-lived cache. Ordinary CLI turns and native
   Fast/Goal routes differ; this benchmark does not establish costs for the latter.
2. **Sequential RPC round trips.** Inspect the native adapter's setup/resume chain
   in a separately labelled native experiment. This CLI benchmark provides no
   per-RPC measurements and cannot support an RPC speedup claim.
3. **Status polling and process spawning.** Compare cumulative status-command time
   and poll counts with terminal latency, then run the same harness with another
   `--poll-interval`. Reduced polling may lower observer cost while increasing
   completion-detection delay; those effects need separate interpretation.
4. **Environment and tool startup.** Compare initial versus resumed samples and
   first-provider versus terminal time. The gap includes real shell/Python result
   writing and a second model round trip, not just model generation. Test any
   proposed startup change separately without weakening isolation or identity checks.

Verification should inspect the harness's isolation and cleanup, run the command,
and record actual observations and limitations in its own `result.md`, without
editing source. The smallest existing installed-host fixture checks are in
`tests/test_installed_native_scheduler.py`; its native lifecycle test also exercises
`MockResponsesProvider`, which this harness subclasses without modifying. Select
that focused test using the repository's established unittest invocation and
installed-host opt-in; do not run the full suite. A failed public benchmark remains
useful compatibility evidence but does not satisfy the six-turn measurement goal.

For the focused existing lifecycle check, from the plugin root:

```sh
PYTHONPATH=tests AF_VERIFY_LOCAL_CODEX=1 python3 -m unittest test_installed_native_scheduler.InstalledSchedulerWithFakeModel.test_native_initial_reopen_accounting_controls_and_validation
```

Its separate timeout and native Goal behavior are not part of the benchmark's
90 second target or the initial/resumed CLI summary.
