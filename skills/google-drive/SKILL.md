---
name: google-drive
description: Share, authorize, import, refresh, mirror, or troubleshoot Google Drive files for local workspace use. Use when Codex needs to choose a Drive sharing method, get read-only access to files visible to a user's Google account, sync materials into source/google/drive under the current project root, handle shared drives or "Shared with me" files, compare Google Drive for desktop, rclone, browser download, OAuth, service account, or link-based access, or avoid unsafe repository-local Google API credential setups.
---

# Sync Google Drive

## Overview

Use this skill to get Google Drive files into a local workspace or explain how
to share Drive access for that purpose. Default the local destination to
`source/google/drive` under the current project root unless the user gives a
different path.

Keep the workflow read-only by default. Do not upload, delete, or modify Drive
files unless the user explicitly asks for write-back behavior.

Prefer the least privileged method that fits the job. Do not create
project-specific Google Cloud OAuth clients or repository-local Google Drive API
importers unless the user explicitly asks or existing project tooling requires
it. Treat those as legacy or project-specific paths, not the default workflow.

## Workspace Convention

- Put original Drive materials under `source/google/drive/` relative to the
  current project root.
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
4. **Existing OAuth/API importer**: Use only when a repository already has a
   suitable importer or the user explicitly wants this route. Confirm it uses
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
find "$HOME/Library/CloudStorage" -maxdepth 3 -type d 2>/dev/null | sed -n '1,120p'
command -v rclone && rclone version
test -d source/google/drive && find source/google/drive -type f | wc -l || true
test -d source/google/drive && du -sh source/google/drive || true
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

- Store local Drive materials under `source/google/drive` in the current
  project root by default.
- Keep credentials, tokens, and rclone config out of git.
- Prefer read-only scopes and copy/sync from Drive to local only.
- Before running a destructive local sync such as `rsync --delete` or
  `rclone sync`, confirm the source and destination paths are correct.
- Do not delete cloud files. For local cleanup, only remove files under the
  confirmed destination directory.
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
mkdir -p source/google/drive
rsync -a "<mounted-drive-path>/" source/google/drive/
```

5. For a mirror of the mounted source into the local destination, use delete
   only after verifying both paths:

```bash
rsync -a --delete "<mounted-drive-path>/" source/google/drive/
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
mkdir -p source/google/drive
rclone copy "<remote>:<path>" source/google/drive --progress
```

For files shared directly with the user account, include:

```bash
rclone copy "<remote>:" source/google/drive --drive-shared-with-me --progress
```

For a local mirror, use `sync` only after verifying the remote and destination:

```bash
rclone sync "<remote>:<path>" source/google/drive --progress
```

When Google Docs, Sheets, or Slides need local file formats, set export formats
explicitly, for example:

```bash
rclone copy "<remote>:<path>" source/google/drive \
  --drive-export-formats docx,xlsx,pptx,pdf \
  --progress
```

## Existing OAuth/API Importer

Use this path only when existing project tooling is appropriate.

1. Check for setup docs and importer scripts, for example:
   - `docs/google_drive_readonly_setup.md`
   - `tools/google_drive_import.py`
2. Confirm the importer requests read-only Drive access for imports:
   - `https://www.googleapis.com/auth/drive.readonly`
3. Keep OAuth client secrets and tokens outside the repository.
4. Import to `source/google/drive`, for example:

```bash
python tools/google_drive_import.py \
  --folder-id FOLDER_ID \
  --output-dir source/google/drive \
  --recursive
```

For shared drives, list or pass the shared drive ID if the importer supports
it:

```bash
python tools/google_drive_import.py --list-shared-drives
python tools/google_drive_import.py \
  --drive-id SHARED_DRIVE_ID \
  --folder-id FOLDER_ID \
  --output-dir source/google/drive \
  --recursive
```

## Troubleshooting

- If listing returns nothing, verify the authenticated account or service
  account has folder access.
- If shared drive files are missing, ensure the tool uses all-drives support or
  that rclone is configured for the correct shared drive.
- If "Shared with me" files are missing in rclone, retry with
  `--drive-shared-with-me`.
- If Google-native files download incorrectly, export Docs, Sheets, and Slides
  as PDF, DOCX, XLSX, or PPTX instead of binary media.
- If a script writes to old `drive_downloads/`, change `--output-dir` to
  `source/google/drive`.

## Verification

After syncing, report:

- source method used,
- local destination path,
- approximate file count and size,
- any skipped Google-native files or export conversions,
- whether credentials or tokens were created.

Useful checks:

```bash
find source/google/drive -type f | wc -l
du -sh source/google/drive
```
