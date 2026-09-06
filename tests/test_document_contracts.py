"""Final publication-source contracts; independent semantic review is still required."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("agent", "convention", "document", "gather", "tool", "workspace")


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class DocumentContractTests(unittest.TestCase):
    def test_reciprocal_identity_complete_local_assets_and_korean_baseline(self):
        self.assertFalse((ROOT / ".codex/skills").exists())
        for name in NAMES:
            with self.subTest(name=name):
                package = ROOT / ".agent-factory/document/specification" / name
                html = (package / "index.html").read_text()
                ai = (ROOT / "skills" / name / "SKILL.md").read_text()
                parser = Tags(); parser.feed(html)
                self.assertIn(("html", {"lang": "ko"}), parser.tags)
                for key, value in (("specification-id", name), ("ai-root", f"skills/{name}/"), ("ai-binding-entry", f"skills/{name}/SKILL.md")):
                    self.assertIn(("meta", {"name": f"agent-factory:{key}", "content": value}), parser.tags)
                for value in (f"specification-id: {name}", f"ai-root: skills/{name}/", f"human-entry: .agent-factory/document/specification/{name}/index.html"):
                    self.assertIn(value, ai)
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

    def test_document_semantics_and_publication_review_are_explicit(self):
        entry = (ROOT / "skills/document/SKILL.md").read_text()
        contract = (ROOT / "skills/document/references/specification.md").read_text()
        for phrase in ("Original", "Processed", "Specification", "provenance", "cloud"):
            self.assertIn(phrase, entry)
        for phrase in ("one semantic body", "independent semantic review", "source order", "hierarchy", "data-source-lines", "data-source-sha256", "document_template", "64 KiB", "license notices", "validate_pair", "category>-<title", "readable baseline without JavaScript", "exact commit", "one complete AI root", "one complete Human root", "failures preserve prior accepted authority"):
            self.assertIn(phrase, contract)
        human = (ROOT / ".agent-factory/document/specification/document/index.html").read_text()
        for phrase in ("document_template", "64 KiB", "라이선스", "validate_pair", "독립 Verification", "misaligned"):
            self.assertIn(phrase, human)

    def test_six_activities_cloud_ownership_and_legacy_preservation(self):
        core = (ROOT / "skills/convention/SKILL.md").read_text()
        for phrase in ("일정, 에이전트, 문서, 외부연동, 로그, 테스트", "Local `exec.py`, `loop.py`", "code retirement is never deletion authority", "Explorer and Interview", "not extra public Skills or roles"):
            self.assertIn(phrase, core)
        workspace = (ROOT / "skills/workspace/SKILL.md").read_text()
        for phrase in ("cloud", "PostgreSQL", "object storage", "Missing tools, account or scope", "Local exec/loop retains graph authority"):
            self.assertIn(phrase, workspace)
        human = (ROOT / ".agent-factory/document/specification/workspace/index.html").read_text()
        for label in ("일정", "에이전트", "문서", "외부연동", "로그", "테스트"):
            self.assertIn(label, human)

    def test_graph_skip_decomposition_and_human_decisions_remain_owned(self):
        agent = " ".join((ROOT / "skills/agent/SKILL.md").read_text().split())
        for phrase in ("exactly three Agent roles", "Main -> Work -> Verification", "Human skip", "after Work completion", "shared mutable resources", "distinct Agent IDs", "Main-owned", "Work and Verification never commit"):
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
        for name in NAMES:
            human = (ROOT / ".agent-factory/document/specification" / name / "index.html").read_text()
            self.assertIn(f'data-ai-source="skills/{name}/SKILL.md"', human)
