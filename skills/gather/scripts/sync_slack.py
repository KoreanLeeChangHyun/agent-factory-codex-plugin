#!/usr/bin/env python3
"""Read-only bounded Slack channel history and file downloader."""

import argparse
import copy
import json
from pathlib import Path

import requests

from provider_support import DestinationStore, load_index, provenance, require_env, resolve, safe_name, save_index, write_bytes, write_json


def api(token, method, **params):
    response = requests.get(f"https://slack.com/api/{method}", headers={"Authorization": f"Bearer {token}"}, params=params, timeout=60)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"Slack {method}: {body.get('error', 'unknown error')}")
    return body


def sanitized_messages(messages):
    """Remove bearer-protected download URLs from persisted API evidence."""
    evidence = copy.deepcopy(messages)

    def scrub(value):
        if isinstance(value, dict):
            value.pop("url_private", None)
            value.pop("url_private_download", None)
            for child in value.values():
                scrub(child)
        elif isinstance(value, list):
            for child in value:
                scrub(child)

    scrub(evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--oldest")
    parser.add_argument("--latest")
    parser.add_argument("--max-messages", type=int, default=200)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--token-env", default="SLACK_BOT_TOKEN")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.max_messages < 1:
        raise SystemExit("--max-messages must be positive")
    root = resolve("slack", args.destination, args.project_root)
    token = require_env(args.token_env)
    messages, cursor = [], None
    while len(messages) < args.max_messages:
        body = api(token, "conversations.history", channel=args.channel_id, oldest=args.oldest, latest=args.latest, limit=min(200, args.max_messages-len(messages)), cursor=cursor)
        messages.extend(body.get("messages", []))
        cursor = body.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    selection = f"oldest-{safe_name(args.oldest, 'none')}_latest-{safe_name(args.latest, 'none')}_max-{args.max_messages}.json"
    snapshot = Path("channels") / args.channel_id / "snapshots" / selection
    with DestinationStore(root) as store:
        if args.overwrite or store.read_text(snapshot) is None:
            write_json(store, snapshot, sanitized_messages(messages))
        index = load_index(store)
        for message in messages:
            for item in message.get("files", []):
                identifier = item["id"]
                if identifier in index and not args.overwrite:
                    continue
                detail = api(token, "files.info", file=identifier)["file"]
                url = detail.get("url_private_download") or detail.get("url_private")
                if not url:
                    continue
                response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
                response.raise_for_status()
                path = write_bytes(store, Path("files") / f"{identifier}-{safe_name(detail.get('name'), identifier)}", response.content)
                index[identifier] = provenance(identifier, detail.get("permalink"), path, response.content, provider="slack", channel_id=args.channel_id, message_ts=message.get("ts"), mime_type=detail.get("mimetype"))
        save_index(store, index)
    print(json.dumps({"destination": str(root), "messages": len(messages), "indexed_files": len(index)}))


if __name__ == "__main__":
    main()
