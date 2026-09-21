from __future__ import annotations

import runtime_test_home  # Isolate all runtime subprocesses from the real home.

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
EXEC_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "exec.py"
LOOP_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "loop.py"


def load_modules():
    exec_spec = importlib.util.spec_from_file_location("exec", EXEC_SCRIPT)
    if exec_spec is None or exec_spec.loader is None:
        raise RuntimeError("cannot load exec runtime")
    agent_exec = importlib.util.module_from_spec(exec_spec)
    exec_spec.loader.exec_module(agent_exec)
    sys.modules["exec"] = agent_exec
    loop_spec = importlib.util.spec_from_file_location("loop", LOOP_SCRIPT)
    if loop_spec is None or loop_spec.loader is None:
        raise RuntimeError("cannot load loop runtime")
    agent_loop = importlib.util.module_from_spec(loop_spec)
    loop_spec.loader.exec_module(agent_loop)
    return agent_exec, agent_loop


class FakeRuntime:
    def __init__(self, root: Path, agent_exec) -> None:
        self.root = root
        self.agent_exec = agent_exec
        self.runs: dict[tuple[str, str], dict] = {}
        self.dispatches: list[dict] = []
        self.next_run = 1
        self.fail_before_call = False
        self.lose_ack = False

    def dispatch(self, **values):
        if self.fail_before_call:
            raise self.agent_exec.ContractError("child_runtime_failure", "crash before call")
        run_id = f"run-{self.next_run}"
        self.next_run += 1
        request = Path(values["request_file"]).read_bytes()
        request_hash = hashlib.sha256(request).hexdigest()
        binding_hash = (
            hashlib.sha256(Path(values["capability_binding_file"]).read_bytes()).hexdigest()
            if values.get("capability_binding_file") else None
        )
        dispatch_tuple = {
            "agentId": values["agent_id"],
            "role": values["role"],
            "actor": "main",
            "requestHash": request_hash,
            "receiptRequestHash": values["request_hash"],
            "verifiedWorkRunId": values["verified_work_run_id"],
            "operation": values["operation"],
            "humanApprovalPolicy": values["human_approval_policy"],
        }
        if values["execution"].get("taskBinding"):
            dispatch_tuple["taskBinding"] = values["execution"]["taskBinding"]
        if "executionPolicy" in values["execution"]:
            dispatch_tuple["executionPolicy"] = values["execution"]["executionPolicy"]
        permission = values["execution"].get("agentPermissions", {}).get(values["role"])
        if permission:
            dispatch_tuple["executionPolicy"] = permission["policy"]
            dispatch_tuple["humanApprovalPolicy"] = permission["humanApprovalPolicy"]
        if values["operation"] == "submit" and values["execution"].get("model"):
            dispatch_tuple.setdefault("executionOptions", {})["model"] = values["execution"]["model"]
        profile = values["execution"].get("agentModels", {}).get(values["role"], {})
        if profile:
            dispatch_tuple.setdefault("executionOptions", {}).update(profile)
        if values["role"] == "work" and values["execution"].get("taskMode"):
            dispatch_tuple.setdefault("executionOptions", {})["taskMode"] = values["execution"]["taskMode"]
        if values["role"] == "work":
            from task_modes import work_goal_options
            dispatch_tuple["executionOptions"] = work_goal_options(
                dispatch_tuple.get("executionOptions", {}), request.decode("utf-8"))
        if binding_hash is not None:
            dispatch_tuple["capabilityBindingHash"] = binding_hash
        directory = self.agent_exec.agent_root(self.root) / values["agent_id"] / "runs" / run_id
        directory.mkdir(parents=True, exist_ok=True)
        session_id = f"session-{values['agent_id']}"
        run = {
            "runId": run_id,
            "agentId": values["agent_id"],
            "role": values["role"],
            "status": "accepted",
            "requestHash": request_hash,
            "receiptRequestHash": values["request_hash"],
            "verifiedWorkRunId": values["verified_work_run_id"],
            "dispatchId": values["dispatch_id"],
            "dispatchTuple": dispatch_tuple,
            "statePath": str(directory / "state.json"),
            "resultPath": str(directory / "result.md"),
            "receiptPath": str(directory / "receipt.json"),
            "receiptSchemaPath": str(directory / "receipt.schema.json"),
            "sessionId": session_id,
        }
        self.agent_exec.atomic_write_json(directory / "state.json", run)
        self.agent_exec.atomic_write_json(directory / "receipt.schema.json", {})
        session = self.agent_exec.session_file(self.root, values["agent_id"])
        session.parent.mkdir(parents=True, exist_ok=True)
        if not session.exists():
            self.agent_exec.atomic_write_json(
                session, {"role": values["role"], "sessionId": session_id}
            )
        self.runs[(values["agent_id"], run_id)] = run
        self.dispatches.append(values)
        if self.lose_ack:
            self.lose_ack = False
            raise self.agent_exec.ContractError("child_runtime_failure", "ack lost")
        return {"runId": run_id}

    def status(self, agent_id, run_id):
        return self.runs[(agent_id, run_id)]

    def status_dispatch(self, agent_id, dispatch_id):
        matches = [
            run for (managed, _run_id), run in self.runs.items()
            if managed == agent_id and run["dispatchId"] == dispatch_id
        ]
        if not matches:
            raise self.agent_exec.ContractError("dispatch_not_found", "not dispatched")
        return matches[0]

    def complete_work(self, agent_id: str, run_id: str, addressed: list[str] | None = None):
        run = self.runs[(agent_id, run_id)]
        receipt = {
            "schemaVersion": "0.1.0", "kind": "work-receipt", "runId": run_id,
            "requestHash": run["receiptRequestHash"], "outcome": "completed",
            "changedPaths": ["changed.txt"], "addressedFindingIds": addressed or [],
            "tests": {"run": False, "reason": "work-agent-prohibited"},
        }
        Path(run["resultPath"]).write_text("work result\n", encoding="utf-8")
        Path(run["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
        run["status"] = "completed"
        return run

    def complete_verification(self, agent_id: str, run_id: str, decision: str):
        run = self.runs[(agent_id, run_id)]
        findings = [] if decision == "pass" else [{
            "id": "finding-1", "path": "changed.txt", "location": "1",
            "problem": "incorrect", "evidence": "observed mismatch", "correction": "fix it",
        }]
        receipt = {
            "schemaVersion": "0.1.0", "kind": "verification-receipt", "runId": run_id,
            "verifiedWorkRunId": run["verifiedWorkRunId"],
            "verifiedRequestHash": run["receiptRequestHash"],
            "decision": decision, "findings": findings,
        }
        Path(run["resultPath"]).write_text("verification result\n", encoding="utf-8")
        Path(run["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
        run["status"] = "completed"
        return run


class AgentLoopContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent_exec, self.agent_loop = load_modules()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.request = self.root / "request.md"
        self.request.write_text("bounded work\n", encoding="utf-8")
        self.tasks = self.root / "tasks.json"
        self.tasks.write_text(json.dumps({"id": "flow-one", "title": "Bounded work", "tasks": [
            {"id": "task-one", "title": "Implement work", "description": "bounded work",
             "completionCriteria": "Work passes checks", "requestHash": hashlib.sha256(self.request.read_bytes()).hexdigest()}]}))
        self.runtime = FakeRuntime(self.root, self.agent_exec)
        self.runtime_patch = mock.patch.object(self.agent_loop, "AgentRuntime", return_value=self.runtime)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    def start(self, extra: list[str] | None = None):
        arguments = [
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--task-list-file", str(self.tasks), "--task-id", "task-one",
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true",
        ]
        arguments.extend(extra or [])
        args = self.agent_loop.build_parser().parse_args(arguments)
        return self.agent_loop.start_loop(args)

    def close(self, started):
        args = self.agent_loop.build_parser().parse_args([
            "close", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", started["loopId"], "--actor", "human",
            "--authorization-reference", "test-request", "--decision-evidence", "Close failed flow",
        ])
        return self.agent_loop.close_loop(args)

    def test_close_failed_preserves_evidence_and_cannot_resume(self):
        started = self.start()
        failed = self.fail_work_receipt(started)
        path = Path(started["statePath"])
        state = json.loads(path.read_text())
        state["workflow"]["tasks"].append({"id": "later", "workStatus": "pending", "verificationStatus": "pending"})
        self.agent_exec.atomic_write_json(path, state)
        closed = self.close(started)
        self.assertEqual(closed["status"], "cancelled")
        self.assertEqual(closed["controlPlaneError"], failed["controlPlaneError"])
        self.assertEqual(closed["latestWorkRunId"], failed["latestWorkRunId"])
        self.assertEqual(closed["workflow"]["tasks"][0]["workStatus"], "failed")
        self.assertEqual(closed["workflow"]["tasks"][1]["workStatus"], "cancelled")
        self.assertEqual(closed["terminalReason"]["authorizationReference"], "test-request")
        self.assertEqual(self.close(started), closed)
        self.assertEqual(self.reconcile(started), closed)
        self.assertEqual(self.recover_receipt(started), closed)
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(self.runtime.runs[("work-agent", started["latestWorkRunId"])]["status"], "failed")

    def test_close_rejects_active_and_uncertain_dispatch(self):
        started = self.start()
        with self.assertRaises(self.agent_exec.ContractError):
            self.close(started)
        self.fail_work_receipt(started)
        path = Path(started["statePath"])
        state = json.loads(path.read_text())
        state["pendingDispatch"] = {"dispatchId": "uncertain"}
        self.agent_exec.atomic_write_json(path, state)
        with self.assertRaises(self.agent_exec.ContractError):
            self.close(started)
        self.assertEqual(json.loads(path.read_text())["status"], "runtime-error")

    def test_close_rechecks_child_before_closing(self):
        started = self.start()
        self.fail_work_receipt(started)
        self.runtime.runs[("work-agent", started["latestWorkRunId"])]["status"] = "running"
        with self.assertRaises(self.agent_exec.ContractError):
            self.close(started)

    def reconcile(self, started):
        args = self.agent_loop.build_parser().parse_args([
            "reconcile", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", started["loopId"],
        ])
        return self.agent_loop.reconcile_loop(args)

    def recover_receipt(self, started):
        args = self.agent_loop.build_parser().parse_args([
            "recover-receipt", "--project-root", str(self.root),
            "--work-agent", "work-agent", "--loop-id", started["loopId"],
        ])
        return self.agent_loop.recover_receipt(args)

    def fail_work_receipt(self, started, code="receipt_path_contract_invalid", message=None):
        run = self.runtime.runs[("work-agent", started["latestWorkRunId"])]
        run.update({
            "status": "failed",
            "error": {
                "code": code,
                "message": message or "changedPaths must contain only project-root-relative paths",
            },
        })
        return self.reconcile(started)

    def add_second_task(self):
        request = self.root / "second.md"
        request.write_text("second independent task\n")
        document = json.loads(self.tasks.read_text())
        document["tasks"].append({"id": "task-two", "title": "Second task", "description": "Second request",
            "completionCriteria": "Second checks pass", "requestFile": str(request),
            "requestHash": hashlib.sha256(request.read_bytes()).hexdigest()})
        self.tasks.write_text(json.dumps(document))

    def assign_second_task(self):
        self.add_second_task()
        document = json.loads(self.tasks.read_text())
        document["tasks"][1].update(workAgentId="work-api", verificationAgentId="verify-api")
        self.tasks.write_text(json.dumps(document))

    def test_task_assignees_preserve_loop_owner_and_revision_sessions(self):
        self.assign_second_task()
        started = self.start()
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        verifying = self.reconcile(started)
        self.runtime.complete_verification("verification-agent", verifying["latestVerificationRunId"], "pass")
        second = self.reconcile(verifying)
        self.assertEqual(second["workAgentId"], "work-agent")
        self.assertEqual(second["currentChild"]["agentId"], "work-api")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "submit")
        self.runtime.complete_work("work-api", second["latestWorkRunId"])
        verifying = self.reconcile(second)
        self.assertEqual(verifying["currentChild"]["agentId"], "verify-api")
        self.assertEqual(self.runtime.dispatches[-1]["verified_work_run_id"], second["latestWorkRunId"])
        self.runtime.complete_verification("verify-api", verifying["latestVerificationRunId"], "fail")
        revision = self.reconcile(verifying)
        self.assertEqual(revision["currentChild"]["agentId"], "work-api")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.runtime.complete_work("work-api", revision["latestWorkRunId"], addressed=["finding-1"])
        verifying = self.reconcile(revision)
        self.runtime.complete_verification("verify-api", verifying["latestVerificationRunId"], "pass")
        ended = self.reconcile(verifying)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual([task["workAgentId"] for task in ended["workflow"]["tasks"]], ["work-agent", "work-api"])
        count = len(self.runtime.dispatches)
        self.reconcile(ended)
        self.assertEqual(len(self.runtime.dispatches), count)

    def test_invalid_assignments_rejected_before_any_dispatch(self):
        self.add_second_task()
        original = json.loads(self.tasks.read_text())
        for key, value in (("workAgentId", "verification-agent"), ("workAgentId", "../bad"),
                           ("verificationAgentId", "work-agent")):
            document = json.loads(json.dumps(original))
            document["tasks"][1][key] = value
            self.tasks.write_text(json.dumps(document))
            with self.subTest(key=key, value=value), self.assertRaises(self.agent_exec.ContractError):
                self.start()
            self.assertEqual(self.runtime.dispatches, [])

    def test_assigned_worker_receipt_recovery_uses_its_session(self):
        self.assign_second_task()
        started = self.start(["--task-mode", "work"])
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        second = self.reconcile(started)
        run = self.runtime.runs[("work-api", second["latestWorkRunId"])]
        run.update(status="failed", error={"code": "receipt_path_contract_invalid", "message": "invalid path"})
        failed = self.reconcile(second)
        recovered = self.recover_receipt(failed)
        self.assertEqual(recovered["currentChild"]["agentId"], "work-api")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.assertEqual(recovered["receiptRecovery"]["failedWorkRunId"], second["latestWorkRunId"])

    def test_assignment_snapshot_tampering_blocks_next_dispatch(self):
        self.assign_second_task()
        started = self.start(["--task-mode", "work"])
        state = json.loads(Path(started["statePath"]).read_text())
        snapshot = Path(state["execution"]["taskListPath"])
        document = json.loads(snapshot.read_text())
        document["tasks"][1]["workAgentId"] = "different-worker"
        snapshot.write_text(json.dumps(document))
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        with self.assertRaises(self.agent_exec.ContractError):
            self.reconcile(started)
        self.assertEqual(len(self.runtime.dispatches), 1)

    def test_automatic_hashes_snapshot_all_tasks_without_rewriting_input(self):
        self.add_second_task()
        first_content = '첫 요청\r\n둘째 줄\n마지막 줄\r\n'.encode('utf-8')
        second_content = '다음 요청\r\n원문 유지\r\n'.encode('utf-8')
        self.request.write_bytes(first_content)
        document = json.loads(self.tasks.read_text())
        Path(document['tasks'][1]['requestFile']).write_bytes(second_content)
        for task in document['tasks']:
            del task['requestHash']
        self.tasks.write_text(json.dumps(document))
        original = self.tasks.read_bytes()
        started = self.start(['--task-mode', 'work'])
        for task, content in zip(started['workflow']['tasks'], (first_content, second_content)):
            snapshot = Path(task['requestPath']).read_bytes()
            self.assertEqual(snapshot, content)
            self.assertEqual(task['requestHash'], hashlib.sha256(snapshot).hexdigest())
        self.assertEqual(self.tasks.read_bytes(), original)
        self.assertEqual(self.request.read_bytes(), first_content)
        first_run = self.runtime.status('work-agent', started['latestWorkRunId'])
        self.assertEqual(first_run['dispatchTuple']['executionOptions'], {
            'taskMode': 'work', 'goalMode': True, 'goalObjective': first_content.decode('utf-8')})
        second = started['workflow']['tasks'][1]
        Path(document['tasks'][1]['requestFile']).write_text('changed after acceptance')
        self.runtime.complete_work('work-agent', started['latestWorkRunId'])
        advanced = self.reconcile(started)
        self.assertEqual(json.loads(Path(advanced['statePath']).read_text())['originalRequestHash'], second['requestHash'])
        self.assertEqual(Path(self.runtime.dispatches[-1]['request_file']).read_bytes(), Path(second['requestPath']).read_bytes())
        second_run = self.runtime.status('work-agent', advanced['latestWorkRunId'])
        self.assertEqual(second_run['dispatchTuple']['executionOptions'], {
            'taskMode': 'work', 'goalMode': True, 'goalObjective': second_content.decode('utf-8')})
        self.assertEqual(Path(second['requestPath']).read_bytes(), second_content)
        self.assertEqual(self.tasks.read_bytes(), original)
        self.assertNotEqual(first_run['runId'], second_run['runId'])
        self.assertEqual([call['operation'] for call in self.runtime.dispatches], ['submit', 'send'])

    def test_normalized_goal_text_is_rejected_even_when_request_hash_matches(self):
        content = '원문 요청\r\n다음 줄\r\n'.encode('utf-8')
        self.request.write_bytes(content)
        original_list = self.tasks.read_bytes()
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start(['--task-mode', 'work'])
        directory = next((self.agent_exec.agent_root(self.root) / 'work-agent' / 'loops').iterdir())
        state = self.agent_exec.safe_read_json(directory / 'state.json')
        pending = state['pendingDispatch']
        run = self.runtime.status_dispatch(pending['agentId'], pending['dispatchId'])
        self.assertEqual(run['dispatchTuple']['requestHash'], hashlib.sha256(content).hexdigest())
        run['dispatchTuple']['executionOptions']['goalObjective'] = content.decode('utf-8').replace('\r\n', '\n')
        with self.assertRaises(self.agent_exec.ContractError) as error:
            self.reconcile({'loopId': state['loopId']})
        self.assertEqual(error.exception.code, 'dispatch_binding_invalid')
        self.assertEqual(len(self.runtime.dispatches), 1, 'A mismatched accepted run must not be redispatched')
        self.assertEqual(self.request.read_bytes(), content)
        self.assertEqual(self.tasks.read_bytes(), original_list)
        retained = self.agent_exec.safe_read_json(directory / 'state.json')
        self.assertEqual(retained['pendingDispatch']['dispatchId'], pending['dispatchId'])

    def test_caller_hashes_do_not_gate_submission(self):
        self.add_second_task()
        document = json.loads(self.tasks.read_text())
        document['tasks'][0]['requestHash'] = 'obsolete'
        document['tasks'][1]['requestHash'] = None
        original = json.dumps(document)
        self.tasks.write_text(original)
        started = self.start(['--task-mode', 'work'])
        state = json.loads(Path(started['statePath']).read_text())
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(self.tasks.read_text(), original)
        for task in state['workflow']['tasks']:
            self.assertEqual(task['requestHash'], hashlib.sha256(Path(task['requestPath']).read_bytes()).hexdigest())
        self.runtime.complete_work('work-agent', started['latestWorkRunId'])
        self.reconcile(started)
        self.assertEqual(len(self.runtime.dispatches), 2)

    def test_entire_list_visible_and_work_only_advances_once(self):
        self.add_second_task()
        started = self.start(["--task-mode", "work"])
        self.assertEqual(len(started["workflow"]["tasks"]), 2)
        self.assertEqual(started["workflow"]["tasks"][1]["workStatus"], "pending")
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        second = self.reconcile(started)
        self.assertEqual(second["workflow"]["index"], 1)
        self.assertEqual(second["workflow"]["tasks"][0]["workStatus"], "completed")
        self.assertEqual(second["workflow"]["tasks"][1]["workStatus"], "running")
        self.reconcile(second)
        self.assertEqual(len(self.runtime.dispatches), 2)
        self.runtime.complete_work("work-agent", second["latestWorkRunId"])
        self.assertEqual(self.reconcile(second)["status"], "completed")

    def test_verification_failure_blocks_next_task_until_pass(self):
        self.add_second_task()
        started = self.start()
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        verifying = self.reconcile(started)
        self.runtime.complete_verification("verification-agent", verifying["latestVerificationRunId"], "fail")
        revision = self.reconcile(verifying)
        self.assertEqual(revision["workflow"]["index"], 0)
        self.assertEqual(revision["workflow"]["tasks"][1]["workStatus"], "pending")
        self.runtime.complete_work("work-agent", revision["latestWorkRunId"], addressed=["finding-1"])
        verifying = self.reconcile(revision)
        self.runtime.complete_verification("verification-agent", verifying["latestVerificationRunId"], "pass")
        second = self.reconcile(verifying)
        self.assertEqual(second["workflow"]["index"], 1)
        self.assertEqual(second["workflow"]["tasks"][0]["verificationStatus"], "completed")
        self.assertEqual([item["role"] for item in self.runtime.dispatches], ["work", "verification", "work", "verification", "work"])

    def six_task_document(self):
        document = json.loads(self.tasks.read_text())
        document["tasks"][0]["requestFile"] = str(self.request)
        for index in range(2, 7):
            request = self.root / f'request-{index}.md'
            request.write_text(f'Bounded task {index}\n')
            document['tasks'].append({'id': f'task-{index}', 'title': f'Task {index}',
                'description': f'Bounded task {index}', 'completionCriteria': f'Task {index} delivered',
                'requestFile': str(request)})
        self.tasks.write_text(json.dumps(document))
        return document

    def test_six_tasks_reuse_session_with_distinct_runs_and_restore_without_duplicate(self):
        document = self.six_task_document()
        contents = []
        for index, task in enumerate(document['tasks'], 1):
            content = f'작업 {index}\r\n원문 유지\n마지막 줄\r\n'.encode('utf-8')
            Path(task['requestFile']).write_bytes(content)
            task.pop('requestHash', None)
            contents.append(content)
        self.tasks.write_text(json.dumps(document))
        original_list = self.tasks.read_bytes()
        snapshot = self.start(['--task-mode', 'work'])
        run_ids = []
        session_ids = set()
        for index in range(6):
            tasks = snapshot['workflow']['tasks']
            self.assertEqual([task['id'] for task in tasks], [task['id'] for task in document['tasks']])
            self.assertEqual([task['workStatus'] for task in tasks],
                ['completed'] * index + ['running'] + ['pending'] * (5 - index))
            run_id = tasks[index]['workRunId']
            run_ids.append(run_id)
            self.assertEqual(tasks[index]['workAgentId'], 'work-agent')
            self.assertEqual(self.runtime.dispatches[-1]['execution']['taskBinding']['taskId'], tasks[index]['id'])
            child = self.runtime.status('work-agent', run_id)
            session_ids.add(child['sessionId'])
            self.assertEqual(child['dispatchTuple']['executionOptions'], {
                'taskMode': 'work', 'goalMode': True,
                'goalObjective': contents[index].decode('utf-8')})
            self.assertEqual(child['dispatchTuple']['requestHash'], hashlib.sha256(contents[index]).hexdigest())
            self.assertEqual(Path(tasks[index]['requestPath']).read_bytes(), contents[index])
            # Every reconcile reloads the persisted snapshot, as a reconnect does.
            restored = self.reconcile(snapshot)
            self.assertEqual(restored['workflow'], snapshot['workflow'])
            self.assertEqual(len(self.runtime.dispatches), index + 1)
            self.runtime.complete_work('work-agent', run_id)
            if index == 2:
                # Lose the fourth task's acknowledgement after acceptance, then
                # recover that exact dispatch with its original Goal text.
                self.runtime.lose_ack = True
                with self.assertRaises(self.agent_exec.ContractError):
                    self.reconcile(snapshot)
                pending = self.agent_exec.safe_read_json(Path(snapshot['statePath']))['pendingDispatch']
                accepted = self.runtime.status_dispatch(pending['agentId'], pending['dispatchId'])
                accepted_tuple = json.loads(json.dumps(accepted['dispatchTuple']))
                snapshot = self.reconcile(snapshot)
                self.assertEqual(snapshot['workflow']['tasks'][3]['workRunId'], accepted['runId'])
                self.assertEqual(accepted['dispatchTuple'], accepted_tuple)
                self.assertIsNone(snapshot['pendingDispatch'])
                self.assertEqual(len(self.runtime.dispatches), 4)
                continue
            snapshot = self.reconcile(snapshot)
        self.assertEqual(len(set(run_ids)), 6)
        self.assertEqual(len(session_ids), 1)
        self.assertEqual(self.tasks.read_bytes(), original_list)
        for task, content in zip(document['tasks'], contents):
            self.assertEqual(Path(task['requestFile']).read_bytes(), content)
        self.assertEqual([task['workRunId'] for task in snapshot['workflow']['tasks']], run_ids)
        self.assertEqual(snapshot['status'], 'completed')
        self.assertEqual([item['operation'] for item in self.runtime.dispatches], ['submit'] + ['send'] * 5)
        self.assertEqual(self.reconcile(snapshot)['workflow'], snapshot['workflow'])
        self.assertEqual(len(self.runtime.dispatches), 6)

    def test_lost_ack_for_second_task_recovers_failed_run_without_dispatching_again(self):
        self.six_task_document()
        started = self.start(['--task-mode', 'work'])
        self.runtime.complete_work('work-agent', started['latestWorkRunId'])
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.reconcile(started)
        state = json.loads(Path(started['statePath']).read_text())
        pending = state['pendingDispatch']
        child = self.runtime.status_dispatch(pending['agentId'], pending['dispatchId'])
        child['status'] = 'failed'
        restored = self.reconcile(started)
        self.assertEqual([task['workStatus'] for task in restored['workflow']['tasks']],
                         ['completed', 'failed'] + ['pending'] * 4)
        self.assertEqual(restored['workflow']['tasks'][1]['workRunId'], child['runId'])
        stopped = self.reconcile(restored)
        self.assertEqual(stopped['status'], 'runtime-error')
        self.assertEqual(len(self.runtime.dispatches), 2)

    def test_readonly_status_projects_blocked_exact_run_without_completing_waiting_tasks(self):
        self.six_task_document()
        started = self.start(['--task-mode', 'work'])
        child = self.runtime.status('work-agent', started['latestWorkRunId'])
        child['status'] = 'needs-human-decision'
        original = Path(started['statePath']).read_bytes()
        args = self.agent_loop.build_parser().parse_args(['status', '--project-root', str(self.root),
            '--work-agent', 'work-agent', '--loop-id', started['loopId']])
        snapshot = self.agent_loop.status_loop(args)
        self.assertEqual([task['workStatus'] for task in snapshot['workflow']['tasks']], ['blocked'] + ['pending'] * 5)
        self.assertEqual(Path(started['statePath']).read_bytes(), original)
        child['status'] = 'completed'
        # Receipt handling has not happened; status alone must not claim completion.
        self.assertEqual(self.agent_loop.status_loop(args)['workflow']['tasks'][0]['workStatus'], 'running')
        self.assertEqual(len(self.runtime.dispatches), 1)

    def test_driver_advances_without_main_or_panel(self):
        self.add_second_task()
        started = self.start(["--task-mode", "work"])
        args = self.agent_loop.build_parser().parse_args(["drive", "--project-root", str(self.root),
            "--work-agent", "work-agent", "--loop-id", started["loopId"]])
        def complete_active(_seconds):
            state = json.loads(Path(started["statePath"]).read_text())
            self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        with mock.patch.object(self.agent_loop.time, "sleep", side_effect=complete_active):
            ended = self.agent_loop.drive_loop(args)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual(len(self.runtime.dispatches), 2)

    def test_driver_stops_and_preserves_error_without_retry(self):
        started = self.start()
        args = self.agent_loop.build_parser().parse_args(["drive", "--project-root", str(self.root),
            "--work-agent", "work-agent", "--loop-id", started["loopId"]])
        with mock.patch.object(self.agent_loop, "reconcile_loop", side_effect=self.agent_exec.ContractError("test_failure", "stop here")) as reconcile:
            ended = self.agent_loop.drive_loop(args)
        self.assertEqual(reconcile.call_count, 1)
        self.assertEqual(ended["status"], "runtime-error")
        self.assertEqual(ended["workflow"]["tasks"][0]["workStatus"], "blocked")
        self.assertEqual(ended["controlPlaneError"]["code"], "test_failure")

    def test_all_requests_validated_before_any_dispatch(self):
        self.add_second_task()
        (self.root / "second.md").write_text("")
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        self.assertEqual(self.runtime.dispatches, [])

    def test_work_mode_completes_without_verification_or_human_skip(self):
        started = self.start(["--task-mode", "work"])
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        ended = self.reconcile(started)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual(ended["terminalReason"]["code"], "work-completed")
        self.assertIsNone(ended["humanSkip"])
        self.assertIsNone(ended["latestVerificationRunId"])
        self.assertEqual([item["role"] for item in self.runtime.dispatches], ["work"])

    def test_plan_work_needs_no_verification_identity_and_completes(self):
        args = self.agent_loop.build_parser().parse_args([
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--task-list-file", str(self.tasks), "--task-id", "task-one",
            "--work-agent", "work-agent", "--task-mode", "plan-work", "--codex", "/bin/true",
        ])
        started = self.agent_loop.start_loop(args)
        work = self.runtime.runs[("work-agent", started["latestWorkRunId"])]
        self.assertEqual(work["dispatchTuple"]["executionOptions"]["taskMode"], "plan-work")
        self.runtime.complete_work("work-agent", work["runId"])
        ended = self.reconcile(started)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual(ended["terminalReason"]["code"], "work-completed")
        self.assertIsNone(ended["humanSkip"])
        self.assertIsNone(ended["latestVerificationRunId"])
        self.assertEqual([item["role"] for item in self.runtime.dispatches], ["work"])

    def test_plan_work_rejects_verification_dispatch_and_skip(self):
        started = self.start(["--task-mode", "plan-work"])
        path = Path(started["statePath"])
        state = self.agent_exec.safe_read_json(path)
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.prepare_dispatch(state, path, role="verification", request_file=self.request)
        self.assertEqual(raised.exception.code, "graph_transition_invalid")
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", started["loopId"], "--actor", "human",
            "--authorization-reference", "explicit-input", "--decision-evidence", "skip",
        ])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.skip_loop(args)
        self.assertEqual(raised.exception.code, "verification_not_requested")

    def test_plan_work_noncompleted_child_never_finishes_or_dispatches_verification(self):
        for status in ("failed", "cancelled", "needs-human-decision"):
            with self.subTest(status=status):
                started = self.start(["--task-mode", "plan-work"])
                self.runtime.runs[("work-agent", started["latestWorkRunId"])]["status"] = status
                ended = self.reconcile(started)
                self.assertEqual(ended["status"], "runtime-error")
                self.assertIsNone(ended["latestVerificationRunId"])
                self.assertTrue(all(item["role"] == "work" for item in self.runtime.dispatches))

    def test_plan_mode_is_bound_to_work_dispatch_and_not_verification(self):
        started = self.start(["--task-mode", "plan-work-verification"])
        work = self.runtime.runs[("work-agent", started["latestWorkRunId"])]
        self.assertEqual(work["dispatchTuple"]["executionOptions"]["taskMode"], "plan-work-verification")
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        checking = self.reconcile(started)
        verification = self.runtime.runs[("verification-agent", checking["latestVerificationRunId"])]
        self.assertNotIn("taskMode", verification["dispatchTuple"].get("executionOptions", {}))
        self.assertEqual(verification["verifiedWorkRunId"], work["runId"])

    def test_plan_mode_failure_reuses_both_sessions(self):
        state = self.start(["--task-mode", "plan-work-verification"])
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        first_verification = state["latestVerificationRunId"]
        self.runtime.complete_verification("verification-agent", first_verification, "fail")
        state = self.reconcile(state)
        revision = self.runtime.runs[("work-agent", state["latestWorkRunId"])]
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.assertEqual(revision["dispatchTuple"]["executionOptions"]["taskMode"], "plan-work-verification")
        self.runtime.complete_work("work-agent", state["latestWorkRunId"], ["finding-1"])
        state = self.reconcile(state)
        self.assertEqual(self.runtime.dispatches[-1]["agent_id"], "verification-agent")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.assertNotEqual(state["latestVerificationRunId"], first_verification)
        self.runtime.complete_verification("verification-agent", state["latestVerificationRunId"], "pass")
        self.assertEqual(self.reconcile(state)["status"], "completed")

    def test_historical_loop_without_mode_retains_verification_route(self):
        started = self.start()
        path = Path(started["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["execution"].pop("taskMode")
        self.agent_exec.atomic_write_json(path, stored)
        self.runtime.complete_work("work-agent", started["latestWorkRunId"])
        checking = self.reconcile(started)
        self.assertEqual(checking["taskMode"], "work-verification")
        self.assertEqual(self.runtime.dispatches[-1]["role"], "verification")

    def test_start_rejects_unsafe_request_paths_before_dispatch(self) -> None:
        final_link = self.root / "linked.md"
        final_link.symlink_to(self.request)
        parent_link = self.root / "linked-parent"
        parent_link.symlink_to(self.root, target_is_directory=True)
        source = self.root / "source"
        source.mkdir()
        for path in (final_link, parent_link / "request.md",
                     source / ".." / "request.md"):
            with self.subTest(path=path):
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.start(["--request-file", str(path)])
                self.assertEqual(raised.exception.code, "capability_binding_invalid")
                self.assertEqual(self.runtime.dispatches, [])

    def test_start_preserves_valid_absolute_and_relative_request_bytes(self) -> None:
        for path in (self.request, Path("request.md")):
            with self.subTest(path=path), mock.patch("pathlib.Path.cwd", return_value=self.root):
                started = self.start(["--request-file", str(path)])
                state = self.agent_exec.safe_read_json(Path(started["statePath"]))
                self.assertEqual(Path(state["originalRequestPath"]).read_bytes(), b"bounded work\n")
                self.assertEqual(state["originalRequestHash"], hashlib.sha256(b"bounded work\n").hexdigest())
                self.assertEqual(self.runtime.dispatches[-1]["role"], "work")

    def test_legacy_execution_upgrade_binds_current_authority_without_rewriting_child(self) -> None:
        started = self.start()
        path = Path(started["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        child_before = dict(self.runtime.runs[(started["currentChild"]["agentId"], started["currentChild"]["runId"])])
        stored["execution"] = {"codex": "/bin/true", "sandbox": "danger-full-access", "model": None}
        self.agent_exec.atomic_write_json(path, stored)
        self.reconcile(started)
        execution = self.agent_exec.safe_read_json(path)["execution"]
        self.assertEqual(execution["executionPolicy"], runtime_test_home.policy("danger-full-access"))
        self.assertEqual(self.agent_exec.safe_read_json(Path(execution["executionPolicyPath"])), execution["executionPolicy"])
        self.assertEqual(self.runtime.runs[(started["currentChild"]["agentId"], started["currentChild"]["runId"])], child_before)

    def test_legacy_execution_upgrade_fails_without_mutating_state_on_invalid_authority(self) -> None:
        started = self.start()
        path = Path(started["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["execution"] = {"codex": "/bin/true", "sandbox": "danger-full-access", "model": None}
        self.agent_exec.atomic_write_json(path, stored)
        before = path.read_bytes()
        with mock.patch.dict(self.agent_exec.os.environ, {"AGENT_FACTORY_EXECUTION_POLICY": "invalid"}):
            with self.assertRaises(self.agent_exec.ContractError) as raised:
                self.reconcile(started)
        self.assertEqual(raised.exception.code, "execution_policy_invalid")
        self.assertEqual(path.read_bytes(), before)

    def test_role_profiles_bind_through_work_verification_revision_loop(self):
        state = self.start(["--work-model", "worker", "--work-reasoning-effort", "high",
                            "--verification-model", "reviewer", "--verification-reasoning-effort", "low"])
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.runtime.complete_verification("verification-agent", state["latestVerificationRunId"], "fail")
        state = self.reconcile(state)
        self.runtime.complete_work("work-agent", state["latestWorkRunId"], ["finding-1"])
        state = self.reconcile(state)
        self.runtime.complete_verification("verification-agent", state["latestVerificationRunId"], "pass")
        state = self.reconcile(state)
        self.assertEqual(state["status"], "completed")
        for run in self.runtime.runs.values():
            expected = ("worker", "high") if run["role"] == "work" else ("reviewer", "low")
            options = run["dispatchTuple"]["executionOptions"]
            self.assertEqual((options["model"], options["reasoningEffort"]), expected)

    def test_complete_graph_reuses_work_and_verification_sessions(self) -> None:
        state = self.start()
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        first_verification = state["latestVerificationRunId"]
        self.runtime.complete_verification("verification-agent", first_verification, "fail")
        state = self.reconcile(state)
        revised_work = state["latestWorkRunId"]
        self.assertEqual(self.runtime.dispatches[-1]["agent_id"], "work-agent")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.runtime.complete_work("work-agent", revised_work, ["finding-1"])
        state = self.reconcile(state)
        second_verification = state["latestVerificationRunId"]
        self.assertNotEqual(first_verification, second_verification)
        self.assertEqual(self.runtime.dispatches[-1]["agent_id"], "verification-agent")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.runtime.complete_verification("verification-agent", second_verification, "pass")
        state = self.reconcile(state)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["terminalReason"]["code"], "pass")

    def test_loop_preserves_capability_binding_for_child_dispatch(self) -> None:
        binding = self.root / "binding.json"
        binding.write_text(json.dumps({
            "schemaVersion": "0.1.0",
            "bindings": [{
                "capabilityId": "git.cli.inspect",
                "authority": {"kind": "native-executable", "reference": "executable:git"},
                "invocationRoute": "git",
                "exactTarget": str(self.root),
                "allowedEffects": [],
                "allowedScopes": ["repository:read"],
                "approvalReference": None,
            }],
        }), encoding="utf-8")
        args = self.agent_loop.build_parser().parse_args([
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--task-list-file", str(self.tasks), "--task-id", "task-one",
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true", "--work-capability-binding-file", str(binding),
        ])
        state = self.agent_loop.start_loop(args)
        dispatched = self.runtime.dispatches[-1]["capability_binding_file"]
        self.assertIsNotNone(dispatched)
        self.assertEqual(Path(dispatched).parent.name, state["loopId"])

    def test_loop_start_rejects_symlinked_capability_binding(self) -> None:
        binding = self.root / "binding.json"
        binding.write_text("{}", encoding="utf-8")
        linked = self.root / "binding-link.json"
        linked.symlink_to(binding)
        args = self.agent_loop.build_parser().parse_args([
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--task-list-file", str(self.tasks), "--task-id", "task-one",
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true", "--work-capability-binding-file", str(linked),
        ])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.start_loop(args)
        self.assertEqual(raised.exception.code, "capability_binding_invalid")

    def test_human_skip_records_evidence_and_never_dispatches_verification(self) -> None:
        state = self.start()
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", state["loopId"], "--actor", "human",
            "--authorization-reference", "human-message-7", "--decision-evidence", "skip verification",
        ])
        state = self.agent_loop.skip_loop(args)
        self.assertEqual(state["status"], "active")
        self.assertIsNone(state["terminalReason"])
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.assertEqual(state["terminalReason"]["code"], "human-skip")
        self.assertEqual(state["humanSkip"]["authorizationReference"], "human-message-7")
        self.assertEqual([call["role"] for call in self.runtime.dispatches], ["work"])

    def test_human_skip_after_revision_starts_no_additional_verification(self) -> None:
        state = self.start()
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.runtime.complete_verification(
            "verification-agent", state["latestVerificationRunId"], "fail"
        )
        state = self.reconcile(state)
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", state["loopId"], "--actor", "human",
            "--authorization-reference", "human-message-8",
            "--decision-evidence", "skip additional verification",
        ])
        state = self.agent_loop.skip_loop(args)
        self.assertEqual(state["status"], "active")
        self.assertIsNone(state["terminalReason"])
        self.runtime.complete_work(
            "work-agent", state["latestWorkRunId"], ["finding-1"]
        )
        state = self.reconcile(state)
        self.assertEqual(state["terminalReason"]["code"], "human-skip")
        self.assertEqual(
            [call["role"] for call in self.runtime.dispatches],
            ["work", "verification", "work"],
        )

    def test_non_human_skip_is_rejected(self) -> None:
        state = self.start()
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", state["loopId"], "--actor", "main",
            "--authorization-reference", "main-claim", "--decision-evidence", "skip",
        ])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.skip_loop(args)
        self.assertEqual(raised.exception.code, "human_skip_unauthorized")

    def test_skip_missing_decision_evidence_is_rejected(self) -> None:
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.build_parser().parse_args([
                "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
                "--loop-id", "loop-one", "--actor", "human",
                "--authorization-reference", "human-message-7",
            ])
        self.assertEqual(raised.exception.code, "invalid_arguments")

    def test_ack_loss_recovers_same_dispatch_without_duplicate(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        loops = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        state = self.agent_exec.safe_read_json(loops / "state.json")
        dispatch_id = state["pendingDispatch"]["dispatchId"]
        state = self.reconcile({"loopId": state["loopId"]})
        self.reconcile(state)
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(self.runtime.runs[("work-agent", state["latestWorkRunId"])]["dispatchId"], dispatch_id)

    def test_dispatch_binds_required_human_approval_policy(self) -> None:
        state = self.start()
        dispatched = self.runtime.dispatches[-1]
        run = self.runtime.runs[("work-agent", state["latestWorkRunId"])]
        self.assertEqual(dispatched["human_approval_policy"], "required")
        self.assertEqual(run["dispatchTuple"]["humanApprovalPolicy"], "required")

    def test_role_permissions_survive_verification_and_revision(self) -> None:
        state = self.start(["--work-execution-mode", "bypass",
                            "--verification-execution-mode", "workspace-write",
                            "--work-model", "gpt-5.6-sol", "--verification-model", "gpt-5.6-sol"])
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.runtime.complete_verification("verification-agent", state["latestVerificationRunId"], "fail")
        state = self.reconcile(state)
        self.runtime.complete_work("work-agent", state["latestWorkRunId"], ["finding-1"])
        state = self.reconcile(state)
        self.runtime.complete_verification("verification-agent", state["latestVerificationRunId"], "pass")
        state = self.reconcile(state)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(self.runtime.dispatches), 4)
        for run in self.runtime.runs.values():
            binding = run["dispatchTuple"]
            self.assertEqual(binding["humanApprovalPolicy"], "bypass" if run["role"] == "work" else "required")
            self.assertEqual(binding["executionOptions"]["model"], "gpt-5.6-sol")

    def test_bypass_pending_ack_is_recovered_without_redispatch(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start(["--work-execution-mode", "bypass"])
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        recovered = self.reconcile({"loopId": stored["loopId"]})
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(recovered["currentChild"]["runId"], child["runId"])

    def test_parent_linked_pending_ack_recovers_without_redispatch(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start(["--task-mode", "work", "--work-execution-mode", "bypass",
                        "--work-model", "gpt-5.6-sol"])
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        parent = {"parentAgentId": "main-original", "parentRunId": "run-original"}
        child.update(parent)
        child["dispatchTuple"].update(parent)
        public = self.agent_exec.public_state(child)
        self.assertEqual({key: public[key] for key in parent}, parent)
        self.runtime.runs[("work-agent", child["runId"])] = public
        # Adoption must use persisted provenance, independent of this caller.
        with mock.patch.object(self.agent_exec, "managed_parent_identity", return_value={"agentId": "main-other", "runId": "run-other"}):
            recovered = self.reconcile(stored)
        self.assertEqual(recovered["currentChild"]["runId"], child["runId"])
        self.runtime.complete_work("work-agent", child["runId"])
        ended = self.reconcile(recovered)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual(len(self.runtime.dispatches), 1)

    def test_parent_linkage_mismatch_is_rejected(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        child.update(parentAgentId="main-original", parentRunId="run-original")
        for parent in ({"parentAgentId": "main-other", "parentRunId": "run-original"},
                       {"parentAgentId": "main-original"},
                       {"parentAgentId": "main-original", "parentRunId": "../invalid"}):
            with self.subTest(parent=parent):
                child["dispatchTuple"].pop("parentRunId", None)
                child["dispatchTuple"].update(parent)
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.reconcile(stored)
                self.assertEqual(raised.exception.code, "dispatch_binding_invalid")
        self.assertEqual(len(self.runtime.dispatches), 1)

    def test_legacy_pending_ack_without_human_approval_policy_is_adopted(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        child["dispatchTuple"].pop("humanApprovalPolicy")

        recovered = self.reconcile({"loopId": stored["loopId"]})

        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(recovered["currentChild"]["runId"], child["runId"])

    def test_pending_ack_rejects_bypass_human_approval_policy(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        child["dispatchTuple"]["humanApprovalPolicy"] = "bypass"

        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.reconcile({"loopId": stored["loopId"]})

        self.assertEqual(raised.exception.code, "dispatch_binding_invalid")
        persisted = self.agent_exec.safe_read_json(directory / "state.json")
        self.assertEqual(persisted["pendingDispatch"]["dispatchId"], child["dispatchId"])

    def legacy_pending_ack_fixture(self):
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        path = directory / "state.json"
        stored = self.agent_exec.safe_read_json(path)
        stored["execution"] = {"codex": "/bin/true", "sandbox": "danger-full-access", "model": None}
        # Both sides must predate the Goal contract. Keeping the modern pending
        # marker while removing the child's Goal options is a real mismatch.
        stored["pendingDispatch"].pop("workGoal")
        stored.pop("workflow")
        child = next(iter(self.runtime.runs.values()))
        child["dispatchTuple"].pop("executionPolicy")
        # Historical loop and child fixtures must both predate task-mode options.
        child["dispatchTuple"].pop("executionOptions")
        child["dispatchTuple"].pop("taskBinding")
        self.agent_exec.atomic_write_json(Path(child["statePath"]), child)
        self.agent_exec.atomic_write_json(path, stored)
        return path, stored, child

    def test_legacy_pending_ack_recovers_original_tuple_without_redispatch(self) -> None:
        path, stored, child = self.legacy_pending_ack_fixture()
        original_tuple = dict(child["dispatchTuple"])
        original_child = Path(child["statePath"]).read_bytes()
        dispatch_id = stored["pendingDispatch"]["dispatchId"]
        request = Path(stored["pendingDispatch"]["requestPath"]).read_bytes()
        recovered = self.reconcile({"loopId": stored["loopId"]})
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(child["dispatchTuple"], original_tuple)
        self.assertEqual(child["dispatchId"], dispatch_id)
        self.assertEqual(Path(child["statePath"]).read_bytes(), original_child)
        self.assertEqual(Path(stored["pendingDispatch"]["requestPath"]).read_bytes(), request)
        self.assertNotIn("executionOptions", child["dispatchTuple"])
        self.assertEqual(recovered["currentChild"]["runId"], child["runId"])
        self.assertEqual(recovered["currentChild"]["agentId"], child["agentId"])
        self.assertIsNone(recovered["pendingDispatch"])
        restored = self.reconcile(recovered)
        self.assertEqual(restored["currentChild"], recovered["currentChild"])
        self.assertEqual(len(self.runtime.dispatches), 1)

    def test_goal_marked_pending_cannot_accept_a_pre_goal_child(self):
        path, stored, child = self.legacy_pending_ack_fixture()
        stored["pendingDispatch"]["workGoal"] = True
        self.agent_exec.atomic_write_json(path, stored)
        original_child = Path(child["statePath"]).read_bytes()
        with self.assertRaises(self.agent_exec.ContractError) as error:
            self.reconcile({"loopId": stored["loopId"]})
        self.assertEqual(error.exception.code, "dispatch_binding_invalid")
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(Path(child["statePath"]).read_bytes(), original_child)
        self.assertTrue(self.agent_exec.safe_read_json(path)["pendingDispatch"]["workGoal"])

    def test_legacy_pending_ack_still_rejects_tampered_identity_and_options(self):
        path, stored, child = self.legacy_pending_ack_fixture()
        original = json.loads(json.dumps(child))
        for field, value in (("dispatchId", "dispatch-wrong"), ("agentId", "other-worker"),
                             ("requestHash", "0" * 64), ("executionOptions", {"goalMode": True})):
            child.clear()
            child.update(json.loads(json.dumps(original)))
            if field == "dispatchId":
                child[field] = value
            else:
                child["dispatchTuple"][field] = value
            # Model a corrupted response to the exact dispatch lookup, not a new request.
            with self.subTest(field=field), mock.patch.object(self.runtime, "status_dispatch", return_value=child):
                with self.assertRaises(self.agent_exec.ContractError) as error:
                    self.reconcile({"loopId": stored["loopId"]})
                self.assertEqual(error.exception.code, "dispatch_binding_invalid")
                self.assertEqual(len(self.runtime.dispatches), 1)
                retained = self.agent_exec.safe_read_json(path)
                self.assertEqual(retained["pendingDispatch"]["dispatchId"], stored["pendingDispatch"]["dispatchId"])
                self.assertIsNone(retained["currentChild"])

    def test_crash_before_call_reuses_durable_dispatch_id(self) -> None:
        self.runtime.fail_before_call = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        loops = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        persisted = self.agent_exec.safe_read_json(loops / "state.json")
        dispatch_id = persisted["pendingDispatch"]["dispatchId"]
        self.runtime.fail_before_call = False
        state = self.reconcile({"loopId": persisted["loopId"]})
        self.assertEqual(self.runtime.dispatches[0]["dispatch_id"], dispatch_id)
        self.assertIsNone(state["pendingDispatch"])

    def test_outside_graph_role_is_rejected(self) -> None:
        state = self.start()
        path = Path(state["statePath"])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.prepare_dispatch(state, path, role="review", request_file=self.request)
        self.assertEqual(raised.exception.code, "graph_role_invalid")

    def test_outside_graph_transition_is_rejected(self) -> None:
        state = self.start()
        path = Path(state["statePath"])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.prepare_dispatch(
                state, path, role="verification", request_file=self.request,
                verified_work_run_id="run-not-latest",
            )
        self.assertEqual(raised.exception.code, "graph_transition_invalid")

    def test_child_failure_is_control_plane_error_not_graph_end(self) -> None:
        state = self.start()
        self.runtime.runs[("work-agent", state["latestWorkRunId"])]["status"] = "failed"
        state = self.reconcile(state)
        self.assertEqual(state["status"], "runtime-error")
        self.assertEqual(state["phase"], "control-plane-error")
        self.assertIsNone(state["terminalReason"])

    def test_receipt_recovery_preserves_failed_run_and_reaches_verification(self) -> None:
        state = self.start()
        failed_run_id = state["latestWorkRunId"]
        failed = dict(self.runtime.runs[("work-agent", failed_run_id)])
        state = self.fail_work_receipt(state)

        state = self.recover_receipt(state)
        recovery_run_id = state["latestWorkRunId"]
        self.assertNotEqual(recovery_run_id, failed_run_id)
        self.assertEqual(self.runtime.runs[("work-agent", failed_run_id)], {
            **failed,
            "status": "failed",
            "error": {
                "code": "receipt_path_contract_invalid",
                "message": "changedPaths must contain only project-root-relative paths",
            },
        })
        recovery = state["receiptRecovery"]
        self.assertEqual(recovery["failedWorkRunId"], failed_run_id)
        self.assertEqual(recovery["recoveryWorkRunId"], recovery_run_id)
        dispatched = self.runtime.dispatches[-1]
        self.assertEqual(dispatched["operation"], "send")
        stored = self.agent_exec.safe_read_json(Path(state["statePath"]))
        self.assertEqual(dispatched["request_hash"], stored["originalRequestHash"])
        self.assertEqual(dispatched["execution"]["executionPolicy"], stored["execution"]["executionPolicy"])
        recovery_request = Path(recovery["requestPath"]).read_text(encoding="utf-8")
        self.assertIn("Do not repeat any already performed tool effect", recovery_request)
        self.assertIn(f"Failed Work run: {failed_run_id}", recovery_request)

        self.runtime.complete_work("work-agent", recovery_run_id)
        state = self.reconcile(state)
        self.assertEqual(state["currentChild"]["role"], "verification")
        verification = self.runtime.runs[("verification-agent", state["latestVerificationRunId"])]
        self.assertEqual(verification["verifiedWorkRunId"], recovery_run_id)
        dispatch_count = len(self.runtime.dispatches)
        repeated = self.recover_receipt(state)
        self.assertEqual(repeated["latestVerificationRunId"], state["latestVerificationRunId"])
        self.assertEqual(len(self.runtime.dispatches), dispatch_count)

    def test_receipt_recovery_preserves_valid_capability_evidence(self) -> None:
        binding = self.root / "binding.json"
        binding.write_text(json.dumps({
            "schemaVersion": "0.1.0",
            "bindings": [{
                "capabilityId": "git.cli.inspect",
                "authority": {"kind": "native-executable", "reference": "executable:git"},
                "invocationRoute": "git", "exactTarget": str(self.root),
                "allowedEffects": [], "allowedScopes": ["repository:read"],
                "approvalReference": None,
            }],
        }), encoding="utf-8")
        state = self.fail_work_receipt(self.start([
            "--work-capability-binding-file", str(binding),
        ]))
        recovered = self.recover_receipt(state)
        stored = self.agent_exec.safe_read_json(Path(recovered["statePath"]))
        self.assertEqual(
            str(self.runtime.dispatches[-1]["capability_binding_file"]),
            stored["capabilityBindings"]["work"]["path"],
        )
        recovery_run = self.runtime.runs[("work-agent", recovered["latestWorkRunId"])]
        request = self.agent_loop.verification_request(
            stored, recovery_run, Path(recovered["statePath"]).parent
        ).read_text(encoding="utf-8")
        self.assertIn(stored["receiptRecovery"]["failedReceiptPath"], request)

    def test_receipt_recovery_preserves_revision_findings(self) -> None:
        state = self.start()
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.runtime.complete_verification(
            "verification-agent", state["latestVerificationRunId"], "fail"
        )
        state = self.reconcile(state)
        state = self.fail_work_receipt(state)

        recovered = self.recover_receipt(state)
        request = Path(recovered["receiptRecovery"]["requestPath"]).read_text(encoding="utf-8")
        self.assertIn('Required addressed finding IDs: ["finding-1"]', request)
        self.runtime.complete_work(
            "work-agent", recovered["latestWorkRunId"], ["finding-1"]
        )
        reconciled = self.reconcile(recovered)
        self.assertEqual(reconciled["currentChild"]["role"], "verification")

    def test_receipt_recovery_reuses_durable_dispatch_after_ack_loss(self) -> None:
        state = self.fail_work_receipt(self.start())
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.recover_receipt(state)
        dispatch_count = len(self.runtime.dispatches)
        stored = self.agent_exec.safe_read_json(Path(state["statePath"]))
        dispatch_id = stored["pendingDispatch"]["dispatchId"]

        recovered = self.recover_receipt(stored)
        self.assertEqual(len(self.runtime.dispatches), dispatch_count)
        self.assertEqual(
            self.runtime.runs[("work-agent", recovered["latestWorkRunId"])]["dispatchId"],
            dispatch_id,
        )

    def test_legacy_changed_path_error_remains_recoverable_without_capabilities(self) -> None:
        state = self.fail_work_receipt(
            self.start(), "receipt_invalid", "changedPaths must be bounded relative paths"
        )
        failed_run_id = state["latestWorkRunId"]
        recovered = self.recover_receipt(state)
        self.assertEqual(recovered["receiptRecovery"]["failedWorkRunId"], failed_run_id)

    def test_receipt_recovery_fails_closed_for_active_unsafe_or_wrong_session(self) -> None:
        active = self.start()
        with self.assertRaises(self.agent_exec.ContractError) as unavailable:
            self.recover_receipt(active)
        self.assertEqual(unavailable.exception.code, "receipt_recovery_unavailable")

        unsafe = self.fail_work_receipt(active, "sandbox_unavailable")
        with self.assertRaises(self.agent_exec.ContractError) as rejected:
            self.recover_receipt(unsafe)
        self.assertEqual(rejected.exception.code, "receipt_recovery_unsafe")

        receipt_error = {
            "code": "receipt_path_contract_invalid",
            "message": "changedPaths must contain only project-root-relative paths",
        }
        run = self.runtime.runs[("work-agent", unsafe["latestWorkRunId"])]
        run["error"] = receipt_error
        path = Path(unsafe["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["controlPlaneError"] = receipt_error
        self.agent_exec.atomic_write_json(path, stored)
        session_path = self.agent_exec.session_file(self.root, "work-agent")
        session = self.agent_exec.safe_read_json(session_path)
        session["sessionId"] = "different-session"
        self.agent_exec.atomic_write_json(session_path, session)
        with self.assertRaises(self.agent_exec.ContractError) as mismatch:
            self.recover_receipt(stored)
        self.assertEqual(mismatch.exception.code, "receipt_recovery_session_invalid")

    def test_receipt_recovery_rejects_test_and_capability_evidence_failures(self) -> None:
        state = self.fail_work_receipt(
            self.start(), "receipt_tests_invalid", "Work receipt must prove Work ran no tests"
        )
        with self.assertRaises(self.agent_exec.ContractError) as tests_error:
            self.recover_receipt(state)
        self.assertEqual(tests_error.exception.code, "receipt_recovery_unsafe")

        failed_run = self.runtime.runs[("work-agent", state["latestWorkRunId"])]
        capability_error = {
            "code": "receipt_capability_invalid",
            "message": "capability outcome binding is invalid",
        }
        failed_run["error"] = capability_error
        path = Path(state["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["controlPlaneError"] = capability_error
        self.agent_exec.atomic_write_json(path, stored)
        before = dict(failed_run)
        with self.assertRaises(self.agent_exec.ContractError) as capability:
            self.recover_receipt(stored)
        self.assertEqual(capability.exception.code, "receipt_recovery_unsafe")
        self.assertEqual(failed_run, before)

    def test_rejected_legacy_recovery_does_not_publish_policy_or_change_bytes(self) -> None:
        state = self.start()
        path = Path(state["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        self.assertTrue((path.parent / ".loop.lock").is_file())
        policy_path = Path(stored["execution"]["executionPolicyPath"])
        policy_path.unlink()
        stored["execution"] = {
            "codex": "/bin/true", "sandbox": "danger-full-access", "model": None,
        }
        self.agent_exec.atomic_write_json(path, stored)
        directory = path.parent
        before_files = {
            item.relative_to(directory): item.read_bytes()
            for item in directory.rglob("*") if item.is_file()
        }
        before_directories = {
            item.relative_to(directory) for item in directory.rglob("*") if item.is_dir()
        }

        with self.assertRaises(self.agent_exec.ContractError) as rejected:
            self.recover_receipt(stored)
        self.assertEqual(rejected.exception.code, "receipt_recovery_unavailable")
        self.assertEqual(before_files, {
            item.relative_to(directory): item.read_bytes()
            for item in directory.rglob("*") if item.is_file()
        })
        self.assertEqual(before_directories, {
            item.relative_to(directory) for item in directory.rglob("*") if item.is_dir()
        })


if __name__ == "__main__":
    unittest.main()

class RoleModelDispatchTests(unittest.TestCase):
    def test_role_flags_are_sent_on_initial_and_revision_turns(self):
        _, loop = load_modules()
        runtime = object.__new__(loop.AgentRuntime)
        runtime.call = mock.Mock(return_value={"status": "accepted"})
        execution = {"codex": "/bin/true", "taskMode": "plan-work-verification", "agentModels": {
            "work": {"model": "work-model", "reasoningEffort": "high"},
            "verification": {"model": "verify-model", "reasoningEffort": "low"}}}
        for operation in ("submit", "send"):
            for role, model, effort in (("work", "work-model", "high"), ("verification", "verify-model", "low")):
                runtime.dispatch(operation=operation, agent_id=role, role=role,
                    request_file=Path("/tmp/role-request.md"), request_hash="0" * 64,
                    dispatch_id="dispatch-role", verified_work_run_id=None,
                    execution=execution, capability_binding_file=None, human_approval_policy="required")
                args = runtime.call.call_args.args[0]
                self.assertEqual(args[args.index("--model") + 1], model)
                self.assertEqual(args[args.index("--reasoning-effort") + 1], effort)
                self.assertEqual(loop.role_model_options(execution, role, operation), execution["agentModels"][role])
                self.assertEqual("--task-mode" in args, role == "work")

    def test_role_flags_parse_and_legacy_shared_model_stays_submit_only(self):
        _, loop = load_modules()
        args = loop.build_parser().parse_args(["start", "--task-list-file", "/tmp/tasks.json", "--task-id", "task-one", "--request-file", "/tmp/request.md", "--work-agent", "work-one",
            "--work-model", "worker", "--work-reasoning-effort", "high", "--verification-model", "reviewer", "--verification-reasoning-effort", "low"])
        self.assertEqual(args.work_model, "worker")
        self.assertEqual(args.verification_reasoning_effort, "low")
        self.assertEqual(loop.role_model_options({"model": "legacy"}, "work", "submit"), {"model": "legacy"})
        self.assertEqual(loop.role_model_options({"model": "legacy"}, "work", "send"), {})

class RolePermissionDispatchTests(unittest.TestCase):
    def test_role_policy_is_preserved_on_submit_and_revision(self):
        exec_module, loop = load_modules()
        runtime = object.__new__(loop.AgentRuntime)
        runtime.call = mock.Mock(return_value={"status": "accepted"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            profiles = {}
            for role, mode in (("work", "bypass"), ("verification", "workspace-write")):
                policy = exec_module.execution_policy.role_policy(mode, None, root)
                path = root / (role + '.json')
                path.write_text(json.dumps(policy))
                profiles[role] = {"policy": policy, "path": str(path), "humanApprovalPolicy": "bypass" if mode == "bypass" else "required"}
            for operation in ("submit", "send"):
                for role in profiles:
                    runtime.dispatch(operation=operation, agent_id=role, role=role,
                        request_file=root / 'request.md', request_hash='0' * 64,
                        dispatch_id='dispatch', verified_work_run_id=None,
                        execution={"codex": '/bin/true', "agentPermissions": profiles},
                        capability_binding_file=None, human_approval_policy='required')
                    args = runtime.call.call_args.args[0]
                    self.assertEqual(args[args.index('--execution-policy-file') + 1], profiles[role]['path'])
                    self.assertEqual(args[args.index('--human-approval-policy') + 1], profiles[role]['humanApprovalPolicy'])
            Path(profiles['work']['path']).write_text('{}')
            with self.assertRaises(exec_module.ContractError):
                runtime.dispatch(operation='send', agent_id='work', role='work', request_file=root / 'request.md', request_hash='0' * 64,
                    dispatch_id='dispatch', verified_work_run_id=None, execution={"codex": '/bin/true', "agentPermissions": profiles},
                    capability_binding_file=None, human_approval_policy='required')

    def test_permission_snapshot_is_validated_and_cannot_be_minted_by_child(self):
        import argparse
        import os
        exec_module, _ = load_modules()
        with mock.patch.dict(os.environ, {}, clear=True):
            options = exec_module.requested_execution(argparse.Namespace(agent_permissions='{"work":"workspace-write"}'))
            self.assertEqual(options["agentPermissions"], {"work": "workspace-write"})
            for value in ('[]', '{"bad":"bypass"}', '{"work":"root"}'):
                with self.assertRaises(exec_module.ContractError):
                    exec_module.requested_execution(argparse.Namespace(agent_permissions=value))
            os.environ[exec_module.execution_policy.PARENT_STATE_ENV] = '/tmp/parent-state.json'
            with self.assertRaises(exec_module.ContractError):
                exec_module.requested_execution(argparse.Namespace(agent_permissions='{"work":"bypass"}'))
