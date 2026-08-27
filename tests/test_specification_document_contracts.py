from __future__ import annotations

from html.parser import HTMLParser
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = ROOT / "skills" / "specification"


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


class SpecificationDocumentContractTests(unittest.TestCase):
    def test_packaged_document_has_exactly_three_assets(self) -> None:
        document = SPECIFICATION / "assets" / "document"
        self.assertEqual(
            {path.name for path in document.iterdir()},
            {"index.html", "styles.css", "app.js"},
        )

    def test_packaged_document_is_local_semantic_and_grounded(self) -> None:
        html = (SPECIFICATION / "assets" / "document" / "index.html").read_text(
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
        document = SPECIFICATION / "assets" / "document"
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
            SPECIFICATION / "references" / "specification-document.md"
        ).read_text(encoding="utf-8")
        project_skill = (
            SPECIFICATION / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")
        for activity in ("explorer/", "information/refined/human/", "skills/"):
            self.assertIn(activity, document)
        self.assertIn("information/refined/human/<specification-id>/", document)
        self.assertIn("<plugin-root>/skills/", project_skill)
        self.assertIn("<project-root>/.codex/skills/<project-skill>/", project_skill)
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
                    r"complete <category>-<name> value unchanged.*directory name.*name field.*frontmatter.*match exactly",
                    paragraph,
                )
                for paragraph in paragraphs
            )
        )
        self.assertTrue(
            any(
                re.search(
                    r"do not create or mirror.*plugin repository.*distributed skills below its \.codex/",
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
            "assets": r"assets/ contains reference material",
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
                "refined",
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


if __name__ == "__main__":
    unittest.main()
