#!/usr/bin/env python3
"""Read-only bounded Notion page/block and file downloader."""

import argparse
import copy
import json
from pathlib import Path
from urllib.parse import urlparse

import requests

from provider_support import DestinationStore, load_index, provenance, require_env, resolve, safe_name, save_index, write_bytes, write_json

VERSION = "2026-03-11"


def notion(token, path, **params):
    response = requests.get(
        f"https://api.notion.com/v1/{path}",
        headers={"Authorization": f"Bearer {token}", "Notion-Version": VERSION},
        params=params, timeout=60,
    )
    response.raise_for_status()
    return response.json()


def block_children(token, block_id, remaining):
    results, cursor = [], None
    while len(results) < remaining:
        body = notion(token, f"blocks/{block_id}/children", page_size=min(100, remaining-len(results)), start_cursor=cursor)
        results.extend(body.get("results", []))
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return results


def file_objects(value):
    if isinstance(value, dict):
        if value.get("type") in {"file", "external"} and isinstance(value.get(value["type"]), dict) and value[value["type"]].get("url"):
            yield value
        for child in value.values():
            yield from file_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from file_objects(child)


def sanitized_evidence(value):
    evidence = copy.deepcopy(value)

    def scrub(child):
        if isinstance(child, dict):
            if child.get("type") == "file" and isinstance(child.get("file"), dict):
                child["file"].pop("url", None)
            for nested in child.values():
                scrub(nested)
        elif isinstance(child, list):
            for nested in child:
                scrub(nested)

    scrub(evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--max-blocks", type=int, default=1000)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--token-env", default="NOTION_TOKEN")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.max_blocks < 1:
        raise SystemExit("--max-blocks must be positive")
    token, root = require_env(args.token_env), resolve("notion", args.destination, args.project_root)
    page = notion(token, f"pages/{args.page_id}")
    blocks, queue = [], [args.page_id]
    while queue and len(blocks) < args.max_blocks:
        current = queue.pop(0)
        batch = block_children(token, current, args.max_blocks-len(blocks))
        blocks.extend(batch)
        queue.extend(item["id"] for item in batch if item.get("has_children"))
    snapshot = Path("pages") / args.page_id / "snapshots" / f"max-blocks-{args.max_blocks}.json"
    with DestinationStore(root) as store:
        if args.overwrite or store.read_text(snapshot) is None:
            write_json(store, snapshot, sanitized_evidence({"page": page, "blocks": blocks}))
        index = load_index(store)
        for block in blocks:
            # Refetch immediately before consuming temporary URLs in memory.
            fresh = notion(token, f"blocks/{block['id']}")
            for position, file_object in enumerate(file_objects(fresh), start=1):
                file_type = file_object["type"]
                url = file_object[file_type]["url"]
                identifier = f"{block['id']}:{position}"
                if identifier in index and not args.overwrite:
                    continue
                response = requests.get(url, timeout=120)
                response.raise_for_status()
                filename = Path(urlparse(url).path).name or identifier
                path = write_bytes(store, Path("files") / f"{safe_name(block['id'])}-{position}-{safe_name(filename)}", response.content)
                index[identifier] = provenance(identifier, url if file_type == "external" else None, path, response.content, provider="notion", page_id=args.page_id, block_id=block["id"], notion_file_type=file_type)
        save_index(store, index)
    print(json.dumps({"destination": str(root), "blocks": len(blocks), "indexed_files": len(index)}))


if __name__ == "__main__":
    main()
