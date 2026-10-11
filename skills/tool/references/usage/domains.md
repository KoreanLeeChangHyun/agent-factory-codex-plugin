# `domains.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `list`: Read the project's domains, worker memberships, unresolved workers and recent change history

## `create`: Create a domain with a real work-area name; for ai an existing matching name is reused
Required: `--actor {human,ai}`, `--source SOURCE`, `--name NAME`
- `--expected-revision EXPECTED_REVISION`: Fail with domain_conflict if the list changed since this revision

## `rename`: Rename a domain; former names stay linked to recorded tasks
Required: `--actor {human,ai}`, `--source SOURCE`, `--domain-id DOMAIN_ID`, `--name NAME`
- `--expected-revision EXPECTED_REVISION`: Fail with domain_conflict if the list changed since this revision

## `assign`: Place a worker in a real domain; ai cannot move a worker the Human placed
Required: `--actor {human,ai}`, `--source SOURCE`, `--agent AGENT`, `--domain-id DOMAIN_ID`
- `--expected-revision EXPECTED_REVISION`: Fail with domain_conflict if the list changed since this revision

## `remove-worker`: Human only: hide a stopped worker from the worker list; its records and domain are preserved
Required: `--actor {human,ai}`, `--source SOURCE`, `--agent AGENT`
- `--expected-revision EXPECTED_REVISION`: Fail with domain_conflict if the list changed since this revision

## `link`: Main: reuse or create the named domain and place the worker unless the Human placed it
Required: `--actor {human,ai}`, `--source SOURCE`, `--agent AGENT`, `--name NAME`
- `--expected-revision EXPECTED_REVISION`: Fail with domain_conflict if the list changed since this revision

## `recover`: Place workers without any entry in the one domain their own runs recorded; list the rest as unresolved
Required: `--actor {human,ai}`, `--source SOURCE`
- `--expected-revision EXPECTED_REVISION`: Fail with domain_conflict if the list changed since this revision
- `--dry-run`: Report what would be recovered without writing
