from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "agent"
    / "scripts"
    / "agent_exec.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("agent_exec", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load agent_exec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentExecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_generated_result_path_schema_has_string_type_and_exact_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            schema = json.loads(
                Path(state["responseSchemaPath"]).read_text(encoding="utf-8")
            )

        self.assertEqual(
            schema["properties"]["resultPath"],
            {"type": "string", "const": state["resultPath"]},
        )

    def test_new_command_keeps_configured_sandbox_without_bypass(self) -> None:
        command = self.module.build_codex_command(
            {
                "codex": "codex",
                "projectRoot": "/tmp/project",
                "sandbox": "danger-full-access",
            },
            {"responseSchemaPath": "/tmp/schema.json"},
            None,
        )

        self.assertIn("--sandbox", command)
        self.assertIn("danger-full-access", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_resume_reasserts_project_root_and_stored_sandbox(self) -> None:
        for sandbox in ("danger-full-access", "workspace-write", "read-only"):
            with self.subTest(sandbox=sandbox):
                command = self.module.build_codex_command(
                    {
                        "codex": "codex",
                        "projectRoot": "/tmp/project",
                        "sandbox": sandbox,
                    },
                    {
                        "responseSchemaPath": "/tmp/schema.json",
                    },
                    "session-1",
                )

                self.assertEqual(
                    command[:7],
                    [
                        "codex",
                        "exec",
                        "--cd",
                        "/tmp/project",
                        "--sandbox",
                        sandbox,
                        "resume",
                    ],
                )
                self.assertEqual(
                    command[7:],
                    [
                        "--json",
                        "--output-schema",
                        "/tmp/schema.json",
                        "session-1",
                        "-",
                    ],
                )
                self.assertNotIn(
                    "--dangerously-bypass-approvals-and-sandbox", command
                )

    def test_sandbox_failure_classification_requires_observed_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stderr_path = Path(directory) / "stderr.log"
            stderr_path.write_text(
                "apply_patch verification failed: fs sandbox helper failed with status "
                "exit status: 1: bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
                encoding="utf-8",
            )

            failure = self.module.missing_result_failure(stderr_path)
            self.assertEqual(failure.code, "sandbox_unavailable")

            stderr_path.write_text(
                "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
                encoding="utf-8",
            )
            failure = self.module.missing_result_failure(stderr_path)
            self.assertEqual(failure.code, "result_file_missing")

    def test_work_receipt_requires_exact_binding_and_no_test_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "work-receipt",
                "runId": state["runId"],
                "requestHash": state["requestHash"],
                "outcome": "implemented",
                "changedPaths": ["skills/agent/SKILL.md"],
                "addressedFindingIds": [],
                "tests": {"run": False, "reason": "work-agent-prohibited"},
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")

            self.assertEqual(
                self.module.validate_receipt(
                    Path(directory), state, agent_id="work-agent", run_id=state["runId"]
                ),
                receipt,
            )
            receipt["tests"]["run"] = True
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_tests_invalid")

    def test_review_receipt_enforces_unique_ids_and_decision_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="review-agent",
                actor="main",
                request=b"review request",
                session={"role": "review", "maxAttempts": 1},
                receipt_request_hash="a" * 64,
                reviewed_work_run_id="run-work-1",
            )
            finding = {
                "id": "REV-001",
                "severity": "blocking",
                "path": "skills/agent/scripts/agent_exec.py",
                "location": "validate_receipt",
                "problem": "binding is not checked",
                "evidence": "the expected value is available in state",
                "correction": "compare the exact values",
            }
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "review-receipt",
                "runId": state["runId"],
                "reviewedWorkRunId": "run-work-1",
                "reviewedRequestHash": "a" * 64,
                "decision": "changes_requested",
                "findings": [finding],
                "resolvedFindingIds": [],
                "tests": {"run": False, "reason": "static-review-only"},
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(
                self.module.validate_receipt(
                    Path(directory), state, agent_id="review-agent", run_id=state["runId"]
                ),
                receipt,
            )

            receipt["decision"] = "approved"
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="review-agent", run_id=state["runId"]
                )
            self.assertEqual(raised.exception.code, "receipt_decision_invalid")

            receipt["decision"] = "changes_requested"
            receipt["findings"] = [finding, finding]
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="review-agent", run_id=state["runId"]
                )
            self.assertEqual(raised.exception.code, "receipt_invalid")

    def test_receipt_rejects_adjacent_noncanonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            adjacent = Path(state["resultPath"]).parent.parent / "adjacent-receipt.json"
            adjacent.write_text("{}\n", encoding="utf-8")
            state["receiptPath"] = str(adjacent)

            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    root, state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_path_invalid")

    def test_receipt_rejects_symlinked_run_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            run_path = Path(state["statePath"]).parent
            relocated = run_path.parent / f"{run_path.name}-relocated"
            run_path.rename(relocated)
            run_path.symlink_to(relocated, target_is_directory=True)

            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    root, state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_path_invalid")


if __name__ == "__main__":
    unittest.main()
