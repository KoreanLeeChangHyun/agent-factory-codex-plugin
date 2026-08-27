---
name: specification
description: Create, edit, redesign, inspect, or verify refined Agent Factory Specifications and project-scoped Project Skills when the Human explicitly requests that document work. Do not use for raw Explorer material, ordinary project implementation, or operational Agent records.
---

# Agent Factory Specification

## Entry contract

Use this skill only for an explicit Human request to work on a Specification or
to create or maintain a project-scoped Project Skill. Preserve the requested
operation and its authorization boundary; inspection or verification alone does
not authorize edits.

Treat a Specification as one refined body of project knowledge with faithful
Human- and AI-facing representations. Ground every claim in explicit Human
instruction, accepted project decisions, or inspected project evidence. Keep
important provenance inspectable, and leave Human-owned priority, deadline,
owner, acceptance, risk acceptance, and completion state unresolved unless the
Human has decided them.

The Specification is the Human-readable HTML, CSS, and JavaScript document and
must be authored in Korean. Its paired Skill is the AI-readable representation
and is not required to be Korean. In this plugin repository the core pair is
owned by the distributed `skills/convention/` Skill; in a separate consumer project it may be a
project-scoped Project Skill below that project's `.codex/skills/`. Preserve technical
identifiers, code, paths, commands, proper nouns, and source quotations in
their original form when translation would reduce accuracy; this narrow
accuracy exception does not weaken the Korean-document requirement.

## Reference routing

- Read `references/specification-document.md` completely whenever creating,
  editing, redesigning, inspecting, or verifying a Specification. It defines
  the authoring workflow, packaged document template, paired representations,
  alignment requirements, and browser document.
- Read `references/project-skill.md` completely whenever the work creates,
  changes, inspects, or verifies the AI-facing representation or any explicitly
  requested project-scoped Project Skill. It defines the standard Skill layout,
  refined project references, and Skills Activity projection.

## Boundaries

Keep Explorer working material, refined Specification output, paired Skills,
and managed Agent session state in separate logical roles and resolved stores.
`.agent-factory/` is the current/default local document adapter, not a
universal canonical backend. An explicitly resolved project server, external
store, mounted filesystem, or other backend is permitted, but do not silently
choose, mirror, migrate, or claim implementation of one. Preserve lifecycle
stage, provenance, authority, isolation, semantic alignment, accessibility,
and security regardless of storage. Do not silently
promote Explorer material, recreate retired schema/profile/manager machinery,
or introduce Intake, Work Unit, Work Package, Project Core, Recording Agent, or
platform subagent concepts.

Preserve the common Specification shell. Locally materialized Human refined
documents live below `.agent-factory/information/refined/human/`, separate from
the shared UI below `.agent-factory/specification/common/`. Change only project-specific
Specification content and the corresponding Project Skill content needed by the
Human's request.

For a new Specification, use the reusable files in `assets/document/` as the
starting point and follow the copy-once and placeholder-refinement workflow in
`references/specification-document.md`. The template is a flexible baseline,
not a schema; adapt its sections to the grounded needs of the Specification.

## Local browser adapter

Use the internal standard-library-only initializer to install the common shell
and one project-root launcher. For first-time initialization, resolve the actual
loaded Specification Skill directory from this `SKILL.md`, then invoke its
initializer with the target Git root explicitly:

```bash
python3 <resolved-specification-skill>/scripts/serve.py \
  --project-root <target-git-root> init
```

The first command installs the reusable assets into
`<target-git-root>/.agent-factory/specification/common/` and copies the packaged
`assets/spec.sh` template to `<target-git-root>/spec.sh` once. The packaged file
is a project asset, not a Skill script to execute in place. Initialization never
changes an existing root `spec.sh`, including with `init --force`; force applies
only to differing common browser assets.

For normal Human use, launch from any current directory with:

```bash
<project-root>/spec.sh
# or, from the project root
./spec.sh --port 9000
```

The root launcher is for locally materialized UI and Human refined roots. It
resolves its own physical location, serves the allowlisted
`.agent-factory/specification/` UI and
`.agent-factory/information/refined/human/` Planning documents on loopback, and opens `/common/` in the default
browser. `--port <port>` or `-p <port>` overrides the default port `8000`.
`serve.py` remains the internal initializer and advanced safe server; place its
global `--project-root <target-git-root>` option before `init` or `serve`.
A server-hosted Specification is exposed by its selected host or adapter and
does not require the local `spec.sh` launcher remotely.
