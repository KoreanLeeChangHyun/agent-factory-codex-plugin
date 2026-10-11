# `operation_records.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`, `--loop-id LOOP_ID`.

## `query`: Structural lookup by task, session, loop, state and update time
- `--task-id TASK_ID`
- `--session-id SESSION_ID`: Agent ID of a conductor, Work or Verification session
- `--state {assigned,running,waiting-external,waiting-decision,blocked,execution-ended,work-completed,check-passed,unknown}`
- `--updated-since UPDATED_SINCE`: ISO-8601 UTC lower bound for a task's latest recorded update
- `--detail`: Return the full records instead of the summary

## `search`: Filter records, run results and lessons, then match words; hits cite sources
- `--text TEXT`: Words to find in requests, results, decisions and lessons (case-insensitive)
- `--match {all,any}`: Require all words (default) or any word
- `--kind {task,session,decision,observation,lesson}`: Record kind to search; repeat to combine (default: all kinds)
- `--task-id TASK_ID`
- `--session-id SESSION_ID`: Agent ID of a conductor, Work or Verification session
- `--state {assigned,running,waiting-external,waiting-decision,blocked,execution-ended,work-completed,check-passed,unknown}`
- `--role ROLE`: Session role (conductor, work, verification) or Work profile
- `--model MODEL`: Exact model ID recorded on the run
- `--since SINCE`: ISO-8601 date or time lower bound (UTC when no zone)
- `--until UNTIL`: ISO-8601 date or time upper bound (UTC when no zone)
- `--limit LIMIT`: Maximum hits returned (default 50)

## `supervise`: Judge unfinished loops (normal, delayed, stuck, decision-needed) and record due one-line reports
- `--interval-minutes INTERVAL_MINUTES`: Periodic report interval (default 10); stuck and decision-needed are reported at once
- `--delay-minutes DELAY_MINUTES`: No recorded activity for this long is delayed (default 20)
- `--stuck-minutes STUCK_MINUTES`: No recorded activity for this long is stuck (default 60)
- `--repeat-limit REPEAT_LIMIT`: Repeats of one control-plane error or failed Verification that are reported (default 3)
- `--save-settings`: Persist the resulting values as this runtime's defaults, also used by the loop driver
- `--dry-run`: Return verdicts without appending reports
