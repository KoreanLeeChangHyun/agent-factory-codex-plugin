---
name: interview
description: Interview a Human adaptively to elicit tacit knowledge, material requirements, or decisions when an identified AI-Human information gap cannot be resolved from available context. Do not use for ordinary answers, external surveys, or one trivial clarification.
---

# Agent Factory Interview

## Entry contract

Use this Skill when the Main Agent must reduce a material information gap with
the Human in the current conversation. Do not launch an Exec Agent to
impersonate or replace the Human.

When external background evidence is needed to prepare the next useful
question or continue the Interview, Main may pause or sequence the Interview
while a managed Explorer Agent gathers that evidence, then integrate it and
resume the Human conversation. Explorer never impersonates or interviews the
Human. Keep Human statements, Explorer evidence, and Main interpretation
distinct.

Establish the purpose, known context, material gaps, constraints, and a
practical stop condition. Then ask the smallest useful set of focused, neutral
questions and adapt each follow-up to the Human's answers. The Human may skip,
defer, correct, or stop at any time. Do not solicit secrets, and ask for other
sensitive information only when it is necessary and authorized.

Read `references/conduct.md` before conducting the interview or presenting its
result. It defines adaptive conduct, evidence distinctions, stopping, and
result handling without imposing a fixed questionnaire or document schema.

## Information boundary

Interview produces processed information by default. Keep its result in the
conversation unless the Human explicitly requests a target or another
already-authorized owning workflow requires an artifact. Do not invent an
Interview storage root or automatically promote the result to refined
Specification truth or a Project Skill.
