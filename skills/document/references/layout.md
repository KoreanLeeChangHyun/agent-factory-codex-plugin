# Project document layout

## 1. Directory map

- `<project-root>/docs/` is the canonical project document root. Create only the
  locations needed by the task; this map is not a request to scaffold every directory.
- Type-specific rules linked below own document meaning and metadata. Artifact purpose
  and delivery rules belong to [Convention](../../convention/references/artifacts.md).

```text
docs/
├── original/<category>[-<domain>]-<name>/metadata.yaml
├── refined/
│   ├── analysis/<topic>/SKILL.md
│   ├── research/<topic>/SKILL.md
│   ├── interview/<topic>/SKILL.md
│   ├── comparison/<topic>/SKILL.md
│   └── history/<topic>/SKILL.md
├── skills/<category>[-<domain>]-<name>/SKILL.md
├── progress/<contract-id>/
│   ├── progress.md
│   ├── contract-v<N>.md
│   └── <explicitly linked contract attachments>
├── lessons-learned/
│   ├── errors/<readable-name>.md
│   └── judgment-differences/<readable-name>.md
└── artifact/
    ├── preview/<task-or-topic>/
    ├── evidence/<task-or-topic>/
    ├── media/<task-or-topic>/
    └── release/<version>/
```

- Refined and Specification packages may contain linked `references/` and `assets/`.
  Do not repeat a Refined category prefix in its topic directory.
- Document-owned assets stay in their package, even when they are images or JSON.
  Standalone deliverables use `artifact/` without a required `SKILL.md` or metadata wrapper.

## 2. Routing and authority

| Content | Owner |
|---|---|
| External source metadata and links, without copied source bodies | [Original](original.md) |
| Analysis, research, interview evidence, comparisons and historical records | [Refined](refined.md) |
| Explicitly authorized current facts, rules and designs | [Specification](specification.md) |
| Bound contract versions, execution records and progress | [Progress](progress.md) |
| Error causes, remedies and Human/AI judgment differences | [Lessons Learned](lessons-learned.md) |
| Standalone previews, retained evidence, reusable media and release bundles | [Artifacts](../../convention/references/artifacts.md) |

- Preserve the source's language, identity, provenance and authority. A move, a
  `SKILL.md` filename or a report calling a decision final does not promote it to a Specification.
- Use the existing Document catalog and search for canonical Documents. Artifacts
  are not a Document type; do not add a parallel README index or database for this layout.
- Expose only `docs/skills/` to host Skill directories through [managed synchronization](host-sync.md).
  Host copies are derived; installed plugin capabilities remain outside project Documents.

## 3. Runtime boundary and migration

- Store lesson narrative once in Markdown. Machine metadata and recovery state live
  in the runtime resolver's project storage, including
  `<runtime-home>/projects/<project-id>/lessons-learned/<record-id>.json`.
  Honor the registered project identity and `AGENT_FACTORY_HOME`; do not hardcode a home path.
- Runtime sessions, locks, caches, temporary logs and scratch files do not belong in
  `docs/`. Use the producing run's storage or system temporary storage.
- For isolated Documents, `--project-root` identifies the original project;
  `--documents-root` is the physical workspace containing `docs/`.
- Existing layouts remain historical input until migration is authorized. Follow
  [Document migration](host-sync.md#document-layout-migration) for lesson and Refined
  conversion, and [artifact reorganization](../../convention/references/artifacts.md)
  for deliverables. Preserve backups, histories, attachments and incoming links.
