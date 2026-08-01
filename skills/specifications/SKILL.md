---
name: specifications
description: Manage canonical Agent Factory Specifications and their diagrams.
---

# Agent Factory Specifications

## Entry contract

Use this skill when Intake or scoped execution requires Specification,
Project Core, Design Report, or diagram work. Read every applicable reference
before acting. Canonical Specification writes must use
`scripts/specification.py`.

## Reference routing

- `references/specification-management.md`: Create, validate, align, and render canonical Specification packages.
- `references/diagram.md`: Choose, model, render, and review architecture, sequence, data, workflow, state, deployment, or UI-flow diagrams.

## Assets and tools

`scripts/specification.py` is the only canonical Specification manager.
`scripts/requirements.txt` declares its dependencies; `assets/` owns profiles,
schemas, and report rendering resources; `tests/` owns regression coverage.
