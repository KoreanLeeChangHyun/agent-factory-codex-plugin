# Session State Model

## Agent Factory State Model Rule

For Agent Factory session UI work, preserve this ownership chain unless the
Human explicitly changes it:

```text
Session -> DOM -> State
```

- A session owns its DOM.
- The session-owned DOM owns visible message, composer, loading, planning, and
  status surfaces for that session.
- State is keyed by the real session id or an explicit pending session id.
- No fake fallback scope may stand in for a missing session.
- If no session is active, no session-owned message, composer, loading, or
  status surface should be visible.

Do not introduce new sentinel ids, pseudo-session ids, pseudo-scopes, or hidden
default session names to make code paths easier.
