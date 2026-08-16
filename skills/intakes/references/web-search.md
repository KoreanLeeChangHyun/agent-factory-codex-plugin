# Agent Factory Web Search

Use this capability for external web search and source verification within an active
Intake. Route internal code, database, data, configuration, log, test, and
runtime investigation to `references/analysis.md`. Route direct observation,
contextual inquiry, workflow shadowing, usability sessions, and consented
participant session review to `references/user-research.md`. A published user
research report found on the web remains web evidence; conducting or reviewing
a participant study does not.

## Storage

- Append each external search activity and source-backed finding through the
  sibling Intake manager's `entry-put` command with activity `web-search`.
- Do not create a separate Markdown, HTML, or JSON intakes source of truth.
- Put non-JSON supporting material under the Intake package's `blocks/`
  directory through the manager's `block-put` command.
- Keep decisions, optional Specifications, and Work Units traceable to the
  exact web-search entry ids.
- Rely on manager-internal mutation validation. Run separate `validate` only
  when the Human explicitly requests verification.

Resolve the sibling manager from the installed Plugin skills root as
`<agent-factory-skills-root>/intakes/scripts/intake.py`. Do not resolve it
relative to the shell working directory or the `intakes` skill directory.

## Web Source Tiers

Rank sources by authority and source proximity first. Freshness is secondary
unless the topic is time-sensitive.

- `T1 authoritative primary`: official standards, specifications, laws,
  regulations, government sources, official product documentation, maintainer
  documentation, official source repositories, release notes, changelogs, and
  API references for the product or technology being checked.
- `T2 primary expert`: peer-reviewed papers, published research, official
  engineering blogs from the organization that owns the system being described,
  reputable institutional publications, and major vendor docs when they describe
  their own platform or service.
- `T3 reputable secondary`: established technical publications, books, vendor
  comparison pages, and explainers that cite primary sources clearly.
- `T4 community or field report`: issue threads, forum discussions, Q&A,
  personal blogs, conference notes, benchmark posts, and migration reports.
- `T5 weak or unusable`: unattributed content, SEO summaries, AI-generated
  pages, copied material, undated pages, stale pages contradicted by higher-tier
  sources, or sources with unclear authorship.

Use the highest available tier that directly answers the question. Do not let a
newer low-tier source overrule an older still-current T1/T2 source.

## Freshness

Record freshness separately from authority:

- `F5`: published or updated within 12 months, or explicitly versioned for the
  current product/API/version.
- `F4`: published or updated within 24 months.
- `F3`: older than 24 months but still consistent with current T1/T2 sources.
- `F2`: older source with uncertain current applicability.
- `F1`: stale, contradicted, undated, or likely obsolete.

For time-sensitive topics such as pricing, laws, APIs, dependencies, models,
security advisories, schedules, market data, or product availability, verify the
latest available T1/T2 source before recording a conclusion.

## Search Rules

- Prefer T1 sources. Use T2 when T1 is unavailable or insufficient.
- Use T3/T4 only as context, comparison, field evidence, or to identify
  questions that need primary-source confirmation.
- Do not base final architecture, legal, medical, security, financial, API, or
  dependency decisions on T3/T4/T5 evidence alone.
- Exclude T5 from conclusions unless recording it as rejected evidence.
- Decision-affecting search must cover the selected option, major alternatives,
  limitations, compatibility, support status, and current state.
- When feasible, compare at least two independent T1/T2 sources. If only one
  authoritative source exists, record that limitation explicitly.
- Separate facts, source-backed findings, recommendations, assumptions, and
  unresolved items.
- Cite source URLs in the Intake and summarize only the evidence used.

## Canonical Record Shape

Each `web-search` entry records `title`, `url`, `authorityTier`, `freshness`,
`retrievedAt`, `findings`, and any `limitations` in its `content` object. Put
cross-source recommendations, assumptions, conflicts, and open items as
separate related Intake entries.

Apply it with `entry-put <package>` and typed data arguments. The manager
constructs and validates JSON; do not create a JSON value file. Run separate
`validate` only when the Human explicitly requests verification.

## Output

State the Intake id and appended entry id, highest source tier used, whether the conclusion is
supported, partial, or blocked, and any unresolved item or Human decision.
