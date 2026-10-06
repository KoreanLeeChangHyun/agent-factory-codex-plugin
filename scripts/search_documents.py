#!/usr/bin/env python3
"""Search the live Original, Refined, Progress and Lessons Learned Document catalog."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from catalog_documents import CATALOG_TYPES, TYPE_ALIASES, build_catalog, catalog_entry, check_path, inventory


def snapshot(root, entry, observer=None):
    """Hash all package dependencies; reuse these bytes for search and section reads."""
    package = root / entry['packagePath']
    files = ([entry['packagePath']] if package.is_file() else
             [str((package / name).relative_to(root)) for name, shape in
              sorted(inventory(package, root).items()) if shape == 'file'])
    bodies = {path: (root / path).read_bytes() for path in files}
    if observer is not None:
        observer(bodies)
    hashes = {path: hashlib.sha256(body).hexdigest() for path, body in bodies.items()}
    revision = hashlib.sha256(json.dumps([entry, hashes], ensure_ascii=False,
                                       sort_keys=True).encode('utf-8')).hexdigest()
    return bodies, hashes, revision


def document_id(entry):
    """Identity includes type and scope; equal prose never merges authority domains."""
    return json.dumps([entry.get(key) for key in
                       ('documentType', 'category', 'domain', 'name', 'scope')], ensure_ascii=False)


def sections(text):
    """Index ATX headings and explicit HTML IDs outside fenced code, without summarizing."""
    headings, offset, fence, pending = [], 0, None, None
    used = {}
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif fence is None:
            anchor = re.match(r'^\s*<a\s+id=[\"\']([^\"\']+)[\"\']\s*>\s*</a>\s*$', line)
            heading = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
            if anchor:
                pending = (anchor[1], offset)
            elif heading:
                title = heading[2]
                slug = re.sub(r'[^\w\- ]', '', title.casefold()).replace(' ', '-')
                number = used.get(slug, 0)
                used[slug] = number + 1
                anchor_id = pending[0] if pending else slug + (f'-{number}' if number else '')
                headings.append(dict(anchor=anchor_id, heading=title, level=len(heading[1]),
                                     start=pending[1] if pending else offset))
                pending = None
            elif line.strip():
                pending = None
        offset += len(line)
    for index, heading in enumerate(headings):
        heading['end'] = next((other['start'] for other in headings[index + 1:]
                               if other['level'] <= heading['level']), len(text))
    return headings


def read_document(root, path, anchor=None, revision=None, documents_root=None, observer=None):
    """Read canonical bytes with dependency freshness and complete entry guidance."""
    identity_root = root.resolve(strict=True)
    root = (documents_root or root).resolve(strict=True)
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Read path must be project-relative without traversal')
    check_path(root / relative, root)
    path = relative.as_posix()
    if len(relative.parts) >= 4 and relative.parts[:2] == ('docs', 'skills'):
        entry = catalog_entry(root, root.joinpath(*relative.parts[:3]), 'specification')
    else:
        entry = next((item for item in build_catalog(identity_root, root)['documents']
                      if path in (item.get('contentPaths') or [item['contentPath']])
                      or path == item['metadataPath']), None)
    if entry is None:
        raise ValueError('Read path is not a canonical Document content path')
    bodies, hashes, current = snapshot(root, entry, observer)
    allowed = entry.get('contentPaths') or [entry['contentPath']]
    if path not in allowed and path != entry['metadataPath']:
        raise ValueError('Read path is not a Document text source')
    if revision is not None and revision != current:
        raise ValueError('Stale document revision; search/read the current source again')
    text = bodies[path].decode('utf-8')
    spans = sections(text)
    selected = [item for item in spans if item['anchor'] == anchor] if anchor else []
    if anchor and len(selected) != 1:
        raise ValueError('Section anchor missing or ambiguous; read the full source')
    start, end = (selected[0]['start'], selected[0]['end']) if selected else (0, len(text))
    entry_path = entry['contentPath'] or entry['metadataPath']
    return dict(schemaVersion='0.1.0', kind='document-read', document=entry,
                documentId=document_id(entry),
                path=path, anchor=anchor, revision=current, sha256=hashes[path],
                start=start, end=end, text=text[start:end], sections=spans,
                entryPath=entry_path, entryText=(bodies[entry_path].decode('utf-8')
                                               if anchor or path != entry_path else None),
                dependencies=hashes, partial=bool(anchor),
                guidance='Selected sections are discovery aids. Read linked rules, decisions and exceptions before acting.')


def search(root: Path, query: str, document_type=None, category=None, limit=20, scope=None, documents_root=None, match='all', offset=0, observer=None) -> dict:
    terms = [term.casefold() for term in query.split() if term]
    if not terms:
        raise ValueError("Search query must contain non-whitespace text")
    if limit < 1 or limit > 100:
        raise ValueError("Search limit must be between 1 and 100")
    if match not in ('all', 'any') or type(offset) is not int or offset < 0:
        raise ValueError('Expected match all/any and nonnegative offset')
    document_type = TYPE_ALIASES.get(document_type, document_type)
    identity_root = root.resolve(strict=True)
    root = (documents_root or root).resolve(strict=True)
    matches = []
    for entry in build_catalog(identity_root, root)["documents"]:
        if document_type and entry["documentType"] != document_type:
            continue
        if category and entry["category"] != category:
            continue
        if scope and entry.get("scope", entry["metadata"].get("scope")) != scope:
            continue
        searchable = json.dumps(entry["metadata"], ensure_ascii=False)
        bodies, hashes, revision = snapshot(root, entry, observer)
        paths = entry.get("contentPaths") or ([entry["contentPath"]] if entry["contentPath"] else [])
        for path in paths:
            searchable += "\n" + bodies[path].decode('utf-8')
        folded = searchable.casefold()
        matched_terms = [term for term in terms if term in folded]
        if not matched_terms or (match == 'all' and len(matched_terms) != len(terms)):
            continue
        result = {key: value for key, value in entry.items() if key != "metadata"}
        for field in ("scope", "status"):
            if field not in result and field in entry["metadata"]:
                result[field] = entry["metadata"][field]
        result["score"] = sum(folded.count(term) for term in terms)
        result.update(documentId=document_id(entry), revision=revision,
                      dependencies=hashes, matchedTerms=matched_terms)
        result['sources'] = []
        for path in paths:
            text = bodies[path].decode('utf-8')
            if any(term in text.casefold() for term in terms):
                result['sources'].append(dict(path=path, sha256=hashes[path], sections=[
                    item for item in sections(text) if any(term in text[item['start']:item['end']].casefold()
                                                          for term in terms)]))
        matches.append(result)
    matches.sort(
        key=lambda item: (
            -(len(item['matchedTerms']) if match == 'any' else 0), -item["score"], item["documentType"], item["category"],
            item["domain"] or "", item["name"],
        )
    )
    return {
        "schemaVersion": "0.1.0",
        "kind": "document-search-results",
        "query": query,
        "count": len(matches[offset:offset + limit]),
        "results": matches[offset:offset + limit],
        "totalCount": len(matches), "offset": offset,
        "nextOffset": offset + limit if offset + limit < len(matches) else None,
        "match": match,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--query")
    operation.add_argument("--read-path", help="Canonical project-relative Document or docs/skills text path")
    parser.add_argument("--anchor", help="Read one ATX section by explicit HTML ID or heading slug; retains complete entry guidance")
    parser.add_argument("--revision", help="Require a matching package revision when reading; stale input fails closed")
    parser.add_argument("--match", choices=('all', 'any'), default='all', help="all preserves legacy AND search; any explicitly explores partial lexical matches")
    parser.add_argument("--offset", type=int, default=0, help="Result page offset; totalCount and nextOffset expose all matches")
    parser.add_argument("--type", choices=(*CATALOG_TYPES, *TYPE_ALIASES))
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--scope")
    parser.add_argument("--documents-root", type=Path, help="Physical workspace containing docs; runtime identity stays --project-root")
    args = parser.parse_args()
    try:
        if args.read_path:
            results = read_document(args.project_root, args.read_path, args.anchor, args.revision, args.documents_root)
        else:
            if args.anchor or args.revision:
                raise ValueError('--anchor and --revision require --read-path')
            results = search(args.project_root, args.query, args.type, args.category, args.limit, args.scope, args.documents_root, args.match, args.offset)
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
