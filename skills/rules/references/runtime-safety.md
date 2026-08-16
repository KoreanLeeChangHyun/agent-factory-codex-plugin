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
- When the Human explicitly requests cache diagnosis, inspect the served module,
  compare it against the local file, and check whether an import chain uses
  query-string cache keys.
- If a changed module is imported through existing query-string cache keys,
  update only the necessary import chain from the changed module back to the
  frontend entrypoint.
- Keep cache-key updates scoped to the touched behavior. Do not rename broad
  cache keys or sweep unrelated imports.
- For frontend UI changes, run syntax checks, boundary checks, Playwright,
  screenshots, or other verification only when the Human explicitly requests
  verification. Use exact supplied commands unchanged or select the smallest
  bounded commands from repository evidence. Return the changed UI for fast
  Human feedback instead.
- Never infer full `npm run check`, E2E, mobile, or screenshot authority from
  shared runtime wiring, global layout/CSS, or broad API impact.
- If focused verification passes but a broader check fails in an unrelated
  area, record the exact failing command, failing file or assertion, and whether
  the failure is in files touched by the current work. Do not fix unrelated
  failures unless the Human approves that expanded scope.
