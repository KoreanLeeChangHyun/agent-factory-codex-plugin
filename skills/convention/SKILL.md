---
name: convention
description: Apply shared communication, Human-decision, development, testing, visual, exploration and interview conventions. Use agent for managed execution and document for document writing, storage and synchronization.
metadata:
  specification-id: convention
---

# Agent Factory Convention

<a id="ownership"></a>

## 1. Ownership

| Task | Owning Skill |
|---|---|
| Managed roles, execution modes, sessions and receipts | [Agent](../agent/SKILL.md) |
| Communication, Human decisions, development, testing, exploration and interview | Convention |
| Document types, writing, packages, storage and synchronization | [Document](../document/SKILL.md) |
| Standalone generated files outside Documents | Convention [Artifacts](#artifacts) |

- Select guidance for the requested operation; read only the relevant references.
- Apply the project's current facts, rules and designs alongside that guidance.
- Resolve installed Skills through the host; similarly named project files are not replacements.
- Research and Interview are Convention activities, not additional Skills or roles.
- Project guidance grants no additional execution or publication authority.
- Whenever an error or observed Human/AI judgment difference occurs during Agent work, apply the mandatory
  [Lessons Learned recording contract](../document/references/lessons-learned.md).

<a id="human-communication"></a>

## 2. Human communication

- Follow the mandatory [respectful-register contract — `references/communication.md`](references/communication.md). Read it when needed if it is not already supplied in
  the current prompt or context; following the contract does not require a file read
  before each message.

<a id="human-decisions"></a>

## 3. Human decisions and authority

- A decision is explicit when stated by the Human or unambiguously resolved by an
  accepted Specification, including requirements, choices, scope and acceptance criteria.
- Resolve genuinely required Human-owned decisions before the affected action.
  Never invent a decision or present an assumption as one.
- Silence, ambiguity, convention, precedent, likely preference and lack of objection
  are not decisions. Inspection supplies facts, not Human authority.
- Capability availability grants no additional scope or mutation authority.
- Source or contract availability proves no deployment, registration or completed migration.
- Required priority, deadlines, ownership, acceptance and risk decisions remain Human-owned.
- Credential access, data retention, deletion and conflicts require owning authority.
- Follow [Agent role responsibilities](../agent/SKILL.md#delegation) for raising decision gaps;
  preserve the active execution route and approval policy.

<a id="research"></a>

## 4. Research and evidence

- Investigate web, code, Documents and data within the requested question, scope,
  constraints and completion criteria. Research creates no separate role or execution route.
- Preserve source identity and location, collection context, fidelity and limitations.
- Distinguish observations, analysis, hypotheses, conclusions, contradictions and
  unresolved gaps. Findings do not themselves authorize decisions or change accepted Specifications.
- When checkable data exists, verify distribution, ratio or primary-cause claims before
  stating them, and never base a recommendation on an unverified estimate. If checking
  is blocked (e.g. permission denied), label the estimate, its basis and how to verify it.
- Follow [Agent](../agent/SKILL.md) for execution roles and authority, and
  [Testing](references/testing.md#agent-graph-boundary) for checks under the captured route.
- Use [Document](../document/SKILL.md#document-package) for durable evidence and analysis,
  including Original/Refined classification, representation and storage. Refined retains
  the compatible `processed` metadata type. Temporary
  material stays within its producing task or run; create no separate research storage root.

<a id="references"></a>

## 5. References

- Read only the reference matching the next operation; reuse guidance already in context.

<a id="core-and-development"></a>

### 5.1. Communication and development

- [`references/development.md#code-ownership-and-minimal-design`](references/development.md#code-ownership-and-minimal-design): required code ownership,
  reuse and minimal-design rules, plus shared checkout boundaries, technical documentation,
  comments and commits.
- `references/work-contracts.md`: task-list contracts, required/optional fields, file-level
  change boundaries, amendments and result reconciliation. Use when preparing or executing a work contract.
- `references/testing.md`: read before authoring or changing tests; covers meaningful
  coverage, full-suite cost, reusable preparation, bounded waits, selection, parallel
  execution and execution boundaries.
- `references/libraries.md`: dependencies, renderers.

<a id="theme-and-knowledge"></a>

### 5.2. Theme and knowledge

- `references/theme.md`: mandatory design/theme consistency, stable tab geometry,
  visual acceptance checks, browser documents and SVG icons. Read before any UI
  creation or modification, including layout-only changes.
- `references/diagrams.md`: ERD, behavior and sequence diagrams.
- `references/interview.md`: Main's Human elicitation.

<a id="bootstrap"></a>

## 6. Bootstrap

- Copy `assets/AGENTS.md` only when authorized and project `AGENTS.md` is absent.
- Preserve existing files. The manifest does not inject project guidance.
- Bootstrap through the template; no local initializer is available.

<a id="artifacts"></a>

## 7. Artifacts

- **Mandatory:** never create a directory the Human has not agreed to; put standalone generated
  deliverables in `docs/artifact/<category>/<task-or-topic>/` unless the Human names another location.
- Route canonical Documents through [Document's directory map](../document/references/layout.md).
- Before creating standalone HTML, SVG, images, screenshots or other non-Document
  deliverables, read [artifact storage and delivery — `references/artifacts.md`](references/artifacts.md).
