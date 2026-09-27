import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/agent/runtime"))
from contract_preflight import validate_contract
from runtime_errors import ContractError


class ContractPreflightTests(unittest.TestCase):
    def document(self):
        return {"contract": {"id": "C1", "version": 2,
                "progress": {"path": "docs/progress/C1/progress.md", "owner": "main"},
                "fileOperations": [
                    {"taskIds": ["T1", "T2"], "operation": "modify", "path": "docs/progress/C1/progress.md"},
                    {"taskIds": ["T2"], "operation": "modify", "path": "target.md"}]},
                "tasks": [{"id": "T1", "requiredFileOperations": []},
                          {"id": "T2", "requiredFileOperations": [{"operation": "modify", "path": "target.md"}]}]}

    def test_main_owned_progress_allows_each_worker_to_complete(self):
        validate_contract(self.document())

    def test_progress_write_required_from_worker_is_rejected(self):
        value = self.document()
        value["tasks"][1]["requiredFileOperations"].append({"operation": "modify", "path": "docs/progress/C1/progress.md"})
        with self.assertRaisesRegex(ContractError, "Main owns"):
            validate_contract(value)

    def test_required_write_cannot_be_assigned_only_to_another_task(self):
        value = self.document()
        value["contract"]["fileOperations"][1]["taskIds"] = ["T1"]
        with self.assertRaisesRegex(ContractError, "outside its contract"):
            validate_contract(value)

    def test_historical_task_list_remains_readable(self):
        validate_contract({"tasks": [{"id": "T1"}]})
