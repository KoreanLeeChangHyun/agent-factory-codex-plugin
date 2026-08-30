#!/usr/bin/env python3
import argparse
import base64
import email
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from provider_support import (
    DestinationStore,
    load_index,
    read_private_json,
    safe_name,
    save_index,
    sync_manager,
    write_private_text,
)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
def config_home():
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config"


GOOGLE_API_CONFIG_DIR = config_home() / "google-api"
DEFAULT_CLIENT = GOOGLE_API_CONFIG_DIR / "oauth-client.json"
DEFAULT_TOKEN = GOOGLE_API_CONFIG_DIR / "gmail-token.json"


resolve_sync_destination = sync_manager.resolve_sync_destination


def b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def load_credentials(client_path, token_path, project_root):
    client_info = read_private_json(
        client_path, project_root, "Google OAuth client", required=True
    )
    token_info = read_private_json(token_path, project_root, "Gmail OAuth token")

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if token_info is not None:
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(client_info, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    write_private_text(token_path, creds.to_json(), project_root, "Gmail OAuth token")
    return creds


def list_message_ids(service, query, max_results):
    ids = []
    request = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=min(max_results, 500),
        )
    )
    while request is not None and len(ids) < max_results:
        response = request.execute()
        ids.extend(item["id"] for item in response.get("messages", []))
        if len(ids) >= max_results:
            break
        request = service.users().messages().list_next(request, response)
    return ids[:max_results]


def headers_by_name(payload):
    headers = {}
    for item in payload.get("headers", []):
        name = item.get("name")
        if name:
            headers[name.lower()] = item.get("value", "")
    return headers


def extract_attachments(raw_bytes, store, message_id):
    message = email.message_from_bytes(raw_bytes)
    attachments = []
    used = set()
    for idx, part in enumerate(message.walk(), start=1):
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        filename = safe_name(filename, f"attachment-{idx}")
        base = filename
        counter = 2
        while filename in used:
            stem = Path(base).stem
            suffix = Path(base).suffix
            filename = f"{stem}-{counter}{suffix}"
            counter += 1
        used.add(filename)
        relative = Path("attachments") / message_id / filename
        store.write_bytes(relative, payload)
        path = store.path(relative)
        attachments.append(
            {
                "filename": filename,
                "path": str(path),
                "size": len(payload),
                "content_type": part.get_content_type(),
            }
        )
    return attachments


def write_index(store, entries):
    save_index(store, entries)


def sync_message(service, message_id, store):
    metadata = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "To", "Cc", "Subject", "Date", "Message-ID"],
        )
        .execute()
    )
    raw = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="raw")
        .execute()
    )
    raw_bytes = b64url_decode(raw["raw"])

    relative = Path("messages") / f"{message_id}.eml"
    store.write_bytes(relative, raw_bytes)
    eml_path = store.path(relative)

    headers = headers_by_name(metadata.get("payload", {}))
    attachments = extract_attachments(raw_bytes, store, message_id)
    return {
        "id": message_id,
        "thread_id": metadata.get("threadId"),
        "label_ids": metadata.get("labelIds", []),
        "internal_date": metadata.get("internalDate"),
        "snippet": metadata.get("snippet", ""),
        "headers": {
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "message_id": headers.get("message-id", ""),
        },
        "eml_path": str(eml_path),
        "eml_size": len(raw_bytes),
        "eml_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "attachments": attachments,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Sync Gmail messages and attachments to local files."
    )
    parser.add_argument(
        "--query",
        default="",
        help="Gmail search query, for example: project-name newer:2026/04/01",
    )
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--client", type=Path, default=DEFAULT_CLIENT)
    parser.add_argument("--token", type=Path, default=DEFAULT_TOKEN)
    parser.add_argument(
        "--allow-all", action="store_true", help="Allow an empty query."
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.query and not args.allow_all:
        raise SystemExit(
            "Refusing broad mailbox import without --query or --allow-all."
        )
    if args.max_results < 1:
        raise SystemExit("--max-results must be positive.")

    resolved = resolve_sync_destination(
        "google-mail",
        destination=args.destination,
        project_root=args.project_root,
    )
    print(
        json.dumps(
            {"event": "destination-resolved", **resolved},
            ensure_ascii=False,
        ),
        flush=True,
    )
    destination = Path(resolved["destination"])

    project_root = Path(resolved["projectRoot"])
    creds = load_credentials(args.client, args.token, project_root)
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=creds)
    message_ids = list_message_ids(service, args.query, args.max_results)
    index_path = destination / "index.jsonl"
    with DestinationStore(destination) as store:
        entries = load_index(store)
        imported = 0
        skipped = 0
        attachment_count = 0
        attachment_bytes = 0
        for message_id in message_ids:
            # Existing index membership is the durable idempotency signal; an
            # explicit overwrite is required to rewrite message side effects.
            if message_id in entries and not args.overwrite:
                skipped += 1
                continue
            entry = sync_message(service, message_id, store)
            entries[message_id] = entry
            imported += 1
            attachment_count += len(entry["attachments"])
            attachment_bytes += sum(item["size"] for item in entry["attachments"])

        write_index(store, entries)
    print(
        json.dumps(
            {
                "destination": str(destination),
                "query": args.query,
                "matched": len(message_ids),
                "imported": imported,
                "skipped_existing": skipped,
                "attachments_imported": attachment_count,
                "attachment_bytes": attachment_bytes,
                "index": str(index_path),
                "token": str(args.token),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
