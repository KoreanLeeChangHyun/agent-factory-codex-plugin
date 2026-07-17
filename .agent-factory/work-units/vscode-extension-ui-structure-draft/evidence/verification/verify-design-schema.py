from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path.cwd()
DESIGN_ROOT = ROOT / "docs/design-documents/vscode-extension-ui-structure"


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


manifest = read_json(DESIGN_ROOT / "data/manifest.json")
sections = {
    section["id"]: read_json(DESIGN_ROOT / section["path"])
    for section in manifest["sections"]
}
collections = {
    name: read_json(DESIGN_ROOT / relative_path)
    for name, relative_path in manifest["collections"].items()
}
diagrams = [
    read_json(DESIGN_ROOT / item["source"])
    for item in collections["diagrams"]["items"]
]
work_unit = read_json(ROOT / manifest["sourceWorkUnit"]["path"])
schema = read_json(DESIGN_ROOT / manifest["schema"])

composite = {
    "manifest": manifest,
    "sections": sections,
    "collections": collections,
    "diagrams": diagrams,
    "workUnitSummary": {
        "id": work_unit["id"],
        "title": work_unit["title"],
    },
    "workUnitReview": {
        "acceptanceCriteria": work_unit["acceptanceCriteria"],
        "definitionOfDone": work_unit["definitionOfDone"],
        "testCriteria": work_unit["testCriteria"],
        "aiChecklist": work_unit["aiChecklist"],
        "humanChecklist": work_unit["humanChecklist"],
        "humanReviewMethod": work_unit["humanReviewMethod"],
    },
}

Draft202012Validator.check_schema(schema)
errors = sorted(Draft202012Validator(schema).iter_errors(composite), key=lambda error: list(error.path))
if errors:
    for error in errors:
        pointer = "/".join(str(part) for part in error.absolute_path)
        print(f"FAIL /{pointer}: {error.message}")
    raise SystemExit(1)

print("PASS Draft 2020-12 Design Document schema self-check")
print("PASS assembled manifest, sections, collections, diagrams and Work Unit review data")
print(f"RESULT PASS 1 schema, {len(sections)} sections, {len(collections)} collections, {len(diagrams)} diagrams")
