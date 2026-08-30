# Gather OneDrive

Use `scripts/sync_onedrive.py` to collect one selected file or folder into the
resolved `onedrive` destination (default `source/microsoft/onedrive`). It uses
Microsoft Graph `/content` downloads and records source IDs, web URLs, hashes,
sizes, timestamps, and local paths in `index.jsonl`. It does not upload, move,
rename, share, or delete DriveItems.

## Connection And Authentication

Register a public-client/native application in Microsoft Entra, enable device
code flow, and put its application/client ID in `ONEDRIVE_CLIENT_ID`. The script
uses MSAL delegated device-code authentication with `Files.Read`. It requests
the broader `Files.Read.All` only when the Human intentionally passes
`--include-shared` to access shared files. Tenant admins may still require
consent according to policy. The refreshable MSAL cache defaults outside the
repository to `${XDG_CONFIG_HOME:-$HOME/.config}/agent-factory/onedrive-token-cache.json`
with user-only permissions.

Gather declares the selected item/folder/drive, recursion and count bounds,
`Files.Read` as the minimum scope, whether `Files.Read.All` and Human/admin
approval are actually required, and the read-only intent. Tool must report the
requested and granted scopes separately and must not widen them. The bundled
script's MSAL and token-cache behavior remains an observed implementation
coupling until concrete Tool connection/token and Gather capability/scope
interfaces exist and migration is separately authorized and verified.

See Microsoft's [delegated auth flow](https://learn.microsoft.com/en-us/graph/auth-v2-user),
[permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference),
and [DriveItem content download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0).

```bash
export ONEDRIVE_CLIENT_ID='application-client-id'
python <gather-skill-directory>/scripts/sync_onedrive.py \
  --path 'Projects/Example' --recursive --max-files 500
```

Alternatively select exactly one `--item-id`. Confirm the selection, recursion,
limit, requested permission, and resolved destination before authentication.
The script percent-encodes IDs as Graph path components and encodes each
`--path` component independently while preserving its `/` separators.
Do not use `--include-shared` unless shared-file collection is intended. For a
shared drive outside the user's own drive, pair it with an explicit
`--drive-id`; this deliberately selects the `/drives/{drive-id}` Graph route.
