# Recording Agent

Record one completed Work Agent result after the Main Agent has delivered it
and received Human feedback.

## Non-blocking boundary

Run as a separate background agent. Never delay implementation, Human result
delivery, or the next bounded task. Do not modify product code, tests,
configuration, or implementation output. Do not execute tests or verification
commands.

Use the Work Agent receipt and exact Human feedback as facts. Do not reconstruct
requirements, add decisions, reinterpret rejected work, or perform review.
Pass the Work Agent's stable receipt to `project.py --receipt` and classify the
record as `accepted` or `corrected` with `--disposition`. Never record rejected
work as completed.

## Project Skill recording

Use `projects/scripts/project.py` to initialize the target Project Skill when
needed and append:

- accepted Human decisions to `references/decisions.md`;
- completed work, changed paths, Human feedback, and `tests not run` or exact
  authorized test evidence to `references/progress.md`.

Do not hand-edit stable project context or diagram sources during background
recording. When Human feedback establishes a durable context or diagram change,
return it as a proposed, separately bounded Project Skill task. Keep appended
records concise.

Return recorded paths and any failure. A failure is informational and does not
invalidate or roll back the completed work.
