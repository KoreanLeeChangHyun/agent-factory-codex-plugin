#!/usr/bin/env python3
import argparse
import base64
import email
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def config_home():
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config"


GOOGLE_API_CONFIG_DIR = config_home() / "google-api"
DEFAULT_CLIENT = GOOGLE_API_CONFIG_DIR / "oauth-client.json"
DEFAULT_TOKEN = GOOGLE_API_CONFIG_DIR / "gmail-token.json"
DEFAULT_DESTINATION = Path("source/google/mail")


def b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def safe_name(value, fallback):
    value = value or fallback
    value = re.sub(r"[/\\:\0]", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:180] or fallback


def load_credentials(client_path, token_path):
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    token_path.chmod(0o600)
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


def extract_attachments(raw_bytes, destination, message_id):
    message = email.message_from_bytes(raw_bytes)
    attachment_dir = destination / "attachments" / message_id
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
        attachment_dir.mkdir(parents=True, exist_ok=True)
        path = attachment_dir / filename
        path.write_bytes(payload)
        attachments.append(
            {
                "filename": filename,
                "path": str(path),
                "size": len(payload),
                "content_type": part.get_content_type(),
            }
        )
    return attachments


def load_index(path):
    entries = {}
    if not path.exists():
        return entries
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if "id" in item:
            entries[item["id"]] = item
    return entries


def write_index(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        json.dumps(entries[key], ensure_ascii=False, sort_keys=True)
        for key in sorted(entries)
    ]
    path.write_text("\n".join(rows) + ("\n" if rows else ""))


def sync_message(service, message_id, destination):
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

    message_dir = destination / "messages"
    message_dir.mkdir(parents=True, exist_ok=True)
    eml_path = message_dir / f"{message_id}.eml"
    eml_path.write_bytes(raw_bytes)

    headers = headers_by_name(metadata.get("payload", {}))
    attachments = extract_attachments(raw_bytes, destination, message_id)
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
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
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
    if not args.client.exists():
        raise SystemExit(f"OAuth client file not found: {args.client}")

    creds = load_credentials(args.client, args.token)
    service = build("gmail", "v1", credentials=creds)
    args.destination.mkdir(parents=True, exist_ok=True)

    message_ids = list_message_ids(service, args.query, args.max_results)
    index_path = args.destination / "index.jsonl"
    entries = load_index(index_path)

    imported = 0
    skipped = 0
    attachment_count = 0
    attachment_bytes = 0
    for message_id in message_ids:
        if message_id in entries and not args.overwrite:
            skipped += 1
            continue
        entry = sync_message(service, message_id, args.destination)
        entries[message_id] = entry
        imported += 1
        attachment_count += len(entry["attachments"])
        attachment_bytes += sum(item["size"] for item in entry["attachments"])

    write_index(index_path, entries)
    print(
        json.dumps(
            {
                "destination": str(args.destination),
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
