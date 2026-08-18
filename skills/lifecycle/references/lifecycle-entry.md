# Agent Factory Lifecycle

Use the opened primary Git workspace as `<project-root>`.

## Default route

```text
Human request
  -> Main Agent bounds the next small task
  -> Work Agent edits the current Git workspace
  -> Main Agent immediately returns the result
  -> Human accepts, corrects, or supplies the next task
  -> Recording Agent records the prior result in the background
```

This route requires no Intake, Specification, Work Unit, Work Package,
documentation pass, AI review, or artifact checkpoint. UI work uses
this route by default because the Human's direct visual feedback is the primary
evaluation loop.

Git is the default history and recovery mechanism. A Work Agent preserves
unrelated uncommitted changes and never commits, resets, restores, deletes,
pushes, deploys, or restarts unless the Human explicitly requests that exact
action.

## Tests

Test criteria, repository conventions, changed code, or Agent preference do not
authorize test execution. Run tests only when the Human explicitly requests
testing or verification. Use an exact supplied command unchanged; otherwise
select the smallest bounded command from repository evidence and report it.
Without authorization, report `tests not run` and let the Human evaluate the
delivered result.

## Project source and view

The target Project Skill is the default AI-facing project source. A local
loopback server may render the Project Skill, Git progress, decisions, and
diagram sources as read-only HTML/CSS/JavaScript for the Human. Use `projects`
for both boundaries.

Project recording follows work and Human feedback. It never gates execution.

## Explicit advanced routes

Only an explicit Human request selects these routes:

- `Intake`: durable evidence or research ledger;
- `Specification`: canonical Specification package;
- `Work Unit` or `Work Package`: durable orchestrated execution in the primary
  Git workspace;
- `tests`: explicitly requested verification, using exact supplied commands or
  bounded commands selected from repository evidence;
- `documentation` or `independent review`: separate role pass.

When selected, use each artifact's owning manager. Never create or mutate
canonical Intake, Specification, Work Unit, or Work Package JSON with generic
file tools. Existing advanced lifecycle validation, Goal launch, role
separation, and review contracts apply only within that selected route.

Specification is an optional feature, not a default. Do not infer it from task
size, code changes, or the existence of historical artifacts.

## Safety boundary

Ask before a Human-owned product decision or an action that deletes, replaces
uncommitted work, pushes, creates a PR, deploys, restarts, migrates, transmits
externally, or crosses the project root. Ordinary reversible implementation
details inside the requested boundary do not require another approval.

The literal `BREAK-GLASS` owner recovery contract remains available for a
named project-internal control-plane target and bounded scope. It does not
expand test, destructive, deployment, restart, or external authority.

## Skill routing

- `agents` for Main, Work, Recording, and optional advanced roles;
- `projects` for Project Skill and local Viewer;
- `rules` before edits, design, review, or workflow claims;
- `intakes`, `specifications`, and `work-units` only when their optional route
  is selected;
- `conventions` for annotations and UI icons;
- `synchronization` for explicit workspace synchronization.
