"""Exercise the owning cloud validator against the complete final distribution.

These structural checks deliberately do not attest Korean semantic equivalence.
Verification must separately review the six complete Human/AI bodies.
"""
from pathlib import Path
import re
import unittest

from mcp_dependency import ApplicationError, fixture_pair, source_files, validate_pair

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("agent", "convention", "document", "gather", "tool", "workspace")


class SpecificationCoverageTests(unittest.TestCase):
    def test_all_complete_distributable_pairs_use_owning_validator(self):
        self.assertEqual(validate_pair.__module__, "app.modules.document.pair")
        for name in NAMES:
            with self.subTest(name=name):
                files = source_files(ROOT, name)
                result = validate_pair(files, fixture_pair(files, name), name)
                self.assertEqual(result["coverage"], "complete")
                self.assertEqual(result["sources"][0], f"skills/{name}/SKILL.md")

    def test_source_and_translation_corruption_fail_closed(self):
        for fault in ("missing", "added", "stale", "reordered", "gap", "empty", "duplicate", "placeholder", "reciprocal", "asset-review"):
            with self.subTest(fault=fault):
                files = source_files(ROOT, "document")
                pair = fixture_pair(files, "document")
                entry = "docs/specifications/document/index.html"
                html = files[entry].decode()
                if fault == "missing":
                    del files["skills/document/references/processed.md"]
                elif fault == "added":
                    files["skills/document/references/new.md"] = b"New rule\n"
                elif fault == "stale":
                    files["skills/document/SKILL.md"] += b"Changed rule\n"
                elif fault == "reordered":
                    html = html.replace('data-ai-source="skills/document/SKILL.md"', 'data-ai-source="TEMP"', 1).replace('data-ai-source="skills/document/agents/openai.yaml"', 'data-ai-source="skills/document/SKILL.md"', 1).replace('data-ai-source="TEMP"', 'data-ai-source="skills/document/agents/openai.yaml"', 1)
                elif fault == "gap":
                    html = html.replace('data-source-lines="1-11"', 'data-source-lines="2-11"', 1)
                elif fault == "empty":
                    html = re.sub(r'(<article data-source-lines="1-11"[^>]*>).*?(</article>)', r'\1\2', html, count=1, flags=re.S)
                elif fault == "duplicate":
                    html = html.replace('</main>', '<section data-ai-source="skills/document/SKILL.md"></section></main>')
                elif fault == "placeholder":
                    html = html.replace('<html ', '<html data-template-placeholder ', 1)
                elif fault == "reciprocal":
                    html = html.replace('name="agent-factory:specification-id" content="document"', 'name="agent-factory:specification-id" content="wrong"')
                elif fault == "asset-review":
                    files["docs/specifications/document/app.js"] += b"\n// changed\n"
                files[entry] = html.encode()
                # Refresh synthetic review hashes except the intentionally stale asset review.
                if fault != "asset-review": pair = fixture_pair(files, "document")
                with self.assertRaises(ApplicationError):
                    validate_pair(files, pair, "document")
