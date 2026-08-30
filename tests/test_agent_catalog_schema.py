from __future__ import annotations

import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "skills" / "agent" / "assets" / "schema" / "catalog.sql"


class AgentCatalogSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ddl = SCHEMA_PATH.read_text(encoding="utf-8")
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(self.ddl)

    def tearDown(self) -> None:
        self.connection.close()

    def test_schema_creates_normalized_catalog_foundations(self) -> None:
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {
                "schema_metadata",
                "schema_migrations",
                "agents",
                "agent_sessions",
                "runs",
                "turns",
                "work_verification_loops",
                "loop_runs",
                "run_relationships",
                "dispatches",
                "document_types",
                "documents",
                "representation_kinds",
                "document_representations",
                "document_relationship_kinds",
                "document_relationships",
                "agent_document_relationships",
                "specification_pair_status",
                "agent_search_entities",
                "agent_search_fts",
                "document_search_entries",
                "document_search_fts",
            }
            <= tables
        )
        self.assertEqual(
            "3",
            self.connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()[0],
        )
        self.assertIn(
            "timestamp",
            {
                row[1]
                for row in self.connection.execute(
                    "PRAGMA table_info(agent_search_fts)"
                )
            },
        )

    def test_initialization_is_idempotent(self) -> None:
        self.connection.executescript(self.ddl)
        self.assertEqual(
            1,
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations WHERE version = 1"
            ).fetchone()[0],
        )
        self.assertEqual(
            1,
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations WHERE version = 2"
            ).fetchone()[0],
        )
        self.assertEqual(
            1,
            self.connection.execute(
                "SELECT count(*) FROM schema_migrations WHERE version = 3"
            ).fetchone()[0],
        )
        self.assertEqual(
            3,
            self.connection.execute("SELECT count(*) FROM document_types").fetchone()[0],
        )

    def test_foreign_keys_and_core_constraints_are_enforced(self) -> None:
        self.assertEqual(
            1, self.connection.execute("PRAGMA foreign_keys").fetchone()[0]
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO runs (run_id, agent_id, source_path) VALUES (?, ?, ?)",
                ("run-1", "missing-agent", ".agent-factory/agent/a/runs/run-1/state.json"),
            )

        self.connection.execute(
            "INSERT INTO agents (agent_id, source_path) VALUES (?, ?)",
            ("work-agent", ".agent-factory/agent/work-agent/session.json"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO runs (run_id, agent_id, request_hash, source_path) "
                "VALUES (?, ?, ?, ?)",
                (
                    "run-2",
                    "work-agent",
                    "not-a-sha256",
                    ".agent-factory/agent/work-agent/runs/run-2/state.json",
                ),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO documents (document_id, document_type, source_path) "
                "VALUES (?, ?, ?)",
                ("doc-1", "invented-type", "document/original/doc-1"),
            )

    def test_agent_ownership_is_consistent_across_sessions_runs_and_documents(self) -> None:
        self.connection.executemany(
            "INSERT INTO agents (agent_id, source_path) VALUES (?, ?)",
            (
                ("agent-a", ".agent-factory/agent/agent-a/session.json"),
                ("agent-b", ".agent-factory/agent/agent-b/session.json"),
            ),
        )
        self.connection.execute(
            "INSERT INTO agent_sessions (session_id, agent_id, source_path) VALUES (?, ?, ?)",
            ("session-a", "agent-a", ".agent-factory/agent/agent-a/session.json"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO runs (run_id, agent_id, session_id, source_path) "
                "VALUES (?, ?, ?, ?)",
                (
                    "run-mismatched-session",
                    "agent-b",
                    "session-a",
                    ".agent-factory/agent/agent-b/runs/run-mismatched-session/state.json",
                ),
            )

        self.connection.execute(
            "INSERT INTO runs (run_id, agent_id, source_path) VALUES (?, ?, ?)",
            ("run-b", "agent-b", ".agent-factory/agent/agent-b/runs/run-b/state.json"),
        )
        self.connection.execute(
            "INSERT INTO documents (document_id, document_type, source_path) "
            "VALUES (?, ?, ?)",
            ("doc-a", "original", ".agent-factory/document/original/doc-a"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO agent_document_relationships "
                "(relationship_id, agent_id, document_id, run_id) VALUES (?, ?, ?, ?)",
                ("relationship-mismatch", "agent-a", "doc-a", "run-b"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO work_verification_loops "
                "(loop_id, work_agent_id, verification_agent_id, latest_work_run_id, source_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "loop-mismatched-work-run",
                    "agent-a",
                    "agent-b",
                    "run-b",
                    ".agent-factory/agent/agent-a/loops/loop-mismatched-work-run/state.json",
                ),
            )

    def test_legacy_is_status_on_processed_not_a_document_type(self) -> None:
        self.connection.execute(
            "INSERT INTO documents "
            "(document_id, document_type, status, source_path) VALUES (?, ?, ?, ?)",
            (
                "processed-legacy-inquery-item",
                "processed",
                "legacy-historical",
                "document/processed/legacy-inquery-item",
            ),
        )
        self.assertEqual(
            [("processed", "legacy-historical")],
            self.connection.execute(
                "SELECT document_type, status FROM documents"
            ).fetchall(),
        )
        self.assertEqual(
            [("original",), ("processed",), ("specification",)],
            self.connection.execute(
                "SELECT type_code FROM document_types ORDER BY type_code"
            ).fetchall(),
        )

    def test_specification_pair_representations_belong_to_the_same_document(self) -> None:
        self.connection.executemany(
            "INSERT INTO documents (document_id, document_type, source_path) VALUES (?, ?, ?)",
            (
                ("spec-a", "specification", "document/specification/spec-a"),
                ("spec-b", "specification", "document/specification/spec-b"),
                ("original-a", "original", "document/original/original-a"),
            ),
        )
        self.connection.executemany(
            "INSERT INTO document_representations "
            "(representation_id, document_id, representation_kind, source_path) "
            "VALUES (?, ?, ?, ?)",
            (
                ("human-a", "spec-a", "human-html", "document/specification/spec-a/index.html"),
                ("ai-a", "spec-a", "ai-skill", ".codex/skills/project-spec-a/SKILL.md"),
                ("wrong-human-a", "spec-a", "other", "document/specification/spec-a/other.txt"),
                ("ai-b", "spec-b", "ai-skill", ".codex/skills/project-spec-b/SKILL.md"),
            ),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO specification_pair_status "
                "(document_id, human_representation_id, ai_representation_id) "
                "VALUES (?, ?, ?)",
                ("spec-a", "human-a", "ai-b"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO specification_pair_status "
                "(document_id, pair_status) VALUES (?, ?)",
                ("spec-a", "aligned"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO specification_pair_status "
                "(document_id, human_representation_id, ai_representation_id, pair_status) "
                "VALUES (?, ?, ?, ?)",
                ("spec-a", "wrong-human-a", "ai-a", "aligned"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO specification_pair_status "
                "(document_id, pair_status) VALUES (?, ?)",
                ("original-a", "unknown"),
            )
        self.connection.execute(
            "INSERT INTO specification_pair_status "
            "(document_id, human_representation_id, ai_representation_id, pair_status) "
            "VALUES (?, ?, ?, ?)",
            ("spec-a", "human-a", "ai-a", "aligned"),
        )

    def test_query_indexes_cover_status_structure_and_relationships(self) -> None:
        indexes = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'index'"
            )
        }
        self.assertTrue(
            {
                "idx_runs_agent_status",
                "idx_loops_status_updated",
                "idx_loop_runs_run",
                "idx_documents_type_status",
                "idx_representations_document_kind",
                "idx_document_relationships_source",
                "idx_document_relationships_target",
                "idx_agent_document_document",
            }
            <= indexes
        )

    def test_schema_has_no_large_body_or_runtime_evidence_columns(self) -> None:
        prohibited = {
            "body",
            "content",
            "events",
            "request",
            "result",
            "receipt",
            "heartbeat",
            "containment",
        }
        for table in (
            "runs",
            "turns",
            "documents",
            "document_representations",
        ):
            with self.subTest(table=table):
                columns = {
                    row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")
                }
                self.assertTrue(prohibited.isdisjoint(columns))

    def test_database_and_runtime_sidecars_are_ignored_and_not_committed(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for name in ("db.sqlite", "db.sqlite-journal", "db.sqlite-shm", "db.sqlite-wal"):
            self.assertIn(f"/.agent-factory/{name}", ignore)
        tracked = subprocess.run(
            ["git", "ls-files", "--", ".agent-factory/db.sqlite*"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual("", tracked)

        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "db.sqlite"
            connection = sqlite3.connect(database)
            try:
                connection.executescript(self.ddl)
                self.assertEqual(
                    "rebuildable-local-projection",
                    connection.execute(
                        "SELECT value FROM schema_metadata WHERE key = 'catalog_kind'"
                    ).fetchone()[0],
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
