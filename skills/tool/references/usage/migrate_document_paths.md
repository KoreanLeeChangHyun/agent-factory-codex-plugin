# `migrate_document_paths.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Required: `--project-root PROJECT_ROOT`
One of: `--backup` | `--apply`
- `--operations OPERATIONS`: Contract-listed file moves (required without --storage-layout)
- `--storage-layout`: Migrate legacy JSON lessons and flat refined packages
- `--documents-root DOCUMENTS_ROOT`: Physical workspace containing docs; runtime identity stays --project-root
- `--language LANGUAGE`: Selected lesson body language; preserves original language and quoted source text
- `--classifications CLASSIFICATIONS`: JSON mapping of source package paths to categories after inspecting their bodies
- `--exclude-path EXCLUDE_PATH`: Preserve a dirty/untracked document or package; repeat as needed
- `--task-id TASK_ID`
- `--backup`: Create and verify a backup after preview.
- `--apply`: Apply contract moves after backup, or create a recoverable storage-layout backup and apply.
- `--backup-dir BACKUP_DIR`
