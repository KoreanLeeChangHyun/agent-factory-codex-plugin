from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "skills" / "document"
CORE_HUMAN = (
    ROOT
    / ".agent-factory"
    / "document"
    / "specification"
    / "human"
    / "agent-factory-core"
    / "index.html"
)


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

        boundary_paragraphs = normalized_paragraphs(entry)
        self.assertTrue(
            any(
                "explorer working material" in paragraph
                and "managed agent session state" in paragraph
                and "separate logical roles" in paragraph
                for paragraph in boundary_paragraphs
            )
        )

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
                CORE_HUMAN
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
        self.assertIn("document/specification/human/<specification-id>/", document)
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

    def test_core_diagram_routes_and_accessibility_metadata_are_complete(self) -> None:
        diagram_path = (
            ROOT / "skills" / "convention" / "references" / "diagrams.md"
        )
        diagrams = diagram_path.read_text(encoding="utf-8")
        routes = set(
            re.findall(r"`(diagrams/(?:erd|behavior|sequence)\.md)`", diagrams)
        )
        self.assertEqual(
            {"diagrams/erd.md", "diagrams/behavior.md", "diagrams/sequence.md"},
            routes,
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertTrue((diagram_path.parent / route).is_file())
        retired = "agent-factory-core-diagrams.md"
        active_contracts = [ROOT / "AGENTS.md", *ROOT.joinpath("skills").rglob("*.md")]
        for contract in active_contracts:
            with self.subTest(contract=contract.relative_to(ROOT)):
                self.assertNotIn(retired, contract.read_text(encoding="utf-8"))
        self.assertFalse((diagram_path.parent / retired).exists())

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

    def test_convention_reference_inventory_is_fully_routed(self) -> None:
        convention = ROOT / "skills" / "convention"
        references = convention / "references"
        entry = (convention / "SKILL.md").read_text(encoding="utf-8")
        root_routes = set(re.findall(r"`references/([^`]+\.md)`", entry))
        declared_routes = set(root_routes)

        for route in root_routes:
            content = (references / route).read_text(encoding="utf-8")
            for nested in re.findall(r"^- Read `([^`]+\.md)`", content, re.MULTILINE):
                declared_routes.add((Path(route).parent / nested).as_posix())

        inventory = {
            path.relative_to(references).as_posix()
            for path in references.rglob("*.md")
        }
        self.assertEqual(inventory, declared_routes)

    def test_workspace_navigation_claims_stay_within_five_activity_boundary(self) -> None:
        specification = (
            DOCUMENT / "references" / "specification.md"
        ).read_text(encoding="utf-8")
        diagrams = (
            ROOT / "skills" / "convention" / "references" / "diagrams.md"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "virtual `프로젝트 스킬` category",
            "Workspace `skills/` Activity",
            "through Planning",
        ):
            with self.subTest(contract="specification", forbidden=forbidden):
                self.assertNotIn(forbidden, specification)
        for forbidden in (
            "Workspace --> Main",
            "Workspace --> Work",
            "Planning[",
            "ExplorerActivity",
            "temporary evidence trees",
        ):
            with self.subTest(contract="diagrams", forbidden=forbidden):
                self.assertNotIn(forbidden, diagrams)

        self.assertIn("neutral read-only discovery or exposure utility", specification)
        self.assertIn("Non-visible read-only discovery utility", diagrams)
        self.assertIn("Producing managed Agent run only", diagrams)

    def test_core_representation_provenance_paths_resolve(self) -> None:
        ai = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")

        ai_source_paragraphs = "\n".join(
            paragraph
            for paragraph in re.split(r"\n\s*\n", ai)
            if re.search(
                r"comes? from|recorded in|supporting, non-canonical evidence|established by",
                paragraph,
                re.IGNORECASE,
            )
        )
        targets = {
            value
            for value in re.findall(r"`([^`]+)`", ai_source_paragraphs)
            if value.startswith((".agent-factory/", ".codex-plugin/", "skills/"))
        }
        human_provenance = "\n".join(
            re.findall(r'<p class="provenance">(.*?)</p>', human, re.DOTALL)
        )
        targets.update(unescape(value) for value in re.findall(r"<code>(.*?)</code>", human_provenance))

        local_targets = {
            value
            for value in targets
            if value.startswith((".agent-factory/", ".codex-plugin/", "skills/"))
            and "<" not in value
            and not value.startswith(("http://", "https://"))
        }
        self.assertTrue(local_targets)
        runtime_request_targets = {
            target
            for target in local_targets
            if target.startswith(".agent-factory/agent/")
        }
        tracked_targets = local_targets - runtime_request_targets
        self.assertTrue(runtime_request_targets)
        self.assertTrue(tracked_targets)
        for target in sorted(runtime_request_targets):
            with self.subTest(runtime_provenance=target):
                self.assertRegex(
                    target,
                    r"^\.agent-factory/agent/[a-z0-9][a-z0-9-]*/runs/"
                    r"run-\d{8}T\d{12}Z-[0-9a-f]{8}/request\.md$",
                )
        for target in sorted(tracked_targets):
            with self.subTest(target=target):
                self.assertTrue((ROOT / target).exists())

    def test_six_skill_decision_has_exact_managed_request_provenance(self) -> None:
        decision_request = (
            ".agent-factory/agent/six-skill-core-sync-work-20260830/runs/"
            "run-20260830T103238358728Z-5e61ab5d/request.md"
        )
        ai = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")

        self.assertIn(decision_request, ai)
        self.assertIn(decision_request, human)
        self.assertNotIn("active Human request for the Tool Skill", ai)
        self.assertNotIn("현재 Tool Skill을 추가하라는 Human 결정", human)

    def test_human_skip_timing_is_aligned_in_ai_and_human_views(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        diagrams = (
            ROOT / "skills" / "convention" / "references" / "diagrams.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")
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

    def test_workspace_activity_and_explorer_boundaries_are_aligned(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")
        normalized_ai_core = " ".join(ai_core.split())
        for path in (
            ".agent-factory/document/original/",
            ".agent-factory/document/processed/",
            ".agent-factory/workspace/explorer/",
        ):
            self.assertIn(path, ai_core)
            self.assertIn(path, human)
        for phrase in (
            "temporary execution-only material remains in the producing managed Agent run",
            "exactly five top-level Activities in this order: 일정, 에이전트, 문서, 로그, 테스트",
            "every Activity's Primary Sidebar information architecture",
            "remain Human-owned and undecided",
            "both forms must exist and remain byte-identical",
            "packaged files are the reusable installation source",
        ):
            self.assertIn(phrase, normalized_ai_core)
        self.assertRegex(
            normalized_ai_core.casefold(),
            r"internal read-only .*file/project metadata projection and .*skill-navigation projection "
            r"(?:define neither|do not define) a top-level activity "
            r"(?:nor nesting|or authorize nesting) under one of the five",
        )
        for phrase in (
            "실행 전용 임시 자료",
            "Activity Bar에는 일정, 에이전트, 문서, 로그, 테스트가 이 순서로 정확히 다섯 개만 있습니다",
            "Primary Sidebar 정보 구조, 상세 기능",
            "Human의 후속 결정을 기다립니다",
            "세 개의 핵심 코드 파일과 필수 동반 notice는 두 형태에 함께 존재하고 각각 byte 단위로 같아야 합니다",
            "THIRD_PARTY_NOTICES.txt",
            "네 번째 브라우저 코드 파일이 아닙니다",
            "패키지 에셋이 재사용 설치 원본",
        ):
            self.assertIn(phrase, human)
        self.assertRegex(
            " ".join(human.split()),
            r"내부 읽기 전용 .*workspace/explorer/.*File/Project metadata 투영과 "
            r".*workspace/skills/.*Skill navigation 투영은 상단 Activity 또는 "
            r"다섯 범주 아래의 navigation(?: 계층)?을 정의하지 않습니다",
        )
        self.assertNotIn("<td>로드맵</td>", human)
        self.assertNotIn("여섯 영역", human)

    def test_tool_and_gather_boundaries_are_aligned_in_both_views(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")
        normalized_ai_core = " ".join(ai_core.split())
        for phrase in (
            "exactly six public distributed Skills",
            "Tool never escalates scope automatically",
            "creates no `.agent-factory/tool/` root or Workspace Activity",
            "Google Drive and OneDrive provider scripts retain their",
        ):
            self.assertIn(phrase, normalized_ai_core)
        for phrase in (
            "public distributed Skill",
            "여섯 개입니다",
            "Tool은 Workspace의 여섯 번째 Activity가 아닙니다",
            "scope를 임의 승격하지 않습니다",
            "Google Drive와 OneDrive의 auth/token 코드는 현재 Gather script에 결합",
            "Tool registry/state 저장소",
        ):
            self.assertIn(phrase, human)

    def test_core_human_connectors_use_accessible_svg_or_visible_prose(self) -> None:
        human = CORE_HUMAN.read_text(encoding="utf-8")
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
