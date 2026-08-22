#!/usr/bin/env python3
"""Read-only bounded Google Drive folder downloader with JSONL provenance."""

import argparse
import io
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from provider_support import DestinationStore, load_index, provenance, resolve, safe_name, save_index, write_bytes

SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]
EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
    ),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}


def credentials(client, token):
    creds = Credentials.from_authorized_user_file(str(token), SCOPE) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPE).run_local_server(port=0)
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json(), encoding="utf-8")
    token.chmod(0o600)
    return creds


def children(service, folder_id):
    page = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime,md5Checksum,size,webViewLink)",
            pageToken=page, pageSize=1000, supportsAllDrives=True,
            includeItemsFromAllDrives=True, corpora="allDrives",
        ).execute()
        yield from response.get("files", [])
        page = response.get("nextPageToken")
        if not page:
            return


def download(request):
    stream = io.BytesIO()
    downloader = MediaIoBaseDownload(stream, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return stream.getvalue()


def main():
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "google-api"
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", required=True)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-files", type=int, default=500)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--client", type=Path, default=config / "oauth-client.json")
    parser.add_argument("--token", type=Path, default=config / "drive-token.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.max_files < 1:
        raise SystemExit("--max-files must be positive")
    if not args.client.is_file():
        raise SystemExit(f"OAuth client file not found: {args.client}")
    root = resolve("google-drive", args.destination, args.project_root)
    service = build("drive", "v3", credentials=credentials(args.client, args.token))
    count, queue = 0, [(args.folder_id, Path())]
    with DestinationStore(root) as store:
        index = load_index(store)
        while queue and count < args.max_files:
            folder_id, relative_dir = queue.pop(0)
            for item in children(service, folder_id):
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    if args.recursive:
                        queue.append((item["id"], relative_dir / safe_name(item["name"], item["id"])))
                    continue
                if item["id"] in index and not args.overwrite:
                    continue
                name = safe_name(item["name"], item["id"])
                if item["mimeType"] in EXPORTS:
                    export_type, suffix = EXPORTS[item["mimeType"]]
                    payload = download(service.files().export_media(fileId=item["id"], mimeType=export_type))
                    name += suffix
                    representation = export_type
                elif item["mimeType"].startswith("application/vnd.google-apps."):
                    continue
                else:
                    payload = download(service.files().get_media(fileId=item["id"], supportsAllDrives=True))
                    representation = item["mimeType"]
                path = write_bytes(store, Path("files") / relative_dir / f"{item['id']}-{name}", payload)
                index[item["id"]] = provenance(
                    item["id"], item.get("webViewLink"), path, payload,
                    provider="google-drive", original_name=item["name"],
                    source_mime_type=item["mimeType"], local_representation=representation,
                    modified_time=item.get("modifiedTime"), source_md5=item.get("md5Checksum"),
                )
                count += 1
                if count >= args.max_files:
                    break
        save_index(store, index)
    print(f"Downloaded {count} files to {root}; index: {root / 'index.jsonl'}")


if __name__ == "__main__":
    main()
