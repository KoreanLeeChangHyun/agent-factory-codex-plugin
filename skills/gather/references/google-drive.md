# Gather Google Drive

## Overview

Use this capability to gather Google Drive files into a local workspace or
explain how to share Drive access for that purpose. Default the local destination to
`source/google/drive` under the Git project root unless
`<git-project-root>/.agent-factory/sync.json` or the user gives a different
path.

Keep the workflow read-only by default. Do not upload, delete, or modify Drive
files unless the user explicitly asks for write-back behavior.

Prefer the bundled read-only API sync for repeatable bounded collection. Drive
for desktop, rclone, and manual download remain useful alternatives.

## Workspace Convention

- Resolve the destination through `gather/scripts/sync.py` before any copy,
  import, or mirror. It applies explicit input, the `google-drive` entry in
  `.agent-factory/sync.json`, then the `source/google/drive` default.
- Put original Drive materials under the normalized resolved destination.
- Keep credentials and tokens private and outside the repository, for example:
  - `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/oauth-client.json`
  - `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/drive-token.json`
  - `${XDG_CONFIG_HOME:-$HOME/.config}/rclone/rclone.conf`
- Do not recreate legacy repository-local credential paths unless the user
  explicitly asks:
  - `tools/google-drive-credentials.json`
  - `tools/.google-drive-token.json`
  - `tools/google-oauth-client-secret.json`
- Do not recreate a root `drive_downloads/` folder unless the user explicitly
  asks for compatibility with older scripts.

## Method Selection

Prefer methods in this order:

1. **Google Drive for desktop**: Use when the user can sign in locally and the
   target files appear in Finder or File Explorer. This avoids creating a
   Google Cloud project.
2. **rclone**: Use when the user wants a repeatable CLI sync or Drive for
   desktop does not expose the needed files. Configure rclone with browser auth
   and read-only scope when possible. Leave `client_id` and `client_secret`
   blank unless the user wants a dedicated Google Cloud project for quota or
   policy reasons.
3. **Manual browser download**: Use for one-off small transfers or when API or
   CLI setup is not worth it.
4. **Bundled OAuth/API importer**: Use `scripts/sync_google_drive.py`. Confirm it uses
   `https://www.googleapis.com/auth/drive.readonly` for imports and stores
   credentials outside committed files.
5. **Service account**: Use for automation when a Google Workspace admin or
   folder owner can share a folder or shared drive with the service account
   email. Do not assume a service account can see a user's My Drive files.

## Sharing And Access Choices

- **Browser sharing**: Use when a human only needs to grant access to another
  human. Share the folder or file in Drive with a Google account or group and
  choose Viewer, Commenter, or Editor.
- **OAuth user consent**: Use when Codex or a local script must list or
  download files visible to a real user account. Prefer read-only scopes.
- **Hosted OAuth connector or Google Picker**: Use only after checking scopes,
  token storage, shared drive support, recursive import support, and export
  formats. Avoid third-party hosted connectors for confidential client data
  unless the user approves them.
- **Shared drive membership**: Prefer for team-owned assets that should not
  depend on one person's My Drive ownership.
- **Link-based download**: Use only for public or "anyone with the link" files
  and simple one-file transfers. It is brittle for folders, restricted files,
  large files, and Google Docs/Sheets/Slides exports.

## Environment Probe

Start with non-destructive checks:

```bash
python <gather-skill-directory>/scripts/sync.py resolve --source google-drive
find "$HOME/Library/CloudStorage" -maxdepth 3 -type d 2>/dev/null | sed -n '1,120p'
command -v rclone && rclone version
test -d "<resolved-drive-destination>" && find "<resolved-drive-destination>" -type f | wc -l || true
test -d "<resolved-drive-destination>" && du -sh "<resolved-drive-destination>" || true
rg -n "google/drive|drive.readonly|Google Drive API|rclone|source/google/drive" .
```

Interpretation:

- If `~/Library/CloudStorage` only shows the base directory, Drive for desktop
  is not currently exposing a usable local Drive mount.
- If `rclone` is missing, do not use the rclone path until it is installed.
- If `source/google/drive` already contains files, treat it as the current
  local source snapshot and avoid overwriting it until the remote source is
  confirmed.
- If repository-local Google Drive API scripts exist, treat them as legacy
  project tooling unless the user asks to use them or no better method is
  available.

## Safety Rules

- Use `gather/scripts/sync.py` to inspect or set project overrides; do not edit
  `.agent-factory/sync.json` directly.
- Check the printed normalized resolved destination before creating directories
  or copying data.
- Store local Drive materials under the resolved destination.
- Keep credentials, tokens, and rclone config out of git.
- Prefer read-only scopes and copy/sync from Drive to local only.
- Before running a destructive local sync such as `rsync --delete`,
  `rclone sync`, or local cleanup, follow `rules/references/change-safety.md`:
  show the exact source, destination, affected files, and exact command, obtain
  Human approval, then obtain one additional explicit confirmation immediately
  before execution.
- Do not delete cloud files. Local cleanup remains limited to the confirmed
  destination directory and still requires both confirmations above.
- If the Drive contains confidential client data, avoid third-party hosted
  connector services unless the user explicitly approves them.
- For Google Workspace domain-wide delegation, require admin approval and use
  it only when the organization explicitly wants impersonation.

## Google Drive For Desktop

Use this path when the user's account is signed in to Google Drive for desktop.

1. Confirm the app is installed and signed in with the account that has access.
2. Locate the mounted Drive folder.
   - On macOS, check:
     `~/Library/CloudStorage/`
   - Also inspect Finder's Google Drive entry if the exact path is unclear.
3. Identify whether the files are under `My Drive`, `Shared drives`, or another
   mounted Drive section.
4. Copy into the workspace:

```bash
mkdir -p "<resolved-drive-destination>"
rsync -a "<mounted-drive-path>/" "<resolved-drive-destination>/"
```

5. For a mirror of the mounted source into the local destination, use delete
   only after satisfying the two-confirmation safety rule above:

```bash
rsync -a --delete "<mounted-drive-path>/" "<resolved-drive-destination>/"
```

Use this method for shared drives when they appear locally. If the target is
only visible in Drive web under "Shared with me" and not in Finder, use rclone
or ask the user to expose the folder through Drive for desktop.

## Rclone

Use rclone when a CLI workflow is better than Finder-based copying.

Check installation:

```bash
rclone version
```

Create or inspect a remote:

```bash
rclone config
rclone listremotes
```

Recommended configuration choices for read-only import:

- Storage: `drive`
- `client_id`: leave blank unless the user wants their own Google Cloud project
- `client_secret`: leave blank unless using a custom client
- Scope: `drive.readonly`
- Service account file: leave blank for browser login with the user's account
- Shared Drive: choose yes only when importing a Google Shared Drive

Copy from a remote into the default workspace destination:

```bash
mkdir -p "<resolved-drive-destination>"
rclone copy "<remote>:<path>" "<resolved-drive-destination>" --progress
```

For files shared directly with the user account, include:

```bash
rclone copy "<remote>:" "<resolved-drive-destination>" --drive-shared-with-me --progress
```

For a local mirror, use `sync` only after satisfying the two-confirmation
safety rule above:

```bash
rclone sync "<remote>:<path>" "<resolved-drive-destination>" --progress
```

When Google Docs, Sheets, or Slides need local file formats, set export formats
explicitly, for example:

```bash
rclone copy "<remote>:<path>" "<resolved-drive-destination>" \
  --drive-export-formats docx,xlsx,pptx,pdf \
  --progress
```

## Bundled OAuth/API Importer

Create an Installed application OAuth client in Google Cloud, enable Drive API,
download its JSON outside the repository as
`${XDG_CONFIG_HOME:-$HOME/.config}/google-api/oauth-client.json`, and add the
account as an OAuth test user when applicable. The first run opens browser
consent and stores a user-only token beside it. The script requests only
`drive.readonly`, downloads binary files with `files.get` media, exports
Google-native Docs/Sheets/Slides to declared local representations, and records
checksums and source metadata in `index.jsonl`.

Import one folder, bounded by count and optionally recursive:

```bash
python <gather-skill-directory>/scripts/sync_google_drive.py \
  --folder-id FOLDER_ID \
  --recursive --max-files 500
```

Official setup and download contracts: [Python quickstart](https://developers.google.com/workspace/drive/api/quickstart/python) and [download/export guide](https://developers.google.com/workspace/drive/api/guides/manage-downloads).

## Troubleshooting

- If listing returns nothing, verify the authenticated account or service
  account has folder access.
- If shared drive files are missing, ensure the tool uses all-drives support or
  that rclone is configured for the correct shared drive.
- If "Shared with me" files are missing in rclone, retry with
  `--drive-shared-with-me`.
- If Google-native files download incorrectly, export Docs, Sheets, and Slides
  as PDF, DOCX, XLSX, or PPTX instead of binary media.
- If a script writes to old `drive_downloads/`, change `--output-dir` to the
  resolved destination.

## Verification

After syncing, report:

- source method used,
- normalized resolved destination and whether it came from explicit input,
  `.agent-factory/sync.json`, or the default,
- approximate file count and size,
- any skipped Google-native files or export conversions,
- whether credentials or tokens were created.

Useful checks:

```bash
find "<resolved-drive-destination>" -type f | wc -l
du -sh "<resolved-drive-destination>"
```
