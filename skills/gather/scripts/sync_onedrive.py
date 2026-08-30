#!/usr/bin/env python3
"""Read-only bounded OneDrive downloader using Graph delegated device auth."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests

from provider_support import DestinationStore, load_index, provenance, read_private_text, require_env, resolve, safe_name, save_index, sync_manager, write_bytes, write_private_text

GRAPH = "https://graph.microsoft.com/v1.0"


def access_token(client_id, tenant, cache_path, shared, project_root):
    cache_text = read_private_text(
        cache_path, project_root, "OneDrive token cache"
    )

    import msal

    cache = msal.SerializableTokenCache()
    if cache_text is not None:
        cache.deserialize(cache_text)
    app = msal.PublicClientApplication(client_id, authority=f"https://login.microsoftonline.com/{tenant}", token_cache=cache)
    scopes = ["Files.Read.All" if shared else "Files.Read"]
    accounts = app.get_accounts()
    result = app.acquire_token_silent(scopes, account=accounts[0]) if accounts else None
    if not result:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise RuntimeError(f"cannot initiate device flow: {flow}")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Microsoft authentication failed"))
    write_private_text(
        cache_path,
        cache.serialize(),
        project_root,
        "OneDrive token cache",
    )
    return result["access_token"]


def graph(token, url):
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    response.raise_for_status()
    return response.json()


def graph_component(value):
    return quote(str(value), safe="")


def graph_selected_path(value):
    return "/".join(graph_component(part) for part in value.strip("/").split("/") if part)


def main():
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--item-id")
    selection.add_argument("--path")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-files", type=int, default=500)
    parser.add_argument("--include-shared", action="store_true")
    parser.add_argument("--drive-id", help="Explicit shared drive ID; requires --include-shared")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--client-id-env", default="ONEDRIVE_CLIENT_ID")
    parser.add_argument("--tenant", default="common")
    default_cache = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "agent-factory" / "onedrive-token-cache.json"
    parser.add_argument("--token-cache", type=Path, default=default_cache)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.max_files < 1:
        raise SystemExit("--max-files must be positive")
    if args.drive_id and not args.include_shared:
        raise SystemExit("--drive-id requires intentional --include-shared consent")
    root = resolve("onedrive", args.destination, args.project_root)
    project_root = sync_manager.resolve_project_root(args.project_root)
    token = access_token(
        require_env(args.client_id_env),
        args.tenant,
        args.token_cache,
        args.include_shared,
        project_root,
    )
    drive_base = f"{GRAPH}/drives/{graph_component(args.drive_id)}" if args.drive_id else f"{GRAPH}/me/drive"
    if args.item_id:
        initial = graph(token, f"{drive_base}/items/{graph_component(args.item_id)}")
    else:
        selected = graph_selected_path(args.path)
        initial = graph(token, f"{drive_base}/root:/{selected}") if selected else graph(token, f"{drive_base}/root")
    queue, files = [(initial, Path())], []
    while queue and len(files) < args.max_files:
        item, relative = queue.pop(0)
        if "folder" not in item:
            files.append((item, relative))
            continue
        url = f"{drive_base}/items/{graph_component(item['id'])}/children?$top=200"
        while url and len(files) < args.max_files:
            body = graph(token, url)
            for child in body.get("value", []):
                if "folder" in child:
                    if args.recursive:
                        queue.append((child, relative / safe_name(child["name"], child["id"])))
                else:
                    files.append((child, relative))
                    if len(files) >= args.max_files:
                        break
            url = body.get("@odata.nextLink")
    with DestinationStore(root) as store:
        index = load_index(store)
        for item, relative in files:
            if item["id"] in index and not args.overwrite:
                continue
            response = requests.get(f"{drive_base}/items/{graph_component(item['id'])}/content", headers={"Authorization": f"Bearer {token}"}, timeout=120)
            response.raise_for_status()
            path = write_bytes(store, Path("files") / relative / f"{item['id']}-{safe_name(item['name'], item['id'])}", response.content)
            index[item["id"]] = provenance(item["id"], item.get("webUrl"), path, response.content, provider="onedrive", original_name=item["name"], modified_time=item.get("lastModifiedDateTime"), source_size=item.get("size"))
        save_index(store, index)
    print(json.dumps({"destination": str(root), "selected_files": len(files), "indexed_files": len(index), "token_cache": str(args.token_cache)}))


if __name__ == "__main__":
    main()
