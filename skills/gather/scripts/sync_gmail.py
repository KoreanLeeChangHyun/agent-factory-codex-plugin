#!/usr/bin/env python3
import argparse
import base64
import email
import importlib.util
import json
import os
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SYNC_MANAGER = (
    Path(__file__).resolve().parents[2] / "gather" / "scripts" / "sync.py"
)


def config_home():
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config"


GOOGLE_API_CONFIG_DIR = config_home() / "google-api"
DEFAULT_CLIENT = GOOGLE_API_CONFIG_DIR / "oauth-client.json"
DEFAULT_TOKEN = GOOGLE_API_CONFIG_DIR / "gmail-token.json"


def load_sync_manager():
    spec = importlib.util.spec_from_file_location(
        "agent_factory_sync_manager", SYNC_MANAGER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sync manager: {SYNC_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_manager = load_sync_manager()
resolve_sync_destination = sync_manager.resolve_sync_destination
DIRECTORY_OPEN_FLAGS = sync_manager.DIRECTORY_OPEN_FLAGS
FILE_NOFOLLOW = sync_manager.FILE_NOFOLLOW


class DestinationStore:
    """Keep destination traversal and writes anchored to directory descriptors."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError("resolved destination must be absolute")
        self.descriptor = -1

    def __enter__(self):
        # Walk from the filesystem anchor one descriptor at a time; later calls
        # never re-resolve the user-selected destination through mutable paths.
        descriptor = os.open(self.root.anchor, DIRECTORY_OPEN_FLAGS)
        try:
            for part in self.root.parts[1:]:
                try:
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                except FileNotFoundError:
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
        except BaseException:
            os.close(descriptor)
            raise
        self.descriptor = descriptor
        return self

    def __exit__(self, *_):
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    @staticmethod
    def _parts(relative):
        candidate = Path(relative)
        if candidate.is_absolute() or not candidate.parts:
            raise ValueError(f"destination-relative path required: {relative}")
        if any(part in {"", ".", ".."} for part in candidate.parts):
            raise ValueError(f"unsafe destination-relative path: {relative}")
        return candidate.parts

    def _open_directory(self, parts, *, create):
        descriptor = os.dup(self.descriptor)
        try:
            for part in parts:
                try:
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def write_bytes(self, relative, payload):
        parts = self._parts(relative)
        parent = self._open_directory(parts[:-1], create=True)
        descriptor = -1
        try:
            try:
                descriptor = os.open(
                    parts[-1],
                    os.O_WRONLY | os.O_NONBLOCK | FILE_NOFOLLOW,
                    dir_fd=parent,
                )
            except FileNotFoundError:
                descriptor = os.open(
                    parts[-1],
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | os.O_NONBLOCK
                    | FILE_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise RuntimeError(f"destination file must be regular: {relative}")
            os.ftruncate(descriptor, 0)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent)

    def read_text(self, relative):
        parts = self._parts(relative)
        try:
            parent = self._open_directory(parts[:-1], create=False)
        except FileNotFoundError:
            return None
        descriptor = -1
        try:
            try:
                descriptor = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_NONBLOCK | FILE_NOFOLLOW,
                    dir_fd=parent,
                )
            except FileNotFoundError:
                return None
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise RuntimeError(f"destination file must be regular: {relative}")
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                descriptor = -1
                return stream.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent)

    def write_text_atomic(self, relative, text):
        parts = self._parts(relative)
        parent = self._open_directory(parts[:-1], create=True)
        temporary_name = None
        try:
            for _ in range(32):
                temporary_name = f".sync.{secrets.token_hex(12)}"
                try:
                    descriptor = os.open(
                        temporary_name,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_NONBLOCK
                        | FILE_NOFOLLOW,
                        0o600,
                        dir_fd=parent,
                    )
                    break
                except FileExistsError:
                    continue
            else:
                raise RuntimeError("cannot allocate destination temporary file")
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            # The index is the synchronization boundary: readers see either the
            # previous complete index or the newly fsynced replacement.
            os.replace(
                temporary_name,
                parts[-1],
                src_dir_fd=parent,
                dst_dir_fd=parent,
            )
            temporary_name = None
            os.fsync(parent)
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=parent)
                except FileNotFoundError:
                    pass
            os.close(parent)

    def path(self, relative):
        return self.root / Path(relative)


def b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def safe_name(value, fallback):
    value = value or fallback
    value = re.sub(r"[/\\:\0]", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:180] or fallback


def load_credentials(client_path, token_path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

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


def load_index(store):
    entries = {}
    text = store.read_text("index.jsonl")
    if text is None:
        return entries
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if "id" in item:
            entries[item["id"]] = item
    return entries


def write_index(store, entries):
    rows = [
        json.dumps(entries[key], ensure_ascii=False, sort_keys=True)
        for key in sorted(entries)
    ]
    store.write_text_atomic(
        "index.jsonl", "\n".join(rows) + ("\n" if rows else "")
    )


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
        )
    )
    destination = Path(resolved["destination"])

    if not args.client.exists():
        raise SystemExit(f"OAuth client file not found: {args.client}")

    creds = load_credentials(args.client, args.token)
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
