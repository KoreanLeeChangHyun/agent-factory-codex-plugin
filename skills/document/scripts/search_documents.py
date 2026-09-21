#!/usr/bin/env python3
"""Search the live Original, Processed, Progress and Lessons Learned Document catalog."""

import argparse
import json
from pathlib import Path
import sys

from catalog_documents import CATALOG_TYPES, build_catalog


def search(root: Path, query: str, document_type=None, category=None, limit=20) -> dict:
    terms = [term.casefold() for term in query.split() if term]
    if not terms:
        raise ValueError("Search query must contain non-whitespace text")
    if limit < 1 or limit > 100:
        raise ValueError("Search limit must be between 1 and 100")
    root = root.resolve(strict=True)
    matches = []
    for entry in build_catalog(root)["documents"]:
        if document_type and entry["documentType"] != document_type:
            continue
        if category and entry["category"] != category:
            continue
        searchable = json.dumps(entry["metadata"], ensure_ascii=False)
        if entry["contentPath"]:
            searchable += "\n" + (root / entry["contentPath"]).read_text(encoding="utf-8")
        folded = searchable.casefold()
        if not all(term in folded for term in terms):
            continue
        result = {key: value for key, value in entry.items() if key != "metadata"}
        result["score"] = sum(folded.count(term) for term in terms)
        matches.append(result)
    matches.sort(
        key=lambda item: (
            -item["score"], item["documentType"], item["category"],
            item["domain"] or "", item["name"],
        )
    )
    return {
        "schemaVersion": "0.1.0",
        "kind": "document-search-results",
        "query": query,
        "count": min(len(matches), limit),
        "results": matches[:limit],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--type", choices=CATALOG_TYPES)
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        results = search(args.project_root, args.query, args.type, args.category, args.limit)
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
