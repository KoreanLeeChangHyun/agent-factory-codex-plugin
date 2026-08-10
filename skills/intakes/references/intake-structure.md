# Intake Ledger Contract

## Purpose

An Intake is the structured source record for one goal or topic. It records all
Human and Agent conversation, interviews, web searches, internal analysis,
user research, observations, decisions, corrections, and other discovery
activity within that boundary. The Main Agent decides the topic boundary unless
the Human explicitly defines it. Explicit Human conditions always take priority.

Intake is not a Specification and not an execution unit. It has no lifecycle,
readiness state, required synthesis sections, table of contents, or completion
gate. A renderer may sort, filter, group, or present the canonical JSON without
creating another canonical Intake artifact.

## Package

```text
<project-root>/.agent-factory/intakes/<intake-id>/
  data/metadata.json
  data/entries/<entry-id>.json
  blocks/index.json
  blocks/**
```

`metadata.json` owns identity, project, topic, versions, timestamps, language,
provenance, artifact relations, and the optional manager-owned operational
Agent session binding. It contains no lifecycle, readiness, title, theme, or
presentation data.

Each entry file records:

```json
{
  "id": "stable-entry-id",
  "sequence": 1,
  "recordedAt": "2026-08-11T00:00:00+00:00",
  "occurredAt": "2026-08-11T00:00:00+00:00",
  "actor": {"type": "human", "id": "optional-id"},
  "activity": "user-input",
  "content": {},
  "attributes": {},
  "sourceRefs": [],
  "blockRefs": [],
  "relations": []
}
```

The manager owns `sequence` and `recordedAt`. `occurredAt`, attributes,
references, blocks, and relations are optional. Activity names are extensible
kebab-case values; capability references define their normal values.

## Append-only semantics

Entries are append-only. Never replace an existing entry to make the record
cleaner. Add a new entry with a relation such as `corrects`, `clarifies`,
`responds-to`, or `derived-from`. Keep facts, statements, observations,
interpretations, and decisions distinguishable in entry content or activity.

The append-only rule is logical, not a claim that personal data must be retained
forever. Apply project privacy, deletion, retention, and access-control policy.
Package deletion remains an explicit manager operation.

## References

Specification and Work Unit artifacts reference the Intake package root and
the exact entry ids they used. A Specification is optional. A Work Unit may be
created directly from sufficient Intake entries, and the Main Agent owns that
sufficiency judgment unless the Human specifies a condition.

## Validation

Validation checks metadata and entry schemas, canonical file names, unique and
contiguous manager-owned sequence values, resolvable entry relations, safe and
resolvable typed paths, and exact registered block integrity. Full validation
recomputes block hashes. Validation proves record integrity, not readiness or
semantic completion.
