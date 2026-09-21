# Progress writing

<a id="authority-and-scope"></a>

## 1. Authority and scope

- Apply the shared [Document requirements](../SKILL.md).
- Use Progress for task progress, current status, completed work, blockers and
  remaining work. Use Processed for research, analysis and reusable working knowledge.
- A Progress document records observations; it grants no execution, approval or
  Specification authority. Link existing task/run evidence when available rather
  than treating the document as the runtime state store.
- Preserve existing Processed `process` documents unless migration is explicitly
  requested. New progress records use this type.

<a id="package-and-metadata"></a>

## 2. Package and metadata

- Store the document at `docs/progress/<category>[-<domain>]-<name>/SKILL.md`,
  with optional `assets/`, using the shared language, structure and asset rules.
- Record `document-type: progress`, `category`, nullable `domain`, `name`,
  `language` and actual provenance in YAML front matter.
- Use `status` for a current snapshot and `worklog` for chronological progress.
- Catalog and search discover Progress documents; they are not activated as Skills
  or exported to `.codex/skills/`.

<a id="writing"></a>

## 3. Writing

- Identify the task or scope and the observation date so readers can assess freshness.
- Record relevant completed work, current work, remaining work and blockers.
- Distinguish reported completion from checks actually performed. Link evidence
  where available and retain unresolved decisions without inventing outcomes.
- For a status snapshot, update the current state. For a worklog, retain dated
  entries so earlier observations are not presented as the current state.
