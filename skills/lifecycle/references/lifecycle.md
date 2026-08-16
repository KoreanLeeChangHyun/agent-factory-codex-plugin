# Lifecycle Reference

## Feedback-first loop

The Human owns task size and final evaluation. Favor short iterations over a
large inferred plan:

1. Human requests the next bounded change.
2. Main Agent resolves the smallest relevant evidence and delegates to one
   Work Agent.
3. Work Agent changes the primary Git workspace and returns a compact receipt.
4. Main Agent immediately presents changed paths, limitations, and exact test
   evidence or `tests not run`.
5. Human accepts, rejects, or provides the next correction.
6. Main Agent starts a Recording Agent for the previous result in the
   background. When safe, the next Work Agent runs without waiting for it.

Do not turn feedback into a readiness interview, artifact approval, or broad
up-front specification. Ask one focused question only when a Human-owned
decision materially changes the result.

## Recording

Recording consumes the completed Work Agent receipt and subsequent Human
feedback. It updates the target Project Skill with accepted decisions and
completed-work facts. It does not review, test, fix, commit, or delay the work.

If recording fails, report the missing record separately. Do not roll back or
invalidate implementation.

## Optional artifact lifecycle

Intake, Specification, Work Unit, Work Package, and linked worktree flows remain
available for explicit Human selection. Their manager-owned schemas and safety
contracts remain authoritative after selection. No artifact's mere existence
activates its lifecycle.

For an explicitly requested Work Unit or Work Package, use the existing Goal
launcher and advanced role chain. The Test Agent still runs only exact
Human-authorized commands. Worktree preparation occurs only when the Human also
selected worktree mode. Promotion, push, PR, deployment, restart, and branch
deletion remain separate explicit actions.

## Human-facing project view

The local Viewer derives its page at request time from the target Project Skill
and read-only Git evidence. Diagram HTML, CSS, JavaScript, and SVG are
presentation. AI-readable Skill references and diagram sources remain the
project source.
