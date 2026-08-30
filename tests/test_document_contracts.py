from __future__ import annotations

from html.parser import HTMLParser
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "skills" / "document"


class TemplateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.tags.append((tag, dict(attrs)))


def semantic_tokens(content: str) -> set[str]:
    """Ignore Markdown punctuation, prose order, and line wrapping."""
    return set(re.findall(r"[a-z0-9]+", content.lower()))


def normalized_paragraphs(content: str) -> list[str]:
    return [
        " ".join(re.sub(r"[`*_]", "", block).lower().split())
        for block in re.split(r"\n\s*\n", content)
        if block.strip()
    ]


class DocumentContractTests(unittest.TestCase):
    def test_three_document_types_are_loose_and_specification_is_paired(self) -> None:
        entry = (DOCUMENT / "SKILL.md").read_text(encoding="utf-8")
        normalized = " ".join(entry.casefold().split())
        for term in (
            "original (원본문서)",
            "processed (가공문서)",
            "specification (스펙 문서)",
            "original -> processed -> specification",
            "not a mandatory pipeline",
            "one-to-many",
            "many-to-one",
            "many-to-many",
            "refined as a fourth active document type",
        ):
            self.assertIn(term, normalized)

        self.assertFalse((ROOT / "skills" / "specification").exists())
        references = DOCUMENT / "references"
        self.assertEqual(
            {path.name for path in references.glob("*.md")},
            {"original.md", "processed.md", "specification.md"},
        )
        self.assertFalse((references / "specification-document.md").exists())

    def test_information_formats_and_pair_completion_are_enforced(self) -> None:
        paths = {
            "instructions": ROOT / "AGENTS.md",
            "bootstrap": ROOT / "skills" / "convention" / "assets" / "AGENTS.md",
            "convention": ROOT / "skills" / "convention" / "SKILL.md",
            "core_ai": (
                ROOT
                / "skills"
                / "convention"
                / "references"
                / "agent-factory-core.md"
            ),
            "document": ROOT / "skills" / "document" / "SKILL.md",
            "specification": (
                ROOT
                / "skills"
                / "document"
                / "references"
                / "specification.md"
            ),
            "core_human": (
                ROOT
                / ".agent-factory"
                / "information"
                / "refined"
                / "human"
                / "agent-factory-core"
                / "index.html"
            ),
        }
        contents = {
            name: path.read_text(encoding="utf-8").lower()
            for name, path in paths.items()
        }

        for name in ("instructions", "bootstrap", "convention", "core_ai"):
            with self.subTest(contract=name):
                content = contents[name]
                self.assertIn("source-appropriate", content)
                self.assertIn("markdown (`.md`)", content)
                self.assertIn("legacy-inquery", content)

        for name in (
            "instructions",
            "bootstrap",
            "convention",
            "core_ai",
            "document",
            "specification",
        ):
            with self.subTest(pair=name):
                content = contents[name]
                normalized_content = " ".join(content.split())
                self.assertIn("one-sided change", content)
                self.assertIn("incomplete and unacceptable", normalized_content)
                self.assertRegex(content, r"must not be reported as completed|do not report")

        human = contents["core_human"]
        self.assertIn("source-appropriate", human)
        self.assertIn("markdown", human)
        self.assertIn("legacy-inquery", human)
        self.assertIn("한쪽만 바꾼 변경은 불완전하고 허용되지 않습니다", human)
        self.assertIn("완료로 보고해서는 안 됩니다", human)

    def test_packaged_document_has_exactly_three_assets(self) -> None:
        document = DOCUMENT / "assets" / "document"
        self.assertEqual(
            {path.name for path in document.iterdir()},
            {"index.html", "styles.css", "app.js"},
        )

    def test_packaged_document_is_local_semantic_and_grounded(self) -> None:
        html = (DOCUMENT / "assets" / "document" / "index.html").read_text(
            encoding="utf-8"
        )
        parser = TemplateParser()
        parser.feed(html)
        tags = {tag for tag, _ in parser.tags}
        self.assertTrue({"header", "nav", "main", "section", "table"} <= tags)
        self.assertEqual(
            {attrs.get("id") for tag, attrs in parser.tags if tag == "section"},
            {"scope", "decisions", "requirements", "evidence", "questions"},
        )
        self.assertIn(("html", {"lang": "ko"}), parser.tags)
        self.assertTrue(
            any(
                tag == "link" and attrs.get("href") == "./styles.css"
                for tag, attrs in parser.tags
            )
        )
        self.assertTrue(
            any(
                tag == "script" and attrs.get("src") == "./app.js"
                for tag, attrs in parser.tags
            )
        )
        self.assertTrue(
            any("data-template-placeholder" in attrs for _, attrs in parser.tags)
        )
        for _, attrs in parser.tags:
            for attribute in ("href", "src"):
                value = attrs.get(attribute, "") or ""
                self.assertFalse(value.startswith(("http://", "https://", "//")))

    def test_packaged_icons_are_inline_svg(self) -> None:
        document = DOCUMENT / "assets" / "document"
        html = (document / "index.html").read_text(encoding="utf-8")
        parser = TemplateParser()
        parser.feed(html)
        icon_elements = [
            tag
            for tag, attrs in parser.tags
            if any("icon" in name.lower() for name in (attrs.get("class") or "").split())
        ]
        self.assertTrue(icon_elements)
        self.assertEqual(set(icon_elements), {"svg"})

        packaged_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in document.iterdir()
            if path.is_file()
        ).lower()
        self.assertFalse(
            re.search(
                r"<img\b|@font-face|icon-font|url\([^)]*\.(?:png|jpe?g|gif|webp|ico)",
                packaged_source,
            )
        )

    def test_guidance_preserves_topology_pairing_and_identity_boundaries(self) -> None:
        document = (
            DOCUMENT / "references" / "specification.md"
        ).read_text(encoding="utf-8")
        project_skill = document
        self.assertIn("## Workspace projection", document)
        self.assertIn("skills/workspace/references/interface.md", document)
        self.assertIn("document remains owned by Document", document)
        self.assertIn("Workspace navigation does not refine content", document)
        self.assertIn("information/refined/human/<specification-id>/", document)
        self.assertIn("<plugin-root>/skills/", project_skill)
        self.assertIn("<project-root>/.codex/skills/<category>-<name>/", project_skill)
        paragraphs = normalized_paragraphs(project_skill)
        self.assertTrue(
            any(
                re.search(
                    r"canonical form <category>-<name>.*category classifies.*name identifies",
                    paragraph,
                )
                for paragraph in paragraphs
            )
        )
        self.assertTrue(
            any(
                re.search(
                    r"complete name.*exactly matches both the directory.*name field.*frontmatter",
                    paragraph,
                )
                for paragraph in paragraphs
            )
        )
        self.assertTrue(
            any(
                re.search(
                    r"do not create.*mirror.*distributed skills below this repository's \.codex/",
                    paragraph,
                )
                for paragraph in paragraphs
            )
        )
        self.assertTrue(
            any(
                re.search(r"project skill is one self-contained directory", paragraph)
                for paragraph in paragraphs
            )
        )
        role_patterns = {
            "skill.md": r"skill\.md is the ai-readable entry point and instruction document",
            "agents": r"agents/ contains agent configuration as yaml files",
            "assets": r"assets/ contains reference material the agent may inspect or reuse",
            "references": r"references/ contains.*supporting ai-readable documents as markdown files",
            "scripts": r"scripts/ contains scripts the agent may execute or reuse",
        }
        for role, pattern in role_patterns.items():
            with self.subTest(role=role):
                self.assertTrue(
                    any(re.search(pattern, paragraph) for paragraph in paragraphs)
                )
        self.assertTrue(
            {
                "specification",
                "paired",
                "project",
                "skill",
                "korean",
                "human",
                "readable",
                "semantic",
                "alignment",
            }
            <= semantic_tokens(document + project_skill)
        )

    def test_core_mermaid_sources_have_unique_accessibility_metadata(self) -> None:
        diagrams = (
            ROOT / "skills" / "convention" / "references" / "diagrams.md"
        ).read_text(encoding="utf-8")
        blocks = re.findall(r"```mermaid\n(.*?)```", diagrams, flags=re.DOTALL)
        self.assertEqual(len(blocks), 9)
        titles = []
        descriptions = []
        for block in blocks:
            title = re.findall(r"^\s*accTitle:\s*(.+)$", block, flags=re.MULTILINE)
            description = re.findall(r"^\s*accDescr:\s*(.+)$", block, flags=re.MULTILINE)
            self.assertEqual(len(title), 1)
            self.assertEqual(len(description), 1)
            titles.extend(title)
            descriptions.extend(description)
        self.assertEqual(len(set(titles)), len(titles))
        self.assertEqual(len(set(descriptions)), len(descriptions))

    def test_human_skip_timing_is_aligned_in_ai_and_human_views(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        diagrams = (
            ROOT / "skills" / "convention" / "references" / "diagrams.md"
        ).read_text(encoding="utf-8")
        human = (
            ROOT
            / ".agent-factory"
            / "information"
            / "refined"
            / "human"
            / "agent-factory-core"
            / "index.html"
        ).read_text(encoding="utf-8")
        normalized_ai_core = " ".join(ai_core.split())
        for phrase in (
            "Human-only, evidenced control-plane intent",
            "not a graph transition or completion",
            "only after the current initial or revision Work completes",
            "starts no next or additional Verification",
        ):
            self.assertIn(phrase, normalized_ai_core)
        for phrase in (
            "Human-only skip intent",
            "not a transition or completion",
            "evaluated only after current",
            "start no next or additional Verification",
        ):
            self.assertIn(phrase, diagrams)
        for phrase in (
            "Human만 근거를 갖춰 기록할 수 있는 skip",
            "제어면 의도이지 전이나 완료가 아니며",
            "현재 initial 또는 revision Work가 끝난 뒤에만 적용",
            "다음 또는 추가 Verification을 시작하지 않고 END에 도달",
        ):
            self.assertIn(phrase, human)

    def test_workspace_explorer_ownership_is_aligned_in_ai_and_human_views(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = (
            ROOT
            / ".agent-factory"
            / "information"
            / "refined"
            / "human"
            / "agent-factory-core"
            / "index.html"
        ).read_text(encoding="utf-8")
        normalized_ai_core = " ".join(ai_core.split())
        for path in (".agent-factory/explorer/", ".agent-factory/workspace/explorer/"):
            self.assertIn(path, ai_core)
            self.assertIn(path, human)
        for phrase in (
            "temporary Work/Explorer evidence storage",
            "read-only Workspace File/Project Explorer Activity projection",
            "without copying, editing, moving, deleting",
        ):
            self.assertIn(phrase, normalized_ai_core)
        for phrase in (
            "임시 evidence workspace",
            "읽기 전용 Activity 투영",
            "편집·이동·삭제·승격하지 않습니다",
        ):
            self.assertIn(phrase, human)

    def test_core_human_connectors_use_accessible_svg_or_visible_prose(self) -> None:
        human = (
            ROOT
            / ".agent-factory"
            / "information"
            / "refined"
            / "human"
            / "agent-factory-core"
            / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r'<(?:span|code)[^>]*aria-hidden="true"[^>]*>\s*[+=→]\s*<', human)
        )
        parser = TemplateParser()
        parser.feed(human)
        connector_svgs = [
            attrs
            for tag, attrs in parser.tags
            if tag == "svg" and "connector-icon" in (attrs.get("class") or "").split()
        ]
        self.assertTrue(connector_svgs)
        for attrs in connector_svgs:
            self.assertEqual(attrs.get("aria-hidden"), "true")
            self.assertEqual(attrs.get("focusable"), "false")
        self.assertIn("Original / Processed / Specification", human)


if __name__ == "__main__":
    unittest.main()
