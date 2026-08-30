from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = ROOT / "skills" / "agent" / "scripts" / "catalog.py"
SPEC = importlib.util.spec_from_file_location("agent_catalog", MANAGER_PATH)
assert SPEC is not None and SPEC.loader is not None
CATALOG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CATALOG)


class AgentCatalogManagerTests(unittest.TestCase):
    def _project(self, root: Path) -> None:
        (root / ".agent-factory" / "agent").mkdir(parents=True)
        (root / ".agent-factory" / "document" / "original").mkdir(parents=True)
        (root / ".agent-factory" / "document" / "processed").mkdir(parents=True)
        (root / ".agent-factory" / "document" / "specification").mkdir(parents=True)

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def _old_catalog(root: Path, version: str | None) -> Path:
        database = root / ".agent-factory" / "db.sqlite"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            if version is not None:
                connection.execute(
                    "INSERT INTO schema_metadata VALUES ('schema_version', ?)",
                    (version,),
                )
            connection.execute(
                "CREATE TABLE stale_rows (value TEXT NOT NULL)"
            )
            connection.execute("INSERT INTO stale_rows VALUES ('must-not-be-migrated')")
            connection.commit()
        finally:
            connection.close()
        return database

    def test_initialization_is_idempotent_and_status_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            path, result = CATALOG.initialize_catalog(root)
            self.assertEqual("created", result["outcome"])
            self.assertTrue(result["created"])
            self.assertFalse(result["migrated"])
            self.assertIsNone(result["sourceSchemaVersion"])
            self.assertEqual("3", result["targetSchemaVersion"])
            before = path.read_bytes()
            same_path, result = CATALOG.initialize_catalog(root)
            self.assertEqual("unchanged", result["outcome"])
            self.assertFalse(result["created"])
            self.assertFalse(result["migrated"])
            self.assertEqual("3", result["sourceSchemaVersion"])
            self.assertEqual("3", result["targetSchemaVersion"])
            self.assertEqual(path, same_path)
            status = CATALOG.catalog_status(root)
            self.assertEqual("ok", status["integrity"])
            self.assertEqual("3", status["schemaVersion"])
            self.assertEqual(before, path.read_bytes())
            self.assertEqual([], status["sidecars"])
            self.assertTrue(status["search"]["available"])
            self.assertEqual(0, status["search"]["agentEntities"])
            self.assertEqual({}, status["search"]["agentEntityKinds"])
            self.assertEqual({}, status["search"]["documentIndexStates"])

    def test_init_rebuild_migrates_supported_v1_and_v2_from_authoritative_files(self) -> None:
        for version in ("1", "2"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                self._project(root)
                document = (
                    root / ".agent-factory" / "document" / "processed" / "migration" / "notes.md"
                )
                document.parent.mkdir()
                document.write_text(f"authoritative version {version}", encoding="utf-8")
                database = self._old_catalog(root, version)

                path, result = CATALOG.initialize_catalog(root)

                self.assertEqual(database, path)
                self.assertEqual("migrated", result["outcome"])
                self.assertFalse(result["created"])
                self.assertTrue(result["migrated"])
                self.assertEqual(version, result["sourceSchemaVersion"])
                self.assertEqual("3", result["targetSchemaVersion"])
                self.assertEqual(1, result["counts"]["documents"])
                status = CATALOG.catalog_status(root)
                self.assertEqual("3", status["schemaVersion"])
                self.assertEqual("ok", status["integrity"])
                connection = sqlite3.connect(database)
                try:
                    self.assertIsNone(
                        connection.execute(
                            "SELECT 1 FROM sqlite_schema WHERE name = 'stale_rows'"
                        ).fetchone()
                    )
                    self.assertEqual(
                        [("processed", ".agent-factory/document/processed/migration")],
                        connection.execute(
                            "SELECT document_type, source_path FROM documents"
                        ).fetchall(),
                    )
                    self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
                finally:
                    connection.close()

    def test_init_rejects_missing_unparseable_unsupported_and_future_versions(self) -> None:
        for version, error in (
            (None, "missing or ambiguous"),
            ("banana", "unparseable"),
            ("0", "unparseable"),
            ("01", "unparseable"),
            (" 1", "unparseable"),
            ("4", "future"),
        ):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                self._project(root)
                database = self._old_catalog(root, version)
                before = database.read_bytes()

                with self.assertRaisesRegex(CATALOG.CatalogError, error):
                    CATALOG.initialize_catalog(root)

                self.assertEqual(before, database.read_bytes())

    def test_init_cli_rejects_oversized_numeric_version_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            self._project(root)
            database = self._old_catalog(root, "9" * 5000)
            before = database.read_bytes()

            completed = subprocess.run(
                [
                    "python3",
                    str(MANAGER_PATH),
                    "--project-root",
                    str(root),
                    "init",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(2, completed.returncode)
            self.assertIn("schema version is unparseable", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertEqual("", completed.stdout)
            self.assertEqual(before, database.read_bytes())

    def test_init_migration_failure_preserves_prior_database_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            database = self._old_catalog(root, "2")
            before = database.read_bytes()
            misplaced = root / ".agent-factory" / "document" / "processed" / "notes.md"
            misplaced.write_text("invalid flat file", encoding="utf-8")

            with self.assertRaisesRegex(CATALOG.CatalogError, "package directories"):
                CATALOG.initialize_catalog(root)

            self.assertEqual(before, database.read_bytes())

    def test_init_cli_reports_migration_versions_and_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            self._project(root)
            self._old_catalog(root, "1")

            completed = subprocess.run(
                [
                    "python3",
                    str(MANAGER_PATH),
                    "--project-root",
                    str(root),
                    "init",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual("init", payload["operation"])
            self.assertEqual("migrated", payload["outcome"])
            self.assertFalse(payload["created"])
            self.assertTrue(payload["migrated"])
            self.assertEqual("1", payload["sourceSchemaVersion"])
            self.assertEqual("3", payload["targetSchemaVersion"])

    def test_rebuild_populates_authoritative_metadata_without_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            agent = root / ".agent-factory" / "agent" / "work-a"
            self._write_json(agent / "session.json", {
                "agentId": "work-a", "sessionId": "session-a", "role": "work",
                "createdAt": "2026-08-30T00:00:00Z", "updatedAt": "2026-08-30T00:01:00Z",
            })
            self._write_json(agent / "runs" / "run-a" / "state.json", {
                "agentId": "work-a", "sessionId": "session-a", "runId": "run-a",
                "role": "work", "status": "completed", "requestHash": "a" * 64,
            })
            original = root / ".agent-factory" / "document" / "original" / "source" / "source.txt"
            original.parent.mkdir()
            original.write_text("body that must not be stored", encoding="utf-8")
            processed = root / ".agent-factory" / "document" / "processed" / "notes" / "notes.md"
            processed.parent.mkdir()
            processed.write_text("derived body", encoding="utf-8")

            database, counts = CATALOG.rebuild_catalog(root)
            self.assertEqual(1, counts["agents"])
            self.assertEqual(1, counts["runs"])
            self.assertEqual(2, counts["documents"])
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [("run-a", "completed", "a" * 64)],
                    connection.execute("SELECT run_id, status, request_hash FROM runs").fetchall(),
                )
                serialized = " ".join(
                    str(value)
                    for table in ("documents", "document_representations")
                    for row in connection.execute(f"SELECT * FROM {table}")
                    for value in row
                )
                self.assertNotIn("body that must not be stored", serialized)
                self.assertNotIn("derived body", serialized)
            finally:
                connection.close()

    def test_rebuild_replaces_stale_rows_and_keeps_deterministic_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            document = root / ".agent-factory" / "document" / "processed" / "one" / "notes.md"
            document.parent.mkdir()
            document.write_text("one", encoding="utf-8")
            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            first_id = connection.execute("SELECT document_id FROM documents").fetchone()[0]
            connection.close()

            document.unlink()
            document.parent.rmdir()
            replacement = root / ".agent-factory" / "document" / "processed" / "two" / "notes.md"
            replacement.parent.mkdir()
            replacement.write_text("two", encoding="utf-8")
            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                rows = connection.execute("SELECT document_id, source_path FROM documents").fetchall()
            finally:
                connection.close()
            self.assertEqual(1, len(rows))
            self.assertNotEqual(first_id, rows[0][0])
            self.assertTrue(rows[0][1].endswith("/two"))

            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(rows, connection.execute("SELECT document_id, source_path FROM documents").fetchall())
            finally:
                connection.close()

    def test_agent_and_document_search_are_bounded_deterministic_and_unicode_aware(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            for name in ("work-b", "work-a"):
                agent = root / ".agent-factory" / "agent" / name
                self._write_json(agent / "session.json", {
                    "agentId": name, "sessionId": f"session-{name}",
                    "role": "work", "status": "ready",
                })
                self._write_json(agent / "runs" / f"run-{name}" / "state.json", {
                    "runId": f"run-{name}", "sessionId": f"session-{name}",
                    "role": "work", "status": "completed",
                    "finishedAt": "2026-08-30T16:15:00Z",
                })
            korean = root / ".agent-factory" / "document" / "processed" / "검색" / "notes.md"
            korean.parent.mkdir()
            korean.write_text("에이전트 카탈로그 한국어 검색 문서", encoding="utf-8")
            CATALOG.rebuild_catalog(root)

            agent_results = CATALOG.search_agents(root, "completed", limit=1)
            self.assertEqual(1, len(agent_results))
            self.assertEqual("run", agent_results[0]["entity_kind"])
            self.assertEqual("run-work-a", agent_results[0]["entity_id"])
            timestamp_results = CATALOG.search_agents(root, "2026-08-30T16")
            self.assertEqual(2, len(timestamp_results))
            self.assertTrue(all(result["timestamp"] == "2026-08-30T16:15:00Z" for result in timestamp_results))
            document_results = CATALOG.search_documents(root, "한국어")
            self.assertEqual(1, len(document_results))
            self.assertEqual("processed", document_results[0]["document_type"])
            self.assertTrue(document_results[0]["source_path"].endswith("검색/notes.md"))
            self.assertEqual([], CATALOG.search_documents(root, "존재하지않음"))

    def test_literal_query_escapes_fts_syntax_and_rejects_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            with self.assertRaisesRegex(CATALOG.CatalogError, "catalog is missing"):
                CATALOG.search_agents(root, "work")
            CATALOG.initialize_catalog(root)
            with self.assertRaisesRegex(CATALOG.CatalogError, "must not be empty"):
                CATALOG.search_agents(root, "   ")
            with self.assertRaisesRegex(CATALOG.CatalogError, "between 1"):
                CATALOG.search_documents(root, "text", 0)
            with self.assertRaisesRegex(CATALOG.CatalogError, "must not contain NUL"):
                CATALOG.search_agents(root, "bad\x00query")
            with self.assertRaisesRegex(CATALOG.CatalogError, "must not exceed"):
                CATALOG.search_agents(root, "a" * (CATALOG.MAX_SEARCH_QUERY_BYTES + 1))

    def test_literal_query_supports_hyphens_spaces_punctuation_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            agent = root / ".agent-factory" / "agent" / "catalog-search-verification"
            self._write_json(agent / "session.json", {
                "agentId": "catalog-search-verification",
                "sessionId": "session-catalog-search-verification",
                "role": "verification",
                "status": "ready",
            })
            document = root / ".agent-factory" / "document" / "processed" / "literal" / "notes.md"
            document.parent.mkdir()
            document.write_text('한국어 검색과 say "hello" 문구', encoding="utf-8")
            CATALOG.rebuild_catalog(root)

            hyphenated = CATALOG.search_agents(root, "catalog-search-verification")
            self.assertTrue(any(row["agent_id"] == "catalog-search-verification" for row in hyphenated))
            self.assertEqual(1, len(CATALOG.search_documents(root, "한국어 검색")))
            self.assertEqual(1, len(CATALOG.search_documents(root, 'say "hello"')))
            self.assertEqual([], CATALOG.search_documents(root, "---"))
            self.assertEqual([], CATALOG.search_agents(root, '"unterminated'))

    def test_literal_query_builder_never_exposes_raw_match_syntax(self) -> None:
        self.assertEqual('"catalog-search-verification"*', CATALOG._literal_fts_query("catalog-search-verification"))
        self.assertEqual('"한국어 검색"*', CATALOG._literal_fts_query(" 한국어 검색 "))
        self.assertEqual('"say ""hello"""*', CATALOG._literal_fts_query('say "hello"'))
        self.assertEqual('"alpha OR beta"*', CATALOG._literal_fts_query("alpha OR beta"))

    def test_search_cli_emits_json_without_mutating_the_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            self._project(root)
            document = root / ".agent-factory" / "document" / "processed" / "cli" / "notes.md"
            document.parent.mkdir()
            document.write_text("commandline token", encoding="utf-8")
            database, _ = CATALOG.rebuild_catalog(root)
            before = database.read_bytes()
            completed = subprocess.run(
                [
                    "python3", str(MANAGER_PATH), "--project-root", str(root),
                    "search-documents", "commandline", "--limit", "1",
                ],
                check=True, capture_output=True, text=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual("search-documents", payload["operation"])
            self.assertEqual(1, len(payload["results"]))
            self.assertEqual(before, database.read_bytes())

    def test_document_search_excludes_binary_and_reports_truncation_and_total_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            original = root / ".agent-factory" / "document" / "original" / "search-fixtures"
            original.mkdir()
            (original / "binary.txt").write_bytes(b"secret\0binary")
            (original / "large.txt").write_text("needle " * 100, encoding="utf-8")
            (original / "later.txt").write_text("later needle", encoding="utf-8")
            with mock.patch.object(CATALOG, "MAX_SEARCH_TEXT_BYTES", 32), mock.patch.object(CATALOG, "MAX_SEARCH_TOTAL_BYTES", 32):
                database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                states = dict(connection.execute(
                    "SELECT source_path, index_status FROM document_search_entries"
                ).fetchall())
            finally:
                connection.close()
            self.assertEqual("excluded-binary", states[next(path for path in states if path.endswith("binary.txt"))])
            self.assertEqual("truncated", states[next(path for path in states if path.endswith("large.txt"))])
            self.assertEqual("excluded-total-limit", states[next(path for path in states if path.endswith("later.txt"))])
            needle_paths = [result["source_path"] for result in CATALOG.search_documents(root, "needle")]
            self.assertFalse(any(path.endswith("later.txt") for path in needle_paths))
            self.assertEqual(1, len(CATALOG.search_documents(root, "binary")))

    def test_rebuild_refreshes_search_and_removes_stale_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            document = root / ".agent-factory" / "document" / "processed" / "refresh" / "notes.md"
            document.parent.mkdir()
            document.write_text("oldterm", encoding="utf-8")
            CATALOG.rebuild_catalog(root)
            status = CATALOG.catalog_status(root)
            self.assertEqual({"indexed": 1}, status["search"]["documentIndexStates"])
            self.assertEqual(1, len(CATALOG.search_documents(root, "oldterm")))
            document.write_text("newterm", encoding="utf-8")
            CATALOG.rebuild_catalog(root)
            self.assertEqual([], CATALOG.search_documents(root, "oldterm"))
            self.assertEqual(1, len(CATALOG.search_documents(root, "newterm")))

    def test_rebuild_discovers_flattened_specification_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            specification = (
                root
                / ".agent-factory"
                / "document"
                / "specification"
                / "project-core"
            )
            specification.mkdir()
            (specification / "index.html").write_text("<main>spec</main>", encoding="utf-8")

            database, counts = CATALOG.rebuild_catalog(root)
            self.assertEqual(1, counts["documents"])
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [
                        (
                            "specification-project-core",
                            "specification",
                            ".agent-factory/document/specification/project-core",
                        )
                    ],
                    connection.execute(
                        "SELECT document_id, document_type, source_path FROM documents"
                    ).fetchall(),
                )
                self.assertEqual(
                    [
                        (
                            "human-html",
                            ".agent-factory/document/specification/project-core/index.html",
                        )
                    ],
                    connection.execute(
                        "SELECT representation_kind, source_path "
                        "FROM document_representations"
                    ).fetchall(),
                )
            finally:
                connection.close()

    def test_rebuild_requires_reciprocal_specification_binding_without_name_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            specification = root / ".agent-factory/document/specification/arbitrary-name"
            specification.mkdir()
            human_entry = ".agent-factory/document/specification/arbitrary-name/index.html"
            (specification / "index.html").write_text(
                """<!doctype html><html><head>
<meta name="agent-factory:specification-id" content="arbitrary-name">
<meta name="agent-factory:ai-root" content="skills/">
<meta name="agent-factory:ai-binding-entry" content="skills/binding/SKILL.md">
</head><body>사람 중심 문서</body></html>""",
                encoding="utf-8",
            )
            skill = root / "skills/binding/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                """---
name: binding
description: test binding
metadata:
  specification-id: arbitrary-name
  human-entry: .agent-factory/document/specification/arbitrary-name/index.html
  ai-root: skills/
---
# Binding
""",
                encoding="utf-8",
            )

            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [("unknown", "semantic-alignment-unverified", human_entry)],
                    connection.execute(
                        "SELECT pair_status, error_code, evidence_path "
                        "FROM specification_pair_status"
                    ).fetchall(),
                )
                self.assertEqual(
                    [("ai-skill", "skills/binding/SKILL.md")],
                    connection.execute(
                        "SELECT representation_kind, source_path "
                        "FROM document_representations WHERE representation_kind = 'ai-skill'"
                    ).fetchall(),
                )
            finally:
                connection.close()

            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "human-entry: .agent-factory/document/specification/arbitrary-name/index.html",
                    "human-entry: .agent-factory/document/specification/other/index.html",
                ),
                encoding="utf-8",
            )
            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [("misaligned", "reciprocal-binding-mismatch")],
                    connection.execute(
                        "SELECT pair_status, error_code FROM specification_pair_status"
                    ).fetchall(),
                )
            finally:
                connection.close()

    def test_rebuild_reports_skill_with_declared_missing_human_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            skill = root / "skills/solo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                """---
name: solo
description: test missing Human pair
metadata:
  specification-id: solo
  human-entry: .agent-factory/document/specification/solo/index.html
  ai-root: skills/solo/
---
# Solo
""",
                encoding="utf-8",
            )

            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [("solo", "missing-human", "missing-human-entry")],
                    connection.execute(
                        "SELECT d.title, p.pair_status, p.error_code "
                        "FROM specification_pair_status p "
                        "JOIN documents d USING(document_id)"
                    ).fetchall(),
                )
                self.assertEqual(
                    [("ai-skill", "skills/solo/SKILL.md")],
                    connection.execute(
                        "SELECT representation_kind, source_path "
                        "FROM document_representations"
                    ).fetchall(),
                )
            finally:
                connection.close()

    def test_malformed_and_legacy_sources_remain_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            agent = root / ".agent-factory" / "agent" / "legacy-agent"
            agent.mkdir()
            (agent / "session.json").write_text("{not-json", encoding="utf-8")
            run = agent / "runs" / "run-legacy"
            run.mkdir(parents=True)
            (run / "state.json").write_text("[]", encoding="utf-8")
            legacy = root / ".agent-factory" / "document" / "processed" / "legacy-inquery-sample" / "report.md"
            legacy.parent.mkdir()
            legacy.write_text("legacy", encoding="utf-8")

            database, _ = CATALOG.rebuild_catalog(root)
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [("unknown", "malformed-json")],
                    connection.execute("SELECT status, error_code FROM runs").fetchall(),
                )
                self.assertEqual(
                    ("processed", "legacy-historical"),
                    connection.execute(
                        "SELECT document_type, status FROM documents"
                    ).fetchone(),
                )
            finally:
                connection.close()

    def test_one_document_per_package_with_recursive_representations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            package = (
                root
                / ".agent-factory"
                / "document"
                / "processed"
                / "legacy-inquery-research"
            )
            (package / "source-cache").mkdir(parents=True)
            (package / "report.md").write_text("historical report", encoding="utf-8")
            (package / "source-cache" / "source.txt").write_text(
                "historical source", encoding="utf-8"
            )

            database, counts = CATALOG.rebuild_catalog(root)
            self.assertEqual(1, counts["documents"])
            self.assertEqual(2, counts["document_representations"])
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    [
                        (
                            "processed-legacy-inquery-research",
                            "processed",
                            "legacy-historical",
                            ".agent-factory/document/processed/legacy-inquery-research",
                        )
                    ],
                    connection.execute(
                        "SELECT document_id, document_type, status, source_path "
                        "FROM documents"
                    ).fetchall(),
                )
                self.assertEqual(
                    [
                        ".agent-factory/document/processed/legacy-inquery-research/report.md",
                        ".agent-factory/document/processed/legacy-inquery-research/source-cache/source.txt",
                    ],
                    [
                        row[0]
                        for row in connection.execute(
                            "SELECT source_path FROM document_representations "
                            "ORDER BY source_path"
                        )
                    ],
                )
            finally:
                connection.close()

    def test_type_root_files_fail_closed_instead_of_becoming_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            misplaced = root / ".agent-factory" / "document" / "processed" / "notes.md"
            misplaced.write_text("not a package", encoding="utf-8")
            with self.assertRaisesRegex(CATALOG.CatalogError, "package directories"):
                CATALOG.rebuild_catalog(root)

    def test_bounded_scans_and_symlink_roots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            for name in ("a", "b"):
                (root / ".agent-factory" / "agent" / name).mkdir()
            with mock.patch.object(CATALOG, "MAX_AGENTS", 1):
                with self.assertRaises(CATALOG.CatalogError):
                    CATALOG.rebuild_catalog(root)

        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory)
            (root / ".agent-factory").mkdir()
            os.symlink(outside_directory, root / ".agent-factory" / "agent")
            (root / ".agent-factory" / "document").mkdir()
            with self.assertRaises(CATALOG.CatalogError):
                CATALOG.rebuild_catalog(root)

    def test_nested_document_file_and_directory_symlinks_preserve_last_good_catalog(self) -> None:
        for source_kind in ("file", "directory"):
            with self.subTest(source_kind=source_kind), tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
                root = Path(temporary_directory)
                outside = Path(outside_directory)
                self._project(root)
                database, _ = CATALOG.rebuild_catalog(root)
                before = database.read_bytes()
                if source_kind == "file":
                    target = outside / "outside.txt"
                    target.write_text("outside", encoding="utf-8")
                    link = root / ".agent-factory" / "document" / "original" / "linked-file"
                else:
                    target = outside / "outside-directory"
                    target.mkdir()
                    link = root / ".agent-factory" / "document" / "original" / "linked-directory"
                os.symlink(target, link)

                with self.assertRaisesRegex(CATALOG.CatalogError, "must not be a symbolic link"):
                    CATALOG.rebuild_catalog(root)
                self.assertEqual(before, database.read_bytes())

    def test_nested_agent_file_and_directory_symlinks_preserve_last_good_catalog(self) -> None:
        for source_kind in ("file", "directory"):
            with self.subTest(source_kind=source_kind), tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
                root = Path(temporary_directory)
                outside = Path(outside_directory)
                self._project(root)
                database, _ = CATALOG.rebuild_catalog(root)
                before = database.read_bytes()
                agent = root / ".agent-factory" / "agent" / "unsafe-agent"
                agent.mkdir()
                if source_kind == "file":
                    target = outside / "session.json"
                    target.write_text("{}", encoding="utf-8")
                    link = agent / "session.json"
                else:
                    (agent / "runs").mkdir()
                    target = outside / "outside-run"
                    target.mkdir()
                    link = agent / "runs" / "linked-run"
                os.symlink(target, link)

                with self.assertRaisesRegex(CATALOG.CatalogError, "must not be a symbolic link"):
                    CATALOG.rebuild_catalog(root)
                self.assertEqual(before, database.read_bytes())

    def test_atomic_failure_preserves_last_good_catalog_and_sidecars_block_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._project(root)
            document = root / ".agent-factory" / "document" / "processed" / "atomic" / "notes.md"
            document.parent.mkdir()
            document.write_text("oldterm", encoding="utf-8")
            database, _ = CATALOG.rebuild_catalog(root)
            before = database.read_bytes()
            document.write_text("newterm", encoding="utf-8")
            with mock.patch.object(CATALOG.os, "replace", side_effect=OSError("publish failed")):
                with self.assertRaises(CATALOG.CatalogError):
                    CATALOG.rebuild_catalog(root)
            self.assertEqual(before, database.read_bytes())

            with mock.patch.object(
                CATALOG,
                "_fsync_directory",
                side_effect=(None, OSError("directory fsync failed"), None),
            ):
                with self.assertRaisesRegex(CATALOG.CatalogError, "directory fsync failed"):
                    CATALOG.rebuild_catalog(root)
            self.assertEqual(before, database.read_bytes())
            self.assertEqual(1, len(CATALOG.search_documents(root, "oldterm")))
            self.assertEqual([], CATALOG.search_documents(root, "newterm"))

            sidecar = Path(f"{database}-wal")
            sidecar.write_bytes(b"active")
            with self.assertRaisesRegex(CATALOG.CatalogError, "sidecars present"):
                CATALOG.rebuild_catalog(root)
            self.assertEqual(before, database.read_bytes())

    def test_catalog_target_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(temporary_directory)
            self._project(root)
            outside = Path(outside_directory) / "outside.sqlite"
            outside.write_bytes(b"do not replace")
            os.symlink(outside, root / ".agent-factory" / "db.sqlite")
            with self.assertRaises(CATALOG.CatalogError):
                CATALOG.rebuild_catalog(root)
            self.assertEqual(b"do not replace", outside.read_bytes())


if __name__ == "__main__":
    unittest.main()
