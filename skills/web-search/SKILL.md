---
name: web-search
description: Use when Codex performs web search, external-source verification, comparison research, recommendation evidence, or external published-source investigation for Agent Factory Intake. Records source-backed findings in the active canonical Intake package and ranks web sources by authority-first tiers; use user-research instead for direct observation or study of users and operators.
---

# Agent Factory Web Search

Use this skill for external web search and source verification within an active
Intake. Route internal code, database, data, configuration, log, test, and
runtime investigation to `analysis`. Route direct observation, contextual
inquiry, workflow shadowing, usability sessions, and consented participant
session review to `user-research`. A published user-research report found on the
web remains web evidence; conducting or reviewing a participant study does not.

## Storage

- Record each external source and finding in the active Intake package's
  `evidence-and-findings` section through the sibling Intake manager's
  `section-item-put` command, normally with kind `web-evidence`.
- `web-evidence` satisfies the Intake profile's `evidence` family; do not add a
  duplicate generic `evidence` item only for readiness.
- Do not create a separate Markdown, HTML, or JSON web-search source of truth.
- Put non-JSON supporting material under the Intake package's `blocks/`
  directory through the manager's `block-put` command.
- Keep findings traceable into their owning requirement, decision,
  specification-impact, and Work Unit basis items instead of copying them into
  competing records.
- Run the Intake manager's separate `validate` command after every update.

Resolve the sibling manager from the installed Plugin skills root as
`<agent-factory-skills-root>/intake/scripts/intake.py`. Do not resolve it
relative to the shell working directory or the `web-search` skill directory.

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

Each `web-evidence` item records `title`, `url`, `authorityTier`, `freshness`,
`retrievedAt`, `findings`, and any `limitations` in its `content` object. Put
cross-source recommendations, assumptions, conflicts, and open items in their
owning Intake sections.

Apply it with `section-item-put <package> evidence-and-findings --value-file
<item.json>`, then run `validate`.

## Output

State the Intake id, highest source tier used, whether the conclusion is
supported, partial, or blocked, and any unresolved item or Human decision.
