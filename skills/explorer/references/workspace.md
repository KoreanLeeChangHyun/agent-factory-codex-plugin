# Explorer Workspace

## Identity and lifetime

One Explorer workspace belongs to one exploration topic and one managed
Explorer Agent session. Create it below:

```text
<project-root>/.agent-factory/explorer/<exploration-id>/
```

Choose a stable lowercase hyphen-case identifier from the assigned topic. On a
follow-up, resume the exact managed session and existing workspace instead of
creating a competing exploration. The workspace is temporary working state,
not a canonical project record.

## Information and provenance

Explorer may preserve source-faithful original information and create processed
information such as comparisons, analysis, hypotheses, and conclusions. Record
source identity, location, retrieval context, and relevant limitations closely
enough that the Main Agent or Human can inspect the evidence. Clearly label
inference and contradiction. Explorer never accepts refined project truth.

Use Markdown for investigation notes unless the evidence itself requires
another local format. Keep generated notes distinct from copied source
material. Do not make the workspace a conversation transcript or canonical
ledger.

## Authority

Reading, analysis, and evidence browsing within the delegated scope are
allowed. Explorer never runs project tests, validators, builds, servers,
runtime probes, or other verification commands. Main preserves explicit Human
authorization and dispatches a separate managed Verification Agent. Explorer
may analyze the returned evidence but cannot turn it into project acceptance.

Return Human-owned product, priority, approval, acceptance, and risk decisions
as unresolved. Do not edit refined Specifications or Project Skills merely
because exploration supports a conclusion.

Preserved legacy Inquery contents at
`.agent-factory/information/processed/legacy-inquery/` are historical,
read-only, evidence-only project data. Inspect them only when the request puts
that evidence in scope; never modify them or use them as an active workspace.
