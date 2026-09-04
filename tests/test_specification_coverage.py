from __future__ import annotations

import hashlib
import html
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "skills" / "document" / "scripts" / "verify_specification_pair.py"
SPEC = importlib.util.spec_from_file_location("specification_coverage", VERIFIER_PATH)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class SpecificationCoverageTests(unittest.TestCase):
    @staticmethod
    def _sha256(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    def _project(self, root: Path) -> list[Path]:
        skill = root / "skills" / "demo"
        (skill / "references").mkdir(parents=True)
        (skill / "agents").mkdir()
        (skill / "SKILL.md").write_text("# Demo\n\nKeep every rule.\n", encoding="utf-8")
        (skill / "references" / "detail.md").write_text(
            "# Detail\n\nPreserve the exception.\n", encoding="utf-8"
        )
        (skill / "agents" / "openai.yaml").write_text(
            'interface:\n  display_name: "Demo"\n', encoding="utf-8"
        )
        return VERIFIER.instruction_sources(skill)

    def _human(self, root: Path, sources: list[Path]) -> Path:
        parts = ["<!doctype html><html lang=\"ko\"><body>"]
        for source in sources:
            data = source.read_bytes()
            line_count = len(data.decode("utf-8").splitlines(keepends=True))
            relative = source.relative_to(root).as_posix()
            parts.append(
                f'<article data-ai-source="{html.escape(relative)}" '
                f'data-ai-sha256="{self._sha256(data)}">'
                f'<section data-source-lines="1-{line_count}" '
                f'data-source-sha256="{self._sha256(data)}">'
                f"{html.escape('전체 내용을 옮긴 한국어 번역입니다.')}</section></article>"
            )
        parts.append("</body></html>")
        entry = (
            root
            / ".agent-factory"
            / "document"
            / "specification"
            / "demo"
            / "index.html"
        )
        entry.parent.mkdir(parents=True)
        entry.write_text("".join(parts), encoding="utf-8")
        return entry

    def test_complete_current_ordered_source_coverage_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = self._project(root)
            self._human(root, sources)
            self.assertEqual(
                [source.relative_to(root).as_posix() for source in sources],
                VERIFIER.verify_pair(root, "demo"),
            )

    def test_all_repository_specification_pairs_pass(self) -> None:
        for specification_id in (
            "agent",
            "convention",
            "document",
            "gather",
            "tool",
            "workspace",
        ):
            with self.subTest(specification_id=specification_id):
                self.assertTrue(VERIFIER.verify_pair(ROOT, specification_id))

    def test_missing_instruction_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = self._project(root)
            self._human(root, sources[:-1])
            with self.assertRaisesRegex(VERIFIER.VerificationError, "missing sources"):
                VERIFIER.verify_pair(root, "demo")

    def test_stale_source_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = self._project(root)
            self._human(root, sources)
            sources[0].write_text("# Demo\n\nChanged rule.\n", encoding="utf-8")
            with self.assertRaisesRegex(VERIFIER.VerificationError, "stale source hash"):
                VERIFIER.verify_pair(root, "demo")

    def test_reordered_instruction_sources_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = self._project(root)
            self._human(root, list(reversed(sources)))
            with self.assertRaisesRegex(VERIFIER.VerificationError, "not in AI source order"):
                VERIFIER.verify_pair(root, "demo")

    def test_non_contiguous_source_range_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = self._project(root)
            human = self._human(root, sources)
            line_count = len(sources[0].read_text(encoding="utf-8").splitlines(keepends=True))
            content = human.read_text(encoding="utf-8").replace(
                f'data-source-lines="1-{line_count}"',
                f'data-source-lines="2-{line_count}"',
                1,
            )
            human.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(VERIFIER.VerificationError, "non-contiguous source range"):
                VERIFIER.verify_pair(root, "demo")

    def test_empty_translation_block_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = self._project(root)
            human = self._human(root, sources)
            content = human.read_text(encoding="utf-8").replace(
                "전체 내용을 옮긴 한국어 번역입니다.", "", 1
            )
            human.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(VERIFIER.VerificationError, "translated block is empty"):
                VERIFIER.verify_pair(root, "demo")


if __name__ == "__main__":
    unittest.main()
