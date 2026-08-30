from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "skills" / "document"
PUBLIC_SKILLS = ("agent", "convention", "document", "gather", "tool", "workspace")
CORE_HUMAN = (
    ROOT
    / ".agent-factory"
    / "document"
    / "specification"
    / "convention"
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
    def test_every_distributed_skill_has_one_exact_human_specification_pair(self) -> None:
        self.assertFalse((ROOT / ".codex" / "skills").exists())
        for skill_name in PUBLIC_SKILLS:
            with self.subTest(skill=skill_name):
                human_path = ROOT / ".agent-factory/document/specification" / skill_name / "index.html"
                human = human_path.read_text(encoding="utf-8")
                skill = (ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(
                    f'<meta name="agent-factory:specification-id" content="{skill_name}">', human
                )
                self.assertIn(
                    f'<meta name="agent-factory:ai-root" content="skills/{skill_name}/">', human
                )
                self.assertIn(
                    f'<meta name="agent-factory:ai-binding-entry" content="skills/{skill_name}/SKILL.md">', human
                )
                self.assertIn(f"specification-id: {skill_name}", skill)
                self.assertIn(
                    f"human-entry: .agent-factory/document/specification/{skill_name}/index.html", skill
                )
                self.assertIn(f"ai-root: skills/{skill_name}/", skill)
                parser = TemplateParser()
                parser.feed(human)
                mappings = [
                    attrs["data-ai-sources"]
                    for tag, attrs in parser.tags
                    if tag == "section" and attrs.get("data-ai-sources")
                ]
                self.assertTrue(mappings)
                self.assertTrue(any(f"skills/{skill_name}/SKILL.md" in item for item in mappings))
                for source in {path for mapping in mappings for path in mapping.split(";")}:
                    self.assertTrue(source.startswith(f"skills/{skill_name}/"), source)
                    self.assertTrue((ROOT / source).is_file(), source)
                self.assertNotIn("[[", human)
        self.assertFalse((ROOT / ".agent-factory/document/specification/agent-factory-core").exists())

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
            {"adapter.md", "original.md", "processed.md", "specification.md"},
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
        }
        contents = {
            name: path.read_text(encoding="utf-8").lower()
            for name, path in paths.items()
        }

        for name in ("convention", "core_ai"):
            with self.subTest(contract=name):
                content = contents[name]
                self.assertIn("source-appropriate", content)
                self.assertIn("markdown (`.md`)", content)
                self.assertIn("legacy-inquery", content)

        for name in (
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
                self.assertRegex(
                    normalized_content,
                    r"must not be reported as completed|do not report",
                )

        for skill_name in PUBLIC_SKILLS:
            human = (
                ROOT / ".agent-factory/document/specification" / skill_name / "index.html"
            ).read_text(encoding="utf-8")
            self.assertRegex(human, r"양쪽(?:의)? 의미 변경은 함께 반영해야 합니다")
            self.assertIn(f"skills/{skill_name}/", human)

    def test_project_skill_and_specification_pair_contract_is_adapter_scoped(self) -> None:
        instructions_path = ROOT / "AGENTS.md"
        bootstrap_path = ROOT / "skills/convention/assets/AGENTS.md"
        self.assertEqual(instructions_path.read_bytes(), bootstrap_path.read_bytes())

        instructions = " ".join(instructions_path.read_text(encoding="utf-8").split())
        self.assertIn(
            "skills/convention/references/agent-factory-core.md", instructions
        )
        self.assertIn(
            "skills/convention/references/directory-structure.md", instructions
        )

        contracts = {
            "convention": " ".join(
                (ROOT / "skills/convention/SKILL.md").read_text(encoding="utf-8").split()
            ),
            "core": " ".join(
                (ROOT / "skills/convention/references/agent-factory-core.md")
                .read_text(encoding="utf-8")
                .split()
            ),
            "document": " ".join(
                (ROOT / "skills/document/SKILL.md").read_text(encoding="utf-8").split()
            ),
            "specification": " ".join(
                (ROOT / "skills/document/references/specification.md")
                .read_text(encoding="utf-8")
                .split()
            ),
        }
        for name, contract in contracts.items():
            with self.subTest(contract=name):
                self.assertIn("exactly one resolved AI-facing", contract)
                self.assertIn("exactly one resolved Human-facing", contract)
                self.assertIn("same stable identity", contract)
                self.assertRegex(
                    contract,
                    r"adapter-resolved|resolved by the selected adapter|each adapter resolves",
                )
                self.assertRegex(contract, r"external backend may use different locators")

        specification = contracts["specification"]
        for optional_role in ("agents/", "assets/", "references/", "scripts/"):
            self.assertRegex(specification, rf"{re.escape(optional_role)}`?\s+optional")
        self.assertIn("only when the Project Skill has content for that role", specification)

        for name in ("convention", "document"):
            human = (
                ROOT / ".agent-factory/document/specification" / name / "index.html"
            ).read_text(encoding="utf-8")
            self.assertIn("stable identity", human)
            self.assertIn("locator", human)
            self.assertIn("외부 backend", human)

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
        self.assertIn("document/specification/<specification-id>/", document)
        self.assertIn("<plugin-root>/skills/", project_skill)
        self.assertIn("<project-root>/.codex/skills/<category>-<title>/", project_skill)
        self.assertIn(
            "<project-root>/.agent-factory/document/specification/<category>-<title>/",
            project_skill,
        )
        paragraphs = normalized_paragraphs(project_skill)
        self.assertTrue(
            any(
                re.search(
                    r"canonical form <category>-<title>.*category classifies.*title identifies",
                    paragraph,
                )
                for paragraph in paragraphs
            )
        )
        self.assertTrue(
            any(
                re.search(
                    r"complete identity.*exactly matches both resolved representations.*name field.*frontmatter.*current/default local adapter.*project skill.*human specification directory",
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

    def test_testing_convention_keeps_execution_focused_and_verification_independent(self) -> None:
        entry = (ROOT / "skills/convention/SKILL.md").read_text(encoding="utf-8")
        testing = (
            ROOT / "skills/convention/references/testing.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")

        self.assertIn("`references/testing.md`", entry)
        for concept in (
            "smallest relevant focused test set",
            "owning component",
            "affected contract",
            "cross-domain impact",
            "human explicitly requests",
            "full test suite",
            "independent verification role",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, " ".join(testing.casefold().split()))
        for local_detail in ("pytest", "unittest", "tests/"):
            with self.subTest(local_detail=local_detail):
                self.assertNotIn(local_detail, testing.casefold())

        self.assertIn("skills/convention/references/testing.md", human)
        normalized_human = " ".join(human.split())
        for concept in (
            "가장 작은 focused test set",
            "cross-domain 영향을 보일 때",
            "full suite는 Human이 명시적으로 요청",
            "독립적인 Verification role",
        ):
            with self.subTest(human_concept=concept):
                self.assertIn(concept, normalized_human)

    def test_explicit_human_input_rule_is_cross_cutting_and_paired(self) -> None:
        entry = (ROOT / "skills/convention/SKILL.md").read_text(encoding="utf-8")
        rule = (
            ROOT / "skills/convention/references/explicit-human-input.md"
        ).read_text(encoding="utf-8")
        human = CORE_HUMAN.read_text(encoding="utf-8")

        self.assertIn("`references/explicit-human-input.md`", entry)
        normalized_rule = " ".join(rule.casefold().split())
        for concept in (
            "human actually states it",
            "accepted specification resolves it unambiguously",
            "do not infer, invent, silently default",
            "ask the human and wait",
            "silence, ambiguity, convention, precedent, likely preference",
            "cannot manufacture a missing human decision",
            "main asks the human",
            "work and verification report the unresolved question to main",
            "explorer may gather evidence",
            "interview is conducted only by main",
            "creates no agent role, public skill, or capability",
            "does not weaken existing safety, authority, specification-pair, or managed graph",
        ):
            with self.subTest(ai_concept=concept):
                self.assertIn(concept, normalized_rule)

        self.assertIn("skills/convention/references/explicit-human-input.md", human)
        normalized_human = " ".join(human.split())
        for concept in (
            "명시되지 않은 결정은 반드시 묻고 기다립니다",
            "추론, 발명, 묵시적 기본값 적용",
            "침묵, 모호함, 관행, 선례",
            "사실과 선택을 구분",
            "Main만 Human에게 질문하고 답을 기다립니다",
            "Work와 Verification은 미해결 질문을 Main에 보고",
            "Main, Work, Verification, Explorer, Interview 전체에 적용",
            "기존 안전, 권한, Specification pair, managed graph 계약도 약화하지 않습니다",
        ):
            with self.subTest(human_concept=concept):
                self.assertIn(concept, normalized_human)

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
        local_targets = {
            value
            for value in targets
            if value.startswith((".agent-factory/", ".codex-plugin/", "skills/"))
            and "<" not in value
            and not value.startswith(("http://", "https://"))
        }
        self.assertTrue(local_targets)
        runtime_provenance_targets = {
            target
            for target in local_targets
            if target.startswith(".agent-factory/agent/")
        }
        tracked_targets = local_targets - runtime_provenance_targets
        self.assertTrue(
            any(target.endswith("/request.md") for target in runtime_provenance_targets)
        )
        self.assertTrue(tracked_targets)
        for target in sorted(runtime_provenance_targets):
            with self.subTest(runtime_provenance=target):
                self.assertRegex(
                    target,
                    r"^\.agent-factory/agent/[a-z0-9][a-z0-9-]*/runs/"
                    r"run-\d{8}T\d{12}Z-[0-9a-f]{8}/(?:request|result)\.md$",
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
        self.assertIn(decision_request, ai)
        self.assertNotIn("active Human request for the Tool Skill", ai)
        self.assertEqual(
            set(PUBLIC_SKILLS),
            {
                path.name
                for path in (ROOT / ".agent-factory/document/specification").iterdir()
                if path.is_dir()
            },
        )

    def test_human_skip_timing_is_aligned_in_ai_and_human_views(self) -> None:
        agent = (ROOT / "skills/agent/SKILL.md").read_text(encoding="utf-8")
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        diagrams = (
            ROOT / "skills" / "convention" / "references" / "diagrams.md"
        ).read_text(encoding="utf-8")
        human = (
            ROOT / ".agent-factory/document/specification/agent/index.html"
        ).read_text(encoding="utf-8")
        normalized_agent = " ".join(agent.casefold().split())
        normalized_ai_core = " ".join(ai_core.casefold().split())
        for contract in (normalized_agent, normalized_ai_core):
            with self.subTest(contract="skip-semantics"):
                words = contract.replace("-", " ").replace("`", "")
                self.assertIn("authorization reference", words)
                self.assertIn("decision evidence", words)
                self.assertIn("before the next verification starts", words)
                self.assertIn("not a graph transition or completion", words)
                self.assertRegex(words, r"only after the current (?:initial or revision )?work")
                self.assertRegex(words, r"starts no next (?:or additional )?verification")
                self.assertIn("reaches end", words)
        for phrase in (
            "Human-only skip intent",
            "not a transition or completion",
            "evaluated only after current",
            "start no next or additional Verification",
        ):
            self.assertIn(phrase, diagrams)
        for phrase in (
            "Main",
            "Work",
            "Verification",
            "fail → 같은 Work",
            "Verification pass → END",
            "Human skip → END",
            "Human만 authorization reference와 결정 근거를 갖춰",
            "현재 initial 또는 revision Work가 끝난 뒤",
            "다음 Verification이 시작되기 전에만 적용",
            "다음 또는 추가 Verification을 시작하지 않고 END에 도달",
            "non-Human이 기록할 수 없으며",
            "fail closed로 거부",
        ):
            self.assertIn(phrase, human)

    def test_main_decomposition_is_aligned_in_agent_specification_pair(self) -> None:
        agent = (ROOT / "skills/agent/SKILL.md").read_text(encoding="utf-8")
        prompt = (ROOT / "skills/agent/prompt/main.md").read_text(encoding="utf-8")
        human = (
            ROOT / ".agent-factory/document/specification/agent/index.html"
        ).read_text(encoding="utf-8")
        normalized_agent = " ".join(agent.split())
        normalized_prompt = " ".join(prompt.split())
        shared_phrases = (
            "materially separable bounded tasks",
            "overlapping repository paths and writes",
            "Uncertainty about independence defaults to sequencing",
            "multiple independent `Work -> Verification` chains concurrently",
            "distinct Agent IDs, loop IDs, run IDs",
            "dependency order",
            "runtime mechanically guarantees conflict freedom",
        )
        for contract in (normalized_agent, normalized_prompt):
            for phrase in shared_phrases:
                with self.subTest(ai_phrase=phrase):
                    self.assertIn(phrase, contract)
        for phrase in (
            "shared mutable resources",
            "its Verification starts only after its Work result is complete",
            "binds that exact Work run",
        ):
            self.assertIn(phrase, normalized_agent)
        for phrase in (
            "shared mutable resource",
            "start its Verification only after its Work result is complete",
            "bind Verification to that exact Work run",
        ):
            self.assertIn(phrase, normalized_prompt)
        for phrase in (
            "실질적으로 분리 가능한 bounded task",
            "repository path와 write",
            "Git index·worktree",
            "독립성이 불확실하면 순차 실행",
            "독립된 Work → Verification chain을 동시에 실행",
            "각 chain 내부는 반드시 순차적",
            "서로 다른 Agent ID·loop ID·run ID",
            "dependency order로 통합",
            "runtime이 conflict freedom을 기계적으로 보장한다는 뜻이 아닙니다",
            "새 Agent role이나 graph node",
            "병렬성을 최대화하라는 요구도 아닙니다",
        ):
            with self.subTest(human_phrase=phrase):
                self.assertIn(phrase, human)

    def test_workspace_activity_and_explorer_boundaries_are_aligned(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = (
            ROOT / ".agent-factory/document/specification/workspace/index.html"
        ).read_text(encoding="utf-8")
        normalized_ai_core = " ".join(ai_core.split())
        for path in (
            ".agent-factory/document/original/",
            ".agent-factory/document/processed/",
            ".agent-factory/workspace/explorer/",
        ):
            self.assertIn(path, ai_core)
        for phrase in (
            "temporary execution-only material remains in the producing managed Agent run",
            "exactly five top-level Activities in this order: 일정, 에이전트, 문서, 로그, 테스트",
            "원본문서`, `가공문서`, and `스펙문서`",
            "The UI label does not rename Specification",
            "other four Activity sidebars and capabilities remain Human-owned and unresolved",
            "both forms must exist and remain byte-identical",
            "packaged files are the reusable installation source",
        ):
            self.assertIn(phrase, normalized_ai_core)
        unresolved = re.search(
            r"## Unresolved architecture decisions\n(.*?)\n## Representation-alignment checklist",
            ai_core,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(unresolved)
        unresolved_text = " ".join(unresolved.group(1).split())
        for label in ("문서 분류", "출처", "태그", "문서 이름", "확장자", "수정 일자"):
            self.assertIn(label, ai_core)
        for decided_behavior in (
            "global and per-column filtering",
            "link/provider-cell behavior",
            "Human column resizing/reordering",
        ):
            self.assertIn(decided_behavior, unresolved_text)
        self.assertNotIn("table columns and behavior", unresolved_text)
        for genuinely_unresolved in (
            "overview content",
            "live source/query integration",
            "synchronization trigger and status",
            "metadata-mutation authority and persistence",
            "other four Activities' sidebar architecture",
        ):
            self.assertIn(genuinely_unresolved, unresolved_text)
        self.assertRegex(
            normalized_ai_core.casefold(),
            r"internal read-only .*file/project metadata projection and .*skill-navigation projection "
            r"(?:define neither|do not define) a top-level activity "
            r"(?:nor nesting|or authorize nesting) under one of the five",
        )
        for phrase in (
            "정확히 다섯 Activity",
            "원본문서",
            "가공문서",
            "스펙문서",
            "Agent-owned db.sqlite",
            "논리 type은 Specification",
        ):
            self.assertIn(phrase, human)
        self.assertNotIn("<td>로드맵</td>", human)
        self.assertNotIn("여섯 영역", human)

    def test_catalog_ownership_is_synchronized_across_specification_pairs(self) -> None:
        agent = (
            ROOT / ".agent-factory/document/specification/agent/index.html"
        ).read_text(encoding="utf-8")
        convention = (
            ROOT / ".agent-factory/document/specification/convention/index.html"
        ).read_text(encoding="utf-8")
        document = (
            ROOT / ".agent-factory/document/specification/document/index.html"
        ).read_text(encoding="utf-8")
        workspace = (
            ROOT / ".agent-factory/document/specification/workspace/index.html"
        ).read_text(encoding="utf-8")
        for phrase in (
            "skills/agent/scripts/catalog.py",
            "skills/agent/assets/schema/catalog.sql",
            "schema version 3",
            "last-good recovery",
        ):
            self.assertIn(phrase, agent)
        self.assertIn("Agent 구현 소유", convention)
        self.assertIn("Agent가 구현을 소유하는 rebuildable·non-authoritative projection", document)
        for phrase in (
            "카탈로그의 schema와 manager",
            "Workspace의 <code>serve.py init</code>은 카탈로그를 만들지 않으며",
            "현재 catalog/search UI나 source/query binding은 구현되지 않았습니다",
        ):
            self.assertIn(phrase, workspace)
        self.assertNotIn("skills/workspace/scripts/catalog.py", workspace)
        self.assertNotIn("skills/workspace/assets/schema/catalog.sql", workspace)

    def test_tool_and_gather_boundaries_are_aligned_in_both_views(self) -> None:
        ai_core = (
            ROOT / "skills" / "convention" / "references" / "agent-factory-core.md"
        ).read_text(encoding="utf-8")
        human = "\n".join(
            (
                ROOT / ".agent-factory/document/specification" / name / "index.html"
            ).read_text(encoding="utf-8")
            for name in ("convention", "gather", "tool")
        )
        normalized_ai_core = " ".join(ai_core.split())
        for phrase in (
            "exactly six public distributed Skills",
            "Tool never escalates scope automatically",
            "creates no `.agent-factory/tool/` root or Workspace Activity",
            "Google Drive and OneDrive provider scripts retain their",
        ):
            self.assertIn(phrase, normalized_ai_core)
        for phrase in ("여섯 public Skill", "최소 read-only permission", "credential 자체를 저장하지 않고"):
            self.assertIn(phrase, human)

    def test_core_human_connectors_use_accessible_svg_or_visible_prose(self) -> None:
        for name in ("agent", "document", "gather", "workspace"):
            human = (
                ROOT / ".agent-factory/document/specification" / name / "index.html"
            ).read_text(encoding="utf-8")
            parser = TemplateParser()
            parser.feed(human)
            svgs = [attrs for tag, attrs in parser.tags if tag == "svg"]
            self.assertTrue(svgs)
            for attrs in svgs:
                self.assertEqual(attrs.get("aria-hidden"), "true")


if __name__ == "__main__":
    unittest.main()
