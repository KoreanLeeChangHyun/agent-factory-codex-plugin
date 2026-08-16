# Change Safety

## Intent Confirmation

Do not delay a bounded, reversible change for implementation details that can
be resolved from repository evidence. Ask first only when ambiguity materially
changes Human-visible behavior, data, security, scope, or an irreversible
action.

Before a materially broad or ambiguous edit:

1. Restate the requested change in 1-3 short sentences.
2. List explicit facts from the Human and inspected repository evidence.
3. List what is unspecified.
4. State the edit boundary: files or areas to touch, and files or areas not to
   touch.
5. Ask for confirmation when an unspecified item would materially change the
   requested outcome or cross a Human-owned decision boundary.

Ask before editing when:

- UI work has two or more materially different visible outcomes that repository
  evidence and the Human's request do not resolve.
- The target file, component, selector, route, API, artifact, or skill is not
  named.
- Unrelated uncommitted changes overlap files that must be touched and cannot be
  preserved safely.
- The change could require a commit, rollback, restart, migration, destructive
  command, or generated artifact update.

For UI work, use the fast Work Agent route. Preserve position, icon, visible
text, DOM structure, event behavior, keyboard behavior, data model,
persistence, and unrelated tests unless the bounded request requires a change.
Return the actual UI quickly for Human feedback.

## Change Safety

Human owner break-glass may bypass project-internal workflow procedures, but
it does not imply permission for a destructive or external action. Deletion,
overwriting or replacing uncommitted work, deployment, restart, and external
transmission must each be named explicitly with its target. Existing exact
confirmation requirements for destructive actions still apply. Tests and
verification commands require exact Human-requested commands even during
break-glass recovery.

- Do not roll back commits unless the Human explicitly asks for a commit
  rollback.
- Do not overwrite, restore, discard, reset, or replace uncommitted work unless
  the Human explicitly approves that exact file and operation.
- Even after the Human approves an operation that can remove or replace
  uncommitted work, ask for one more explicit confirmation before executing it.
- Do not treat a broken runtime state as permission to revert files.
- Before any operation that can remove or replace uncommitted changes, show the
  exact files and exact command or edit, then wait for Human approval.
- Prefer read-only diagnosis first: inspect status, diffs, logs, runtime state,
  browser errors, and tests before proposing any destructive or replacement
  action.
- If a file appears broken but contains uncommitted work, preserve it first and
  ask the Human how to proceed.

## Hard Stops

Stop and ask before editing when:

- No authoritative source supports a required external technology claim.
- Repository evidence contradicts the proposed design.
- The change would replace a domain model with an invented fallback, sentinel,
  pseudo-scope, cache key, or hidden global state.
- The implementation requires a broad architecture or workflow decision not
  recorded in the Specification, Work Unit, or Human instruction.
- The change can remove, overwrite, reset, or replace uncommitted work.
