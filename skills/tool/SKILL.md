---
name: tool
description: Find which Agent Factory plugin script performs an operation and where its rules live. Use to choose a plugin tool, not for ordinary conversation or general-purpose CLIs.
metadata:
  specification-id: tool
---

# Agent Factory Tool

- `<plugin-root>` is the installed Agent Factory plugin directory that contains `skills/`,
  `runtime/` and `scripts/`; it is two levels above this `SKILL.md`.
- This is a catalog only. Before running a tool, follow the owning Skill's rules; they
  remain the single source for authority and failure handling.
- Run every tool as `python3 <plugin-root>/scripts/<script> ...`.
- Each script name links to its usage file with subcommands and arguments, generated from
  its `--help`. Read only the file (and subcommand section) for the tool you will run.

<a id="catalog"></a>

## 1. Plugin tools

| Script / usage | Operation | Rules |
|---|---|---|
| [`exec.py`](references/usage/exec.md) | One managed run | [Agent](../agent/SKILL.md) |
| [`coordination.py`](references/usage/coordination.md) | Append Main-owned contract control/decision records | [Coordination records](../agent/references/role-exceptions.md#coordination-records) |
| [`commit.py`](references/usage/commit.md) | Main-owned receipt-bound ordinary local commit | [Commit boundary](../agent/references/role-exceptions.md#ordinary-local-commit) |
| [`loop.py`](references/usage/loop.md) | Announced Work/Verification loop | [Agent](../agent/SKILL.md) |
| [`lessons.py`](references/usage/lessons.md) | Lessons and published rules | [Lessons](../document/references/lessons-learned.md#lifecycle-cli) |
| [`migrate_runtime_lessons.py`](references/usage/migrate_runtime_lessons.md) | Merge legacy runtime captures by signature | [Lessons](../document/references/lessons-learned.md#runtime-capture) |
| [`sync_documents.py`](references/usage/sync_documents.md) | Continuous host synchronization | [Host sync](../document/references/host-sync.md#continuous-codex-synchronization) |
| [`export_documents.py`](references/usage/export_documents.md) | One-time host export | [Export](../document/references/host-sync.md#explicit-codex-export) |
| [`catalog_documents.py`](references/usage/catalog_documents.md) | Live Document catalog | [Document](../document/SKILL.md) |
| [`search_documents.py`](references/usage/search_documents.md) | Search that catalog | [Document](../document/SKILL.md) |
| [`migrate_document_paths.py`](references/usage/migrate_document_paths.md) | Document layout migration and contract-listed moves | [Document](../document/SKILL.md) |
