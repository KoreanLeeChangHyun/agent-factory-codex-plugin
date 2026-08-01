# Runtime Safety

## Runtime Restart Safety

- Do not restart the Agent Factory server, frontend, backend, supervisor, or
  all runtime targets on your own.
- Runtime restart is allowed only when the Human explicitly asks for server
  restart.
- Even after the Human explicitly asks for server restart, ask for one more explicit confirmation
  before executing any restart command, API call, button
  flow, script, or supervisor operation.
- If the Human does not provide the second confirmation, do not restart.

## Frontend Cache And Verification

- When changing frontend JavaScript modules while an existing Agent Factory
  frontend server is running, do not assume the browser or Vite module graph has
  loaded the newest file.
- Do not restart the frontend server just to clear module cache unless the
  Human explicitly asks for restart and gives the required second confirmation.
- Prefer read-only cache diagnosis first: inspect the served module with
  `curl`, compare it against the local file, and check whether an import chain
  uses query-string cache keys.
- If a changed module is imported through existing query-string cache keys,
  update only the necessary import chain from the changed module back to the
  frontend entrypoint.
- Keep cache-key updates scoped to the touched behavior. Do not rename broad
  cache keys or sweep unrelated imports.
- For small frontend UI behavior changes, default to focused verification:
  syntax checks for touched JavaScript, relevant minimal-app boundary checks,
  and the Playwright spec or grep that covers the changed behavior.
- Run full `npm run check`, full E2E, mobile checks, or screenshot checks only
  when the change touches shared runtime wiring, global layout/CSS, broad API
  behavior, or when the Human asks for full verification.
- If focused verification passes but a broader check fails in an unrelated
  area, record the exact failing command, failing file or assertion, and whether
  the failure is in files touched by the current work. Do not fix unrelated
  failures unless the Human approves that expanded scope.
