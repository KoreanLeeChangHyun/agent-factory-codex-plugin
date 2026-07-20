from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "assets" / "scripts" / "work_unit.py"
INTAKE_SCRIPT = SKILL_ROOT.parent / "intake" / "scripts" / "intake.py"
SCHEMA_ROOT = SKILL_ROOT / "assets" / "schema"
PROFILE = SKILL_ROOT / "assets" / "profiles" / "work-unit.profile.json"
SCHEMA_NAMES = {
    "metadata.schema.json",
    "title.schema.json",
    "table-of-contents.schema.json",
    "section.schema.json",
    "blocks.schema.json",
}
REQUIRED_SECTIONS = [
    "basis",
    "work-definition",
    "plan",
    "execution-context",
    "acceptance-and-verification",
    "execution",
    "ai-review",
    "human-review",
    "report",
]


def run_cli(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def run_intake(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(INTAKE_SCRIPT), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def item(
    item_id: str, kind: str, content: object, **extra: object
) -> dict[str, object]:
    value: dict[str, object] = {"id": item_id, "kind": kind, "content": content}
    value.update(extra)
    return value


def data_args(value: object) -> list[str]:
    arguments: list[str] = []

    def add(path: str, current: object) -> None:
        if isinstance(current, dict):
            if not current:
                arguments.extend(("--empty-object", path))
            for key, child in current.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                add(f"{path}/{escaped}", child)
        elif isinstance(current, list):
            if not current:
                arguments.extend(("--empty-list", path))
            for index, child in enumerate(current):
                add(f"{path}/{index}", child)
        elif isinstance(current, bool):
            arguments.extend(("--boolean", path, str(current).lower()))
        elif isinstance(current, int):
            arguments.extend(("--integer", path, str(current)))
        elif isinstance(current, float):
            arguments.extend(("--number", path, str(current)))
        elif current is None:
            arguments.extend(("--null", path))
        else:
            arguments.extend(("--string", path, str(current)))

    if isinstance(value, (dict, list)):
        if not value:
            raise AssertionError("test data root must not be empty")
        for key, child in (
            value.items() if isinstance(value, dict) else enumerate(value)
        ):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            add(f"/{escaped}", child)
    else:
        raise AssertionError("test data root must be structured")
    return arguments


def data_value(_: Path, __: str, value: object) -> list[str]:
    return data_args(value)


def create_package(root: Path, work_unit_id: str = "sample-unit") -> Path:
    package = root / ".agent-factory" / "work-units" / work_unit_id
    run_cli(
        "create",
        str(package),
        "--id",
        work_unit_id,
        "--title",
        "Sample Work Unit",
        "--project-id",
        "sample-project",
        "--language",
        "ko",
        "--theme",
        "default",
    )
    return package


def create_ready_intake(root: Path, intake_id: str = "source-intake") -> Path:
    package = root / ".agent-factory" / "intakes" / intake_id
    run_intake(
        "create",
        str(package),
        "--id",
        intake_id,
        "--title",
        "Source Intake",
        "--project-id",
        "sample-project",
        "--language",
        "ko",
        "--theme",
        "default",
    )
    required = {
        "request-and-goal": [
            item("REQUEST-001", "human-request", "Work Unit v4"),
            item("OUTCOME-001", "desired-outcome", "Executable unit"),
            item("SUCCESS-001", "success-criterion", "Validation passes"),
        ],
        "context-and-scope": [
            item("CONTEXT-001", "context", "Agent Factory"),
            item("SCOPE-001", "scope", "Work Unit v4"),
            item("OUT-001", "out-of-scope", "Existing data"),
        ],
        "stakeholders-and-approval": [
            item("STAKEHOLDER-001", "stakeholder", "Human"),
            item("OWNER-001", "decision-owner", "Human"),
            item("APPROVAL-001", "approval-boundary", "Human Review"),
        ],
        "evidence-and-findings": [
            item("EVIDENCE-001", "evidence", "Accepted interview")
        ],
        "requirements-and-constraints": [
            item("REQUIREMENT-001", "requirement", "Sectioned package"),
            item("AC-001", "acceptance-criterion", "Anchor resolves"),
        ],
        "decisions-and-open-items": [
            item("DECISION-001", "decision-status", "A/A/A accepted"),
            item("OPEN-STATUS-001", "open-items-status", "No blockers"),
        ],
        "work-unit-basis": [
            item(
                "SPEC-001",
                "specification-impact",
                {"status": "aligned"},
                attributes={"status": "aligned"},
            ),
            item("BASIS-001", "work-unit-basis", "Implement v4 package"),
        ],
    }
    for section_id, content in required.items():
        path = package / "data" / "sections" / f"{section_id}.json"
        section = json.loads(path.read_text(encoding="utf-8"))
        section["content"] = content
        path.write_text(
            json.dumps(section, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    metadata_path = package / "data" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["lifecycle"]["status"] = "ready"
    metadata["readiness"] = {
        "contractValid": True,
        "evidenceComplete": True,
        "requirementsComplete": True,
        "specificationConsistent": True,
        "executionReady": True,
        "reviewedAt": "2026-07-16T00:00:00+00:00",
        "findings": [],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    run_intake("validate", str(package), "--full")
    return package


def ready_items(
    root: Path, intake: Path, work_unit_id: str = "sample-unit"
) -> dict[str, list[dict[str, object]]]:
    intake_ref = {
        "artifactType": "intake",
        "id": intake.name,
        "path": f".agent-factory/intakes/{intake.name}",
        "anchor": {"sectionId": "work-unit-basis", "itemId": "BASIS-001"},
    }
    return {
        "basis": [
            item(
                "BASIS-REF-001",
                "intake-basis-ref",
                "Accepted basis",
                sourceRefs=[intake_ref],
            )
        ],
        "work-definition": [
            item("GOAL-001", "goal", "Implement the scoped Work Unit"),
            item("SCOPE-001", "scope", ["manager", "schemas"]),
            item("OUT-001", "out-of-scope", ["existing data"]),
            item("OUTPUT-001", "expected-output", "Validated v4 package"),
        ],
        "plan": [item("PLAN-001", "plan-step", "Plan -> Work -> AI Review -> Report")],
        "execution-context": [
            item(
                "EXEC-CONTEXT-001",
                "execution-context",
                {
                    "goalId": work_unit_id,
                    "objective": "Implement the scoped Work Unit",
                    "execInvocation": f"/goal {work_unit_id}",
                    "executionAgent": "Codex",
                    "repository": str(root),
                    "baseRef": "main",
                    "branch": f"work-unit/{work_unit_id}",
                    "worktreePath": str(
                        root / ".agent-factory" / "worktree" / work_unit_id
                    ),
                },
            )
        ],
        "acceptance-and-verification": [
            item("AC-001", "acceptance-criterion", "Package validates"),
            item("DOD-001", "definition-of-done", "Evidence recorded"),
            item("TEST-001", "test-criterion", "Regression passes"),
            item(
                "QUALITY-001",
                "quality-check",
                "Not run",
                attributes={"status": "not-run", "evidence": []},
            ),
        ],
        "execution": [
            item(
                "EXECUTION-STATUS",
                "execution-result",
                "Not started",
                attributes={"status": "not-started", "verificationResult": "not-run"},
            )
        ],
        "ai-review": [
            item("AI-CHECKLIST-001", "ai-checklist", ["Scope", "Tests"]),
            item(
                "AI-REVIEW-STATUS",
                "ai-review-result",
                "Not run",
                attributes={"result": "not-run", "checklistResult": "not-run"},
            ),
        ],
        "human-review": [
            item("HUMAN-CHECKLIST-001", "human-checklist", ["Inspect package"]),
            item(
                "HUMAN-METHOD-001", "human-review-method", "Inspect evidence and decide"
            ),
            item(
                "HUMAN-REVIEW-STATUS",
                "human-review-result",
                "Pending",
                attributes={"status": "pending"},
            ),
        ],
        "report": [
            item(
                "REPORT-STATUS",
                "report-result",
                "Not run",
                attributes={"verificationResult": "not-run", "evidence": []},
            )
        ],
    }


def populate_ready_candidate(root: Path, package: Path, intake: Path) -> None:
    for section_id, content in ready_items(root, intake, package.name).items():
        source = data_value(root, f"{section_id}.json", content)
        run_cli("section-items-put", str(package), section_id, *source)
    readiness = data_value(
        root,
        "readiness.json",
        {
            "contractValid": False,
            "intakeTraceabilityValid": True,
            "definitionComplete": True,
            "executionContextComplete": True,
            "verificationPlanComplete": True,
            "reviewedAt": "2026-07-16T00:00:00+00:00",
            "findings": [],
        },
    )
    run_cli("metadata-set", str(package), "readiness", *readiness)


class WorkUnitV4ManagerTests(unittest.TestCase):
    def initialize_and_start_execution(
        self,
        package: Path,
        *,
        invocation_id: str = "session-1",
        head_commit: str = "a" * 40,
    ) -> dict[str, object]:
        run_cli(
            "execution-init",
            str(package),
            "--head-commit",
            head_commit,
        )
        return json.loads(
            run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                invocation_id,
                "--head-commit",
                head_commit,
            ).stdout
        )

    def current_execution_target(self, package: Path) -> dict[str, object]:
        shown = json.loads(
            run_cli("show", str(package), "--section", "execution-context").stdout
        )
        state = next(
            entry for entry in shown["content"] if entry["kind"] == "execution-state"
        )["content"]
        return {
            "contractVersion": state["contractVersion"],
            "revision": state["currentRevision"],
            "attempt": state["currentAttempt"],
            "invocationId": state["invocationId"],
            "headCommit": state["subject"]["digest"],
        }

    def integration_receipt(self, package: Path) -> dict[str, object]:
        context = ready_items(
            package_project_root := package.parent.parent.parent,
            package_project_root / ".agent-factory" / "intakes" / "source-intake",
            package.name,
        )["execution-context"][0]["content"]
        return {
            "command": "integrate",
            "context": {
                "workUnitId": package.name,
                "repository": context["repository"],
                "sourceBranch": context["branch"],
                "targetBranch": "main",
                "worktreePath": context["worktreePath"],
                "humanDecision": "approved",
                "sourceCommit": "a" * 40,
                "targetBeforeCommit": "b" * 40,
                "targetAfterCommit": "a" * 40,
                "relationship": "fast-forwardable",
                "strategy": "ff-only",
                "operationResult": "fast-forwarded",
            },
            "error": None,
            "ok": True,
            "operations": [
                {
                    "args": [
                        "git",
                        "-C",
                        context["repository"],
                        "merge",
                        "--ff-only",
                        "a" * 40,
                    ],
                    "returnCode": 0,
                    "stderr": "",
                    "stdout": "",
                }
            ],
            "schemaVersion": "1.0.0",
            "state": "integrated",
        }

    def test_schemas_and_profile_define_v4_sectioned_contract(self) -> None:
        payload = json.loads(run_cli("check-schemas").stdout)
        self.assertEqual(payload["schemaVersion"], "4.0.0")
        self.assertEqual(set(payload["schemas"]), SCHEMA_NAMES)
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["version"], "4.0.0")
        self.assertEqual(profile["implementationStatus"], "implemented")
        self.assertEqual(profile["storageContract"], "sectioned-document-package-v2")
        self.assertEqual(
            [entry["id"] for entry in profile["profileRequiredSections"]],
            REQUIRED_SECTIONS,
        )

    def test_create_builds_common_sectioned_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            self.assertFalse((package / "data" / "work-unit.json").exists())
            self.assertTrue((package / "data" / "metadata.json").is_file())
            self.assertTrue((package / "data" / "title.json").is_file())
            self.assertTrue((package / "data" / "table-of-contents.json").is_file())
            self.assertTrue((package / "blocks" / "index.json").is_file())
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(
                [entry["id"] for entry in toc["sections"]], REQUIRED_SECTIONS
            )
            result = json.loads(run_cli("validate", str(package), "--full").stdout)
            self.assertEqual(result["status"], "backlog")
            self.assertEqual(result["schemaVersion"], "4.0.0")

    def test_batch_update_increments_one_document_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            source = data_value(
                root,
                "batch.json",
                [
                    item(f"PLAN-{index:04d}", "plan-step", index)
                    for index in range(1000)
                ],
            )
            run_cli("section-items-put", str(package), "plan", *source)
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertEqual(metadata["documentVersion"], "1.0.1")
            shown = json.loads(
                run_cli("show", str(package), "--section", "plan").stdout
            )
            self.assertEqual(len(shown["content"]), 1000)

    def test_optional_section_lifecycle_preserves_required_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section = {
                "id": "rework-history",
                "title": "Rework History",
                "content": [],
                "subsections": [],
            }
            source = data_value(root, "optional.json", section)
            run_cli(
                "section-add",
                str(package),
                *source,
                "--after",
                "report",
            )
            run_cli("section-move", str(package), "rework-history", "--before", "basis")
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(toc["sections"][0]["id"], "rework-history")
            run_cli("section-remove", str(package), "rework-history")
            self.assertFalse(
                (package / "data" / "sections" / "rework-history.json").exists()
            )
            self.assertTrue(
                json.loads(run_cli("validate", str(package)).stdout)["valid"]
            )

    def test_ready_transition_resolves_package_root_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            result = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["validationMode"], "full")

    def test_shared_intake_mutation_policy_does_not_reopen_working_work_unit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            before = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            update = data_value(
                root, "working-update.json", item("PLAN-002", "plan-step", "Execute")
            )

            run_cli("section-item-put", str(package), "plan", *update)

            after = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(after["lifecycle"]["status"], "working")
            self.assertEqual(after["readiness"], before["readiness"])

    def test_missing_anchor_item_rejected_without_mutating_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            relation = data_value(
                root,
                "relations.json",
                [
                    {
                        "type": "based-on",
                        "target": {
                            "artifactType": "intake",
                            "id": intake.name,
                            "path": f".agent-factory/intakes/{intake.name}",
                            "anchor": {
                                "sectionId": "work-unit-basis",
                                "itemId": "MISSING",
                            },
                        },
                    }
                ],
            )
            result = run_cli(
                "metadata-set",
                str(package),
                "relations",
                *relation,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("typed reference anchor item does not exist", result.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

    def test_anchor_path_must_target_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            source = data_value(
                root,
                "bad-basis.json",
                item(
                    "BASIS-REF-001",
                    "intake-basis-ref",
                    "Bad path",
                    sourceRefs=[
                        {
                            "artifactType": "intake",
                            "id": intake.name,
                            "path": f".agent-factory/intakes/{intake.name}/data/sections/work-unit-basis.json",
                            "anchor": {
                                "sectionId": "work-unit-basis",
                                "itemId": "BASIS-001",
                            },
                        }
                    ],
                ),
            )
            result = run_cli(
                "section-item-put",
                str(package),
                "basis",
                *source,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "anchor path must target a sectioned package root", result.stderr
            )

    def test_ready_rejects_missing_required_kind_and_invalid_execution_branch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            content = ready_items(root, intake, package.name)
            content["work-definition"] = [
                entry
                for entry in content["work-definition"]
                if entry["kind"] != "expected-output"
            ]
            content["execution-context"][0]["content"]["branch"] = "feature/wrong"
            for section_id, items in content.items():
                source = data_value(root, f"invalid-{section_id}.json", items)
                run_cli(
                    "section-items-put",
                    str(package),
                    section_id,
                    *source,
                )
            readiness = data_value(
                root,
                "readiness.json",
                {
                    "contractValid": True,
                    "intakeTraceabilityValid": True,
                    "definitionComplete": True,
                    "executionContextComplete": True,
                    "verificationPlanComplete": True,
                    "reviewedAt": "2026-07-16T00:00:00+00:00",
                    "findings": [],
                },
            )
            run_cli(
                "metadata-set",
                str(package),
                "readiness",
                *readiness,
            )
            result = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required content kinds", result.stderr)

            expected = data_value(
                root, "expected.json", item("OUTPUT-001", "expected-output", "Output")
            )
            run_cli(
                "section-item-put",
                str(package),
                "work-definition",
                *expected,
            )
            result = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("execution context branch must equal", result.stderr)

    def test_ready_rejects_codex_global_option_after_exec_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            worktree_path = context["content"]["worktreePath"]
            context["content"]["execInvocation"] = (
                "codex exec --sandbox danger-full-access --ask-for-approval never "
                f"-C {worktree_path} 'Execute the Work Unit'"
            )
            source = data_value(root, "invalid-exec-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )

            rejected = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("must appear before the exec subcommand", rejected.stderr)

            context["content"]["execInvocation"] = (
                "codex --ask-for-approval never exec --sandbox danger-full-access "
                f"-C {worktree_path} 'Execute the Work Unit'"
            )
            source = data_value(root, "valid-exec-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )
            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")

    def test_ready_rejects_noncanonical_worktree_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"]["worktreePath"] = str(
                root.parent / "worktrees" / package.name
            )
            source = data_value(root, "noncanonical-worktree.json", [context])
            run_cli(
                "section-items-put",
                str(package),
                "execution-context",
                *source,
            )

            rejected = run_cli("transition", str(package), "ready", check=False)

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("execution context worktreePath must equal", rejected.stderr)

    def test_execution_attempt_retry_and_resume_preserve_identity_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")

            started = self.initialize_and_start_execution(package)
            self.assertEqual(started["status"], "working")
            shown = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["contractVersion"], "1.0.0")
            self.assertEqual(state["currentRevision"], 1)
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(state["invocationId"], "session-1")
            self.assertEqual(state["invocationChain"], ["session-1"])
            self.assertEqual(state["subject"]["digest"], "a" * 40)
            self.assertEqual(state["history"], [])

            run_cli(
                "attempt-resume",
                str(package),
                "--invocation-id",
                "session-1-resume",
            )
            resumed = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in resumed["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(state["invocationId"], "session-1")
            self.assertEqual(
                state["invocationChain"], ["session-1", "session-1-resume"]
            )

            run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                "session-2",
                "--head-commit",
                "b" * 40,
            )
            retried = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in retried["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentRevision"], 1)
            self.assertEqual(state["currentAttempt"], 2)
            self.assertEqual(state["invocationId"], "session-2")
            self.assertEqual(state["invocationChain"], ["session-2"])
            self.assertEqual(state["subject"]["digest"], "b" * 40)
            self.assertEqual(len(state["history"]), 1)
            self.assertEqual(state["history"][0]["revision"], 1)
            self.assertEqual(state["history"][0]["attempt"], 1)
            self.assertEqual(
                state["history"][0]["invocationChain"],
                ["session-1", "session-1-resume"],
            )
            before = (
                package / "data" / "sections" / "execution-context.json"
            ).read_bytes()
            duplicate = run_cli(
                "attempt-resume",
                str(package),
                "--invocation-id",
                "session-1-resume",
                check=False,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("must be unique in execution history", duplicate.stderr)
            self.assertEqual(
                (package / "data" / "sections" / "execution-context.json").read_bytes(),
                before,
            )

    def test_active_execution_requires_init_and_state_is_manager_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()

            rejected = run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                "session-1",
                "--head-commit",
                "a" * 40,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("requires execution-init", rejected.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

            direct_state = item(
                "EXECUTION-STATE-001",
                "execution-state",
                {
                    "contractVersion": "1.0.0",
                    "state": "planned",
                    "subject": {"algorithm": "gitCommit", "digest": "a" * 40},
                    "currentRevision": 1,
                    "currentAttempt": None,
                    "invocationId": None,
                    "invocationChain": [],
                    "history": [],
                },
            )
            rejected = run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *data_value(root, "direct-state.json", direct_state),
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("execution-state is manager-owned", rejected.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

    def test_rework_invalidates_results_and_review_rejects_stale_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            target = self.current_execution_target(package)
            block = root / "tests.log"
            block.write_text("tests passed\n", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(block),
                "--path",
                "blocks/logs/tests.log",
                "--media-type",
                "text/plain",
                "--description",
                "tests",
            )
            replacements = {
                "execution": item(
                    "EXECUTION-STATUS",
                    "execution-result",
                    "Complete",
                    attributes={
                        "status": "complete",
                        "verificationResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "acceptance-and-verification": item(
                    "QUALITY-001",
                    "quality-check",
                    "Pass",
                    attributes={
                        "status": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "ai-review": item(
                    "AI-REVIEW-STATUS",
                    "ai-review-result",
                    "Pass",
                    attributes={
                        "result": "pass",
                        "checklistResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "report": item(
                    "REPORT-STATUS",
                    "report-result",
                    "Pass",
                    attributes={
                        "verificationResult": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
            }
            for section_id, replacement in replacements.items():
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *data_value(root, f"replace-{section_id}.json", replacement),
                )
            run_cli("transition", str(package), "review")
            run_cli(
                "rework-start",
                str(package),
                "--human-decision",
                "approved",
            )
            run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                "session-2",
                "--head-commit",
                "b" * 40,
            )

            shown = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentRevision"], 2)
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(len(state["history"]), 1)
            self.assertEqual(
                state["history"][0]["outcomes"]["report-result"]["attributes"][
                    "verificationResult"
                ],
                "pass",
            )
            execution = json.loads(
                run_cli("show", str(package), "--section", "execution").stdout
            )["content"][0]
            self.assertEqual(execution["attributes"]["status"], "pending")

            for section_id, replacement in replacements.items():
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *data_value(root, f"stale-{section_id}.json", replacement),
                )
            rejected = run_cli("transition", str(package), "review", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("current execution target", rejected.stderr)

    def test_existing_done_v4_without_execution_state_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            target = self.current_execution_target(package)
            block = root / "tests.log"
            block.write_text("tests passed\n", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(block),
                "--path",
                "blocks/logs/tests.log",
                "--media-type",
                "text/plain",
                "--description",
                "tests",
            )
            replacements = {
                "execution": item(
                    "EXECUTION-STATUS",
                    "execution-result",
                    "Complete",
                    attributes={
                        "status": "complete",
                        "verificationResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "acceptance-and-verification": item(
                    "QUALITY-001",
                    "quality-check",
                    "Pass",
                    attributes={
                        "status": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "ai-review": item(
                    "AI-REVIEW-STATUS",
                    "ai-review-result",
                    "Pass",
                    attributes={
                        "result": "pass",
                        "checklistResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "report": item(
                    "REPORT-STATUS",
                    "report-result",
                    "Pass",
                    attributes={
                        "verificationResult": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
            }
            for section_id, replacement in replacements.items():
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *data_value(root, section_id, replacement),
                )
            run_cli("transition", str(package), "review")
            run_cli("transition", str(package), "done", "--human-review", "approved")

            report_path = package / "data" / "sections" / "report.json"
            report_before = report_path.read_bytes()
            immutable = run_cli(
                "section-item-put",
                str(package),
                "report",
                *data_value(
                    root,
                    "mutated-done-report.json",
                    item(
                        "REPORT-STATUS",
                        "report-result",
                        "Changed after approval",
                        attributes={
                            "verificationResult": "pass",
                            "evidence": ["blocks/logs/tests.log"],
                            "executionTarget": target,
                        },
                    ),
                ),
                check=False,
            )
            self.assertNotEqual(immutable.returncode, 0)
            self.assertIn(
                "done Work Unit outcome records are immutable", immutable.stderr
            )
            self.assertEqual(report_path.read_bytes(), report_before)

            human_review_path = package / "data" / "sections" / "human-review.json"
            human_review = json.loads(human_review_path.read_text(encoding="utf-8"))
            approval = next(
                entry
                for entry in human_review["content"]
                if entry["kind"] == "human-review-result"
            )
            approval["attributes"]["executionTarget"]["headCommit"] = "b" * 40
            human_review_path.write_text(
                json.dumps(human_review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            stale = run_cli("validate", str(package), "--full", check=False)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("human-review-result approval", stale.stderr)

            execution_context_path = (
                package / "data" / "sections" / "execution-context.json"
            )
            execution_context = json.loads(
                execution_context_path.read_text(encoding="utf-8")
            )
            execution_context["content"] = [
                entry
                for entry in execution_context["content"]
                if entry["kind"] != "execution-state"
            ]
            execution_context_path.write_text(
                json.dumps(execution_context, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(
                json.loads(run_cli("validate", str(package), "--full").stdout)["valid"]
            )

    def test_review_and_done_transitions_enforce_results_and_atomic_human_approval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            target = self.current_execution_target(package)
            premature = run_cli("transition", str(package), "review", check=False)
            self.assertNotEqual(premature.returncode, 0)
            self.assertIn(
                "review transition requires passing execution", premature.stderr
            )

            replacements = {
                "execution": item(
                    "EXECUTION-STATUS",
                    "execution-result",
                    "Complete",
                    attributes={
                        "status": "complete",
                        "verificationResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "acceptance-and-verification": item(
                    "QUALITY-001",
                    "quality-check",
                    "Pass",
                    attributes={
                        "status": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "ai-review": item(
                    "AI-REVIEW-STATUS",
                    "ai-review-result",
                    "Pass",
                    attributes={
                        "result": "pass",
                        "checklistResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "report": item(
                    "REPORT-STATUS",
                    "report-result",
                    "Pass",
                    attributes={
                        "verificationResult": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
            }
            block = root / "tests.log"
            block.write_text("tests passed\n", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(block),
                "--path",
                "blocks/logs/tests.log",
                "--media-type",
                "text/plain",
                "--description",
                "tests",
            )
            for section_id, replacement in replacements.items():
                source = data_value(root, f"replace-{section_id}.json", replacement)
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *source,
                )
            self.assertEqual(
                json.loads(run_cli("transition", str(package), "review").stdout)[
                    "status"
                ],
                "review",
            )
            denied = run_cli("transition", str(package), "done", check=False)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("requires --human-review approved", denied.stderr)
            done = json.loads(
                run_cli(
                    "transition", str(package), "done", "--human-review", "approved"
                ).stdout
            )
            self.assertEqual(done["status"], "done")
            shown = json.loads(
                run_cli("show", str(package), "--section", "human-review").stdout
            )
            status = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "human-review-result"
            )
            self.assertEqual(status["attributes"]["status"], "approved")
            receipt = root / "done-integration-receipt.json"
            receipt.write_text(
                json.dumps(self.integration_receipt(package)), encoding="utf-8"
            )
            integrated = json.loads(
                run_cli(
                    "integration-put",
                    str(package),
                    str(receipt),
                    "--path",
                    "blocks/integration/done-receipt.json",
                ).stdout
            )
            self.assertEqual(integrated["status"], "done")

    def test_orphan_block_style_data_and_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            orphan = package / "blocks" / "orphan.log"
            orphan.write_text("orphan", encoding="utf-8")
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("block file set", result.stderr)
            orphan.unlink()
            styled = data_value(
                root,
                "styled.json",
                item("STYLE-001", "plan-step", {"style": {"color": "red"}}),
            )
            result = run_cli(
                "section-item-put",
                str(package),
                "plan",
                *styled,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("actual style", result.stderr)

            source = root / "evidence.log"
            source.write_text("evidence", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(source),
                "--path",
                "blocks/evidence.log",
                "--media-type",
                "text/plain",
                "--description",
                "evidence",
            )
            (package / "blocks" / "evidence.log").write_text(
                "tampered", encoding="utf-8"
            )
            result = run_cli("validate", str(package), "--full", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("block integrity mismatch", result.stderr)

    def test_integration_put_atomically_registers_normalized_result_and_raw_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps(self.integration_receipt(package)), encoding="utf-8"
            )

            result = run_cli(
                "integration-put",
                str(package),
                str(receipt),
                "--path",
                "blocks/integration/receipt.json",
            )

            self.assertTrue(json.loads(result.stdout)["valid"])
            report = json.loads(
                run_cli("show", str(package), "--section", "report").stdout
            )
            integration = next(
                entry
                for entry in report["content"]
                if entry["kind"] == "integration-result"
            )
            self.assertEqual(integration["content"]["workUnitId"], package.name)
            self.assertEqual(
                integration["content"]["operationResult"], "fast-forwarded"
            )
            self.assertEqual(integration["blockRef"], "blocks/integration/receipt.json")
            self.assertTrue(
                json.loads(run_cli("validate", str(package), "--full").stdout)["valid"]
            )

            version = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )["documentVersion"]
            run_cli(
                "integration-put",
                str(package),
                str(receipt),
                "--path",
                "blocks/integration/receipt.json",
            )
            repeated = json.loads(
                run_cli("show", str(package), "--section", "report").stdout
            )
            self.assertEqual(
                len(
                    [
                        entry
                        for entry in repeated["content"]
                        if entry["kind"] == "integration-result"
                    ]
                ),
                1,
            )
            self.assertEqual(
                json.loads((package / "data" / "metadata.json").read_text())[
                    "documentVersion"
                ],
                version,
            )

            recovered_value = self.integration_receipt(package)
            recovered_value["context"].update(
                {
                    "operationResult": "already-merged",
                    "relationship": "already-merged",
                    "strategy": "no-ff",
                    "targetBeforeCommit": "a" * 40,
                }
            )
            recovered_value["operations"] = []
            recovered_value["state"] = "already-merged"
            recovered = root / "recovered-receipt.json"
            recovered.write_text(json.dumps(recovered_value), encoding="utf-8")
            run_cli(
                "integration-put",
                str(package),
                str(recovered),
                "--path",
                "blocks/integration/recovered-receipt.json",
            )
            recovered_report = json.loads(
                run_cli("show", str(package), "--section", "report").stdout
            )
            self.assertEqual(
                len(
                    [
                        entry
                        for entry in recovered_report["content"]
                        if entry["kind"] == "integration-result"
                    ]
                ),
                2,
            )

            (package / "blocks" / "integration" / "receipt.json").write_text(
                "tampered", encoding="utf-8"
            )
            rejected = run_cli("validate", str(package), "--full", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("block integrity mismatch", rejected.stderr)

    def test_integration_put_rejects_receipt_for_another_work_unit_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            receipt_value = self.integration_receipt(package)
            receipt_value["context"]["workUnitId"] = "another-unit"
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps(receipt_value), encoding="utf-8")
            before = {
                path.relative_to(package): path.read_bytes()
                for path in package.rglob("*")
                if path.is_file()
            }

            rejected = run_cli(
                "integration-put",
                str(package),
                str(receipt),
                "--path",
                "blocks/integration/receipt.json",
                check=False,
            )

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("receipt workUnitId must match package id", rejected.stderr)
            after = {
                path.relative_to(package): path.read_bytes()
                for path in package.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_integration_put_rejects_symlink_receipt_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps(self.integration_receipt(package)), encoding="utf-8"
            )
            receipt_link = root / "receipt-link.json"
            receipt_link.symlink_to(receipt)
            before = (package / "data" / "metadata.json").read_bytes()

            rejected = run_cli(
                "integration-put",
                str(package),
                str(receipt_link),
                "--path",
                "blocks/integration/receipt.json",
                check=False,
            )

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("readable non-symlink file", rejected.stderr)
            self.assertEqual((package / "data" / "metadata.json").read_bytes(), before)
            self.assertFalse((package / "blocks" / "integration").exists())

    def test_interrupted_transaction_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            title_path = package / "data" / "title.json"
            original = title_path.read_bytes()
            transaction_root = package / ".manager" / "transactions" / "interrupted"
            backup = transaction_root / "backup" / "0.old"
            backup.parent.mkdir(parents=True)
            backup.write_bytes(original)
            title_path.write_text("{invalid", encoding="utf-8")
            journal = {
                "version": 1,
                "id": "interrupted",
                "entries": [
                    {
                        "path": "data/title.json",
                        "existed": True,
                        "backup": "backup/0.old",
                        "stage": "stage/0.new",
                    }
                ],
            }
            journal_path = package / ".manager" / "transaction.json"
            journal_path.parent.mkdir(exist_ok=True)
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            self.assertTrue(
                json.loads(run_cli("validate", str(package)).stdout)["valid"]
            )
            self.assertEqual(title_path.read_bytes(), original)
            self.assertFalse(journal_path.exists())

    def test_toc_digest_owns_section_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            toc_path = package / "data" / "table-of-contents.json"
            toc = json.loads(toc_path.read_text())
            toc["sections"].reverse()
            toc_path.write_text(json.dumps(toc), encoding="utf-8")
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("table of contents integrity", result.stderr)


if __name__ == "__main__":
    unittest.main()
