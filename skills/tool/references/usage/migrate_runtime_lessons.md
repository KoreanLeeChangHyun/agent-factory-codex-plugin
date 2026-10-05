# `migrate_runtime_lessons.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Required: `--project-root PROJECT_ROOT`
- `--agents-root AGENTS_ROOT`: Run storage to read signatures from; defaults to the project's runtime storage
- `--list`: Also list each signature and the undetermined record IDs
- `--apply`: Write the merge; without it nothing is changed
- `--backup BACKUP`: Existing empty directory that receives merged sources (required with --apply)
