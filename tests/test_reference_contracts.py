"""Optional reference assets and the plugin's owned domain boundaries."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class ReferenceContractTests(unittest.TestCase):
    def test_existing_reference_documents_have_local_assets_and_korean_baseline(self):
        self.assertFalse((ROOT / ".codex/skills").exists())
        for entry in sorted((ROOT / "docs/specifications").glob("*/index.html")):
            with self.subTest(document=entry.parent.name):
                package = entry.parent
                html = (package / "index.html").read_text()
                parser = Tags(); parser.feed(html)
                self.assertIn(("html", {"lang": "ko"}), parser.tags)
                self.assertNotIn("[[", html)
                self.assertFalse(any("data-template-placeholder" in attrs for _, attrs in parser.tags))
                for asset in ("styles.css", "app.js"):
                    self.assertTrue((package / asset).is_file())
                self.assertTrue(re.search(r"[가-힣]", html))
                self.assertIn("main", {tag for tag, _ in parser.tags})
                for tag, attrs in parser.tags:
                    # Standalone executable and stylesheet dependencies must resolve locally.
                    target = attrs.get("src") if tag == "script" else attrs.get("href") if tag == "link" and attrs.get("rel") == "stylesheet" else None
                    if target:
                        self.assertFalse(target.startswith(("https:", "http:", "//")))
                        self.assertTrue((package / target).is_file(), target)
                    if tag == "svg":
                        self.assertTrue(attrs.get("aria-hidden") == "true" or attrs.get("role") == "img")

    def test_placeholder_attribute_detection_preserves_explanatory_text(self):
        prose = Tags()
        prose.feed('<p>모든 data-template-placeholder 속성을 제거한다.</p>')
        self.assertFalse(any("data-template-placeholder" in attrs for _, attrs in prose.tags))
        for markup in ('<h2 data-template-placeholder>제목</h2>',
                       '<meta name="identity" data-template-placeholder="true">'):
            parser = Tags(); parser.feed(markup)
            self.assertTrue(any("data-template-placeholder" in attrs for _, attrs in parser.tags))

    def test_document_semantics_and_mcp_ownership_are_explicit(self):
        contract = (ROOT / "skills/convention/SKILL.md").read_text()
        core = (ROOT / "skills/convention/references/agent-factory-core.md").read_text()
        for phrase in ("Original", "Processed", "Specification", "provenance", "cloud"):
            self.assertIn(phrase, contract)
        for phrase in ("exactly two public distributed Skills", "MCP Document domain", "MCP Gather domain", "MCP Tool domain", "MCP Workspace domain"):
            self.assertIn(phrase, core)

    def test_six_activities_cloud_ownership_and_legacy_preservation(self):
        core = (ROOT / "skills/convention/SKILL.md").read_text()
        for phrase in ("일정, 에이전트, 문서, 외부연동, 로그, 테스트", "Local `exec.py`, `loop.py`", "code retirement is never deletion authority", "Explorer and Interview", "not extra public Skills or roles"):
            self.assertIn(phrase, core)

    def test_graph_skip_decomposition_and_human_decisions_remain_owned(self):
        agent = " ".join((ROOT / "skills/agent/SKILL.md").read_text().split())
        for phrase in ("exactly three Agent roles", "Main -> Work -> Verification", "Human skip", "after Work completion", "shared mutable resource", "distinct Agent", "explicitly asks to execute, proceed, or delegate", "does not authorize execution or delegation", "Main-owned", "Work and Verification never commit"):
            # Main-owned publication is expressed as Main performs it directly.
            if phrase == "Main-owned":
                self.assertIn("Main promptly performs", agent)
            else:
                self.assertIn(phrase, agent)
        rule = (ROOT / "skills/convention/references/explicit-human-input.md").read_text().lower()
        for phrase in ("main asks the human", "work and verification report", "do not infer, invent, silently default", "ask the human and wait"):
            self.assertIn(phrase, " ".join(rule.split()))
        testing = (ROOT / "skills/convention/references/testing.md").read_text().lower()
        for phrase in ("smallest relevant focused test set", "cross-domain impact", "human explicitly requests", "independent verification role"):
            self.assertIn(phrase, " ".join(testing.split()))

    def test_reference_inventory_and_source_backed_diagrams(self):
        convention = ROOT / "skills/convention"
        entry = (convention / "SKILL.md").read_text()
        routes = set(re.findall(r"`references/([^`]+\.md)`", entry))
        declared = set(routes)
        for route in routes:
            content = (convention / "references" / route).read_text()
            for nested in re.findall(r"^- Read `([^`]+\.md)`", content, re.M):
                declared.add((Path(route).parent / nested).as_posix())
        self.assertEqual(declared, {p.relative_to(convention / "references").as_posix() for p in (convention / "references").rglob("*.md")})
        diagrams = (convention / "references/diagrams.md").read_text()
        for phrase in ("accTitle", "accDescr", "Mermaid"):
            self.assertIn(phrase, diagrams)
