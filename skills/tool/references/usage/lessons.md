# `lessons.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Required: `--project-root PROJECT_ROOT`, `action {check,record,resolve,retrieve,audit,candidate,evaluate,publish,sync,apply,retire,recover}`
One of: `--input` | `--input-json`
- `--documents-root DOCUMENTS_ROOT`: Physical workspace containing docs; runtime identity stays --project-root
- `--input INPUT`
- `--input-json INPUT_JSON`: Inline JSON payload; avoids temporary input files for read-only queries
