# Processed Document

## Type contract

A Processed (가공문서) contains transformations or derived working knowledge,
including analysis, comparison, hypotheses, research results, interview
results, and conclusions. Processed material can be useful and well-supported,
but it is non-authoritative working knowledge and is not accepted or reconciled
Specification truth.

Under the current/default local adapter, active Processed Documents are
Markdown (`.md`). Processed is a logical, storage-independent Document type;
the Markdown convention does not make the type dependent on the local adapter.
Every immediate child directory below the local `document/processed/` root is
one Processed Document package. Its files and internal subdirectories are
representations within that package; do not add a producer, category, or legacy
wrapper layer. Preserved historical Inquery packages use explicit
`legacy-inquery-<legacy-id>` identities directly below the Processed root. They
remain Processed Documents, with legacy recorded as status/provenance metadata,
and are not active targets or format precedents.

## Relationships and provenance

Use the conceptual ordering `Original -> Processed -> Specification` only to
show possible derivation or evidence relationships. A Processed Document may
exist without an Original relationship or without producing a Specification.
Relationships may be absent, one-to-many, many-to-one, or many-to-many.

Preserve inspectable provenance for actual inputs, transformations, evidence,
and limitations. Keep observations, analysis, hypotheses, conclusions,
contradictions, and unresolved questions distinguishable. Do not infer
completeness, acceptance, authority, a required transition, or automatic
promotion from the Processed type.

Explorer may create Processed Documents while performing bounded evidence work
under Convention. Explorer does not accept or reconcile Specification truth.
