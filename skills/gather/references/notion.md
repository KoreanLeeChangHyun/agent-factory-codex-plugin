# Gather Notion

Use `scripts/sync_notion.py` to collect one explicitly selected page and its
descendant block tree into the resolved `notion` destination (default
`source/notion`). It saves the page and block API representations together in
a block-limit-specific file under `pages/<page-id>/snapshots/`, downloads
block file objects, and records inspectable JSONL provenance. It does not edit
pages, blocks, comments, or data sources.

## Connection And Authentication

For a workspace-local workflow, create an internal integration and store its
bearer token outside the repository in `NOTION_TOKEN`. For a multi-workspace
application, use Notion public OAuth and provide the resulting access token in
the same environment variable. In either case, explicitly share the source
page and any required data sources with the integration; authentication alone
does not grant access. Use read-content capability only. The script sends
`Notion-Version: 2026-03-11`.

See Notion's [authentication contract](https://developers.notion.com/reference/authentication)
and [block API](https://developers.notion.com/reference/block).

```bash
export NOTION_TOKEN='ntn_...'
python <gather-skill-directory>/scripts/sync_notion.py \
  --page-id PAGE_ID --max-blocks 1000
```

Confirm the page ID, block limit, integration sharing, and resolved destination.
Notion-hosted file URLs are temporary, so the script refetches each block just
before downloading and removes those URLs from all saved API evidence and
provenance. External file URLs remain source URLs. Different block limits
retain separate snapshots. Existing snapshots and indexed files are retained
by default; pass `--overwrite` only to replace evidence for that same block
limit and refresh already indexed files.
