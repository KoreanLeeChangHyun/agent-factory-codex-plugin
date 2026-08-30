#!/usr/bin/env python3
"""Read-only bounded Discord channel history and attachment downloader."""

import argparse
import copy
import json
from pathlib import Path

import requests

from provider_support import DestinationStore, load_index, provenance, require_env, resolve, safe_name, save_index, write_bytes, write_json

API = "https://discord.com/api/v10"


def sanitized_messages(messages):
    evidence = copy.deepcopy(messages)

    def scrub(value):
        if isinstance(value, dict):
            attachments = value.get("attachments")
            if isinstance(attachments, list):
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        attachment.pop("url", None)
                        attachment.pop("proxy_url", None)
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
    boundary = parser.add_mutually_exclusive_group()
    boundary.add_argument("--before")
    boundary.add_argument("--after")
    parser.add_argument("--max-messages", type=int, default=200)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--token-env", default="DISCORD_BOT_TOKEN")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.max_messages < 1:
        raise SystemExit("--max-messages must be positive")
    root = resolve("discord", args.destination, args.project_root)
    token = require_env(args.token_env)
    headers, messages, cursor = {"Authorization": f"Bot {token}"}, [], args.before or args.after
    while len(messages) < args.max_messages:
        params = {"limit": min(100, args.max_messages-len(messages))}
        if cursor:
            params["before" if not args.after else "after"] = cursor
        response = requests.get(f"{API}/channels/{args.channel_id}/messages", headers=headers, params=params, timeout=60)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        messages.extend(batch)
        cursor = batch[-1 if not args.after else 0]["id"]
        if len(batch) < params["limit"]:
            break
    direction = "after" if args.after else "before"
    boundary_value = args.after or args.before or "none"
    selection = f"{direction}-{safe_name(boundary_value)}_max-{args.max_messages}.json"
    snapshot = Path("channels") / args.channel_id / "snapshots" / selection
    with DestinationStore(root) as store:
        if args.overwrite or store.read_text(snapshot) is None:
            write_json(store, snapshot, sanitized_messages(messages))
        index = load_index(store)
        for message in messages:
            for attachment in message.get("attachments", []):
                identifier = attachment["id"]
                if identifier in index and not args.overwrite:
                    continue
                # Consume the signed URL only from the fresh in-memory response.
                response = requests.get(attachment["url"], timeout=120)
                response.raise_for_status()
                path = write_bytes(store, Path("attachments") / f"{identifier}-{safe_name(attachment.get('filename'), identifier)}", response.content)
                index[identifier] = provenance(identifier, None, path, response.content, provider="discord", channel_id=args.channel_id, message_id=message["id"], filename=attachment.get("filename"), content_type=attachment.get("content_type"))
        save_index(store, index)
    print(json.dumps({"destination": str(root), "messages": len(messages), "indexed_attachments": len(index)}))


if __name__ == "__main__":
    main()
