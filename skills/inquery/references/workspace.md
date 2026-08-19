# Inquiry Workspace

## Ownership

An Inquiry workspace belongs to one Inquiry Agent and one uncertain topic. The
Agent may create, replace, reorganize, and remove its own temporary working
files as needed for that Inquiry. It must not write into another Inquiry's
directory.

Use a stable lowercase identifier for `<inquiry-id>`. Resolve every write below
the selected Inquiry root, reject traversal outside that root, and do not
follow a symlink that escapes it.

## Contents

The workspace has no mandatory internal schema. Choose filenames and
subdirectories that help the active Inquiry. Typical contents may include:

- unrefined Markdown notes and working conclusions;
- copied or extracted source material;
- temporary data and comparison tables;
- authorized experimental code and observations;
- intermediate outputs needed by later turns in the same session.

AI-generated Inquiry documents use Markdown. Do not require the Agent to
record every Human conversation turn, mirror runtime event streams, or maintain
an append-only ledger.

## Document boundary

Inquiry material is temporary and optimized primarily for AI use. It may be
incomplete, contradictory, exploratory, or superseded by later work. Clearly
label uncertainty instead of polishing it into an authoritative artifact.

Do not store refined Human-facing Specification HTML, CSS, or JavaScript in the
Inquiry workspace. Do not store a refined Project Skill there. Do not treat an
Inquiry file as accepted project truth merely because it exists.

## Runtime relationship

The managed Agent session owns operational continuity. Keep its exact Codex
session identifier and run state below `.agent-factory/agent/`. Resume the
same session for follow-up work on the same Inquiry so the Agent can reuse both
conversation context and workspace files.

The Inquiry workspace must remain useful even when individual run result files
are not loaded, but it does not replace the runtime's request, state, event,
heartbeat, or result files.

## Cleanup

Do not assume temporary means disposable without authority. Remove an Inquiry
workspace only when the Human explicitly requests that exact Inquiry cleanup.
Do not automatically preserve or promote its content elsewhere before cleanup.
