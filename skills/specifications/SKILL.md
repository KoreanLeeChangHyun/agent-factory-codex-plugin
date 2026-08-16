---
name: specifications
description: Manage optional canonical Agent Factory Specifications and Specification-owned diagrams only when the Human explicitly requests that artifact route.
---

# Agent Factory Specifications

## Entry contract

Use this skill only when the Human explicitly requests a Specification,
Project Core, Design Report, or Specification-owned diagram. Use `projects`
for the default Project Skill and local browser diagrams. Read every applicable
reference before acting. Canonical Specification writes must use
`scripts/specification.py`.

## Reference routing

- `references/specification-management.md`: Create, validate, and align canonical Specification packages for external rendering.
- `references/diagram.md`: Choose, model, render, and review architecture, sequence, data, workflow, state, deployment, or UI-flow diagrams.

## Assets and tools

`scripts/specification.py` is the only canonical Specification manager.
`scripts/requirements.txt` declares its dependencies; `assets/` owns profiles
and schemas; `tests/` owns regression coverage. The external viewer owns both
canonical Specification package rendering and Human-facing Design Report
rendering.
