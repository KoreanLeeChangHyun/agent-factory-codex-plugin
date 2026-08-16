---
name: projects
description: Maintain an AI-facing Project Skill in a target repository and serve its Human-facing local browser view. Use for project knowledge, progress, decisions, diagrams, or the local HTML/CSS/JavaScript viewer; use Specification only when the Human explicitly requests it.
---

# Agent Factory Projects

## Entry contract

Use the target project's Project Skill as the default AI-facing source for
project purpose, boundaries, decisions, progress, and diagram sources. Read
`references/project-skill.md` completely before creating or updating it.

Use `scripts/project.py` for Project Skill initialization and append-only
progress or decision recording. Do not make those records a precondition for
implementation or Human feedback. A Recording Agent performs them after the
work result and Human feedback.

Read `references/local-viewer.md` before serving the Human-facing view. The
viewer is read-only derived HTML, CSS, and JavaScript. It never owns project
facts and binds to loopback by default.

## Reference routing

- `references/project-skill.md`: Project Skill location, source ownership, and
  post-work recording contract.
- `references/local-viewer.md`: Local server, browser view, and diagram source
  contract.

## Assets and tools

`scripts/project.py` owns deterministic Project Skill initialization and
append-only recording. `scripts/viewer.py` serves `assets/viewer/` and a
read-only project API. The target Project Skill lives under the target project,
not in this plugin repository.
