# `sync_documents.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Required: `--project-root PROJECT_ROOT`
One of: `--reconcile` | `--check`
- `--reconcile`: Back up conflicting or interrupted output, then rebuild it from docs/skills.
- `--check`: Report hosts that differ from docs/skills; exit 1 when any differs. Changes nothing.
