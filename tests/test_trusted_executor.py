from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "agent" / "scripts" / "trusted_executor.py"
FIXTURE_SCRIPT = SCRIPT.with_name("trusted_executor_fixture.py")
WORKFLOW = SCRIPT.parents[3] / ".github" / "workflows" / "trusted-executor.yml"


def load_module():
    spec = importlib.util.spec_from_file_location("trusted_executor_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load trusted executor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_fixture_module():
    spec = importlib.util.spec_from_file_location("trusted_executor_fixture_test", FIXTURE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load trusted executor fixture")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"trusted_executor": load_module()}):
        spec.loader.exec_module(module)
    return module


def manifest(module, *, grade="best-effort-tree"):
    inputs = []
    interpreter = Path(sys.executable).resolve()
    return {
        "schemaVersion": module.SCHEMA_VERSION,
        "kind": "agent-factory-execution",
        "source": {"inputs": inputs, "ignoredPolicy": "include-by-digest", "ignoreFileDigests": {}, "submodules": [], "snapshotDigest": module.digest_bytes(module.canonical_bytes(inputs))},
        "dependencies": {"lockfiles": [], "noExternalDependencies": True},
        "toolchain": {"executables": [], "interpreter": {"path": str(interpreter), "version": "fixture", "sha256": module.digest_bytes(module.read_regular(interpreter, module.MAX_ARTIFACT_BYTES))}, "runnerImage": {"kind": "host", "digest": "c" * 64, "sbomDigest": "d" * 64}},
        "environment": {"clear": True, "allow": {"LANG": "C.UTF-8", "TZ": "UTC"}, "forbidPrefixes": ["LD_", "DYLD_"]},
        "platform": {"os": "fixture", "architecture": "fixture", "runnerImageDigest": "c" * 64},
        "command": {"argv": [str(interpreter), "fixture.py"], "cwd": ".", "stdin": "closed", "umask": "0022"},
        "policy": {"network": {"mode": "inherit"}, "time": {"mode": "host", "unixSeconds": 0}, "randomness": {"mode": "host", "seedDigest": "0" * 64}, "filesystem": {"mode": "host"}, "limits": {"wallSeconds": 30, "memoryBytes": 268435456, "pids": 16, "cpu": "100000 100000", "enforce": False}},
        "outputs": {"root": "out", "symlinks": "reject", "specialFiles": "reject"},
        "builder": {"id": "fixture", "backend": "auto", "requiredGrade": grade},
    }


class TrustedExecutorTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def trusted_capabilities(self):
        value = self.module.capability_report()
        value["controlPlaneIsolation"] = "brokered-fixture"
        if os.name != "nt":
            value["artifactPublication"] = "posix-descriptor"
        return value

    def advance_success(self, run, journal, capabilities):
        journal.advance("contained", capabilities=capabilities)
        journal.advance("launching")
        journal.advance("launched")
        result = {"status": "completed", "exitCode": 0}
        terminal = self.module._terminal_observation(run, result)
        journal.advance("observed", result=result, terminal_digest=terminal)
        journal.advance("quiescent")

    def test_manifest_identity_is_canonical_and_ignores_host_environment(self):
        value = manifest(self.module)
        identity = self.module.digest_bytes(self.module.canonical_bytes(value))
        with mock.patch.dict(os.environ, {"HOME": "/mutated", "TZ": "host"}, clear=True):
            mutated_host_identity = self.module.digest_bytes(self.module.canonical_bytes(value))
        self.assertEqual(identity, mutated_host_identity)
        value["environment"]["allow"]["TZ"] = "Asia/Seoul"
        self.assertNotEqual(identity, self.module.digest_bytes(self.module.canonical_bytes(value)))

    def test_rfc8785_float_free_golden_vectors_and_ijson_boundaries(self):
        vectors = (
            ({"\U0001f600": 1, "\ue000": 2}, b'{"\xf0\x9f\x98\x80":1,"\xee\x80\x80":2}'),
            ({"quote": '"\\\b\f\n\r\t'}, b'{"quote":"\\"\\\\\\b\\f\\n\\r\\t"}'),
            ({"max": (1 << 53) - 1, "min": -((1 << 53) - 1)}, b'{"max":9007199254740991,"min":-9007199254740991}'),
        )
        for value, expected in vectors:
            with self.subTest(value=value):
                self.assertEqual(self.module.canonical_bytes(value), expected)
        for invalid in ((1 << 53), -1 << 53, {"bad": "\ud800"}):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(self.module.ExecutorError) as raised:
                    self.module.canonical_bytes(invalid)
                self.assertEqual(raised.exception.code, "manifest_invalid")

    def test_manifest_and_evidence_unknown_fields_fail_closed(self):
        value = manifest(self.module)
        value["unknown"] = True
        with self.assertRaises(self.module.ExecutorError) as raised:
            self.module.validate_manifest(value)
        self.assertEqual(raised.exception.code, "manifest_invalid")

    @unittest.skipIf(os.name == "nt", "native Windows directory handles are required")
    def test_artifact_symlink_special_file_and_post_seal_mutation_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory).resolve()
            output = run / "out"
            output.mkdir()
            artifact = output / "answer.txt"
            artifact.write_bytes(b"answer")
            capabilities = self.trusted_capabilities()
            journal = self.module.Journal(run)
            journal.create("a" * 64)
            self.advance_success(run, journal, capabilities)
            result = self.module.seal_artifacts(run, output)
            blob = run / "cas" / "sha256" / result["artifacts"][0]["sha256"][:2] / result["artifacts"][0]["sha256"]
            os.chmod(blob, 0o600)
            blob.write_bytes(b"forged")
            with self.assertRaises(self.module.ExecutorError) as raised:
                self.module.verify_artifacts(run, Path(result["indexPath"]))
            self.assertEqual(raised.exception.code, "artifact_digest_mismatch")
            if os.name != "nt":
                link = output / "outside"
                link.symlink_to(Path(directory).parent)
                with self.assertRaises(self.module.ExecutorError) as symlink:
                    self.module.seal_artifacts(run, output, require_quiescent=False)
                self.assertEqual(symlink.exception.code, "artifact_path_invalid")

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    @unittest.skipIf(os.name == "nt", "native Windows directory handles are required")
    def test_signature_forgery_wrong_key_and_payload_splice_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "run-fixture"
            project = root / "project"
            project.mkdir()
            out = run / "out"
            out.mkdir(parents=True)
            (out / "a").write_bytes(b"a")
            value = manifest(self.module)
            manifest_path = run / "execution.manifest.json"
            manifest_path.write_bytes(self.module.canonical_bytes(value))
            capabilities = self.trusted_capabilities()
            journal = self.module.Journal(run)
            journal.create(self.module.digest_bytes(self.module.canonical_bytes(value)))
            self.advance_success(run, journal, capabilities)
            index = self.module.seal_artifacts(run, out)
            private = root / "private.pem"
            public = root / "public.pem"
            other_private = root / "other-private.pem"
            other_public = root / "other-public.pem"
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(other_private)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["openssl", "pkey", "-in", str(other_private), "-pubout", "-out", str(other_public)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            policy_path = root / "policy.json"
            policy_path.write_text(json.dumps({"schemaVersion": self.module.SCHEMA_VERSION, "expectedBuilderId": "fixture", "expectedKeyId": self.module.public_key_id(public), "minimumGrade": "best-effort-tree", "allowedBackends": [capabilities["backend"]]}))
            evidence = self.module.attest(run_dir=run, run_id="run-fixture", manifest_path=manifest_path, index_path=Path(index["indexPath"]), private_key=private, public_key=public, project_root=project)
            with self.assertRaises(self.module.ExecutorError) as wrong_key:
                self.module.verify_bundle(run_dir=run, bundle_path=Path(evidence["bundlePath"]), public_key=other_public, expected_run_id="run-fixture", manifest_path=manifest_path, index_path=Path(index["indexPath"]), policy_path=policy_path)
            self.assertEqual(wrong_key.exception.code, "signature_invalid")
            bundle = json.loads(Path(evidence["bundlePath"]).read_text())
            bundle["signatures"][0]["sig"] = "AAAA"
            forged_content = self.module.canonical_bytes(bundle)
            bundle_reads = 0
            original_read = self.module.read_regular
            def mutate_after_verified_read(path, maximum=self.module.MAX_MANIFEST_BYTES):
                nonlocal bundle_reads
                content = original_read(path, maximum)
                if Path(path) == Path(evidence["bundlePath"]):
                    bundle_reads += 1
                    if bundle_reads == 1:
                        os.chmod(evidence["bundlePath"], 0o600)
                        replacement = run / "forged-bundle.json"
                        replacement.write_bytes(forged_content)
                        os.replace(replacement, evidence["bundlePath"])
                return content
            with mock.patch.object(self.module, "read_regular", side_effect=mutate_after_verified_read):
                accepted = self.module.verify_bundle(run_dir=run, bundle_path=Path(evidence["bundlePath"]), public_key=public, expected_run_id="run-fixture", manifest_path=manifest_path, index_path=Path(index["indexPath"]), policy_path=policy_path)
            self.assertTrue(accepted["verified"])
            self.assertEqual(bundle_reads, 1)
            with self.assertRaises(self.module.ExecutorError) as forged:
                self.module._verify_signed_bundle(run_dir=run, bundle_path=Path(evidence["bundlePath"]), public_key=public, expected_run_id="run-fixture", manifest_path=manifest_path, index_path=Path(index["indexPath"]),)
            self.assertEqual(forged.exception.code, "signature_invalid")

    @unittest.skipIf(os.name == "nt", "POSIX startup-barrier fixture")
    def test_child_receives_only_allowlisted_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "environment.json"
            environment = {"ALLOWED": "yes", "LC_CTYPE": "C", "AF_EXECUTOR_UMASK": "0022"}
            env_executable = shutil.which("env")
            if env_executable is None:
                self.skipTest("env executable is unavailable")
            with mock.patch.dict(os.environ, {"ALLOWED": "host", "LD_PRELOAD": "forged", "SECRET": "forged"}, clear=True):
                with output.open("wb") as output_stream:
                    process, identity = self.module._compatibility_spawn([env_executable], Path(directory), environment, lambda: None, stdout=output_stream)
                    self.assertEqual(process.wait(timeout=10), 0)
            actual = dict(line.split("=", 1) for line in output.read_text().splitlines())
            self.assertEqual(identity, process.pid)
            self.assertEqual(actual, {"ALLOWED": "yes", "LC_CTYPE": "C"})

    def test_every_python_bootstrap_reconstructs_the_payload_environment(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("dict(os.environ)) if ok==b'G'", source)
        self.assertEqual(source.count("process = _spawn_python_bootstrap("), 3)
        environment = {"ALLOWED": "yes", "LC_CTYPE": "C", "AF_EXECUTOR_UMASK": "0022"}
        self.assertEqual(json.loads(self.module._payload_environment_bytes(environment)), {"ALLOWED": "yes", "LC_CTYPE": "C"})
        for apply_umask in (False, True):
            bootstrap = self.module._python_bootstrap(apply_umask=apply_umask)
            self.assertIn("payload_environment=json.loads(payload_environment_data)", bootstrap)
            self.assertIn("os.execvpe(sys.argv[4],sys.argv[4:],payload_environment)", bootstrap)

    @unittest.skipIf(os.name == "nt", "POSIX process-group cleanup fixture")
    def test_startup_callback_exception_quiesces_the_spawned_group(self):
        ownership = self.module._SpawnOwnership()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "journal failed"):
                self.module._compatibility_spawn([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), {"AF_EXECUTOR_UMASK": "0022"}, lambda: (_ for _ in ()).throw(RuntimeError("journal failed")), owned=ownership.own_posix)
            self.module._cleanup_spawn_ownership(ownership)
        self.assertIsNotNone(ownership.process)
        self.assertIsNotNone(ownership.process.poll())

    @unittest.skipIf(os.name == "nt", "POSIX early group-verification fixture")
    def test_unverified_spawned_group_leader_cleanup_stays_observed(self):
        ownership = self.module._SpawnOwnership()
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run-fixture"
            run.mkdir()
            journal = self.module.Journal(run)
            journal.create("a" * 64)
            with mock.patch.object(self.module.os, "getpgid", side_effect=lambda pid: pid + 1):
                with self.assertRaises(self.module.ExecutorError) as startup_raised:
                    self.module._compatibility_spawn([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), {"AF_EXECUTOR_UMASK": "0022"}, lambda: None, owned=ownership.own_posix)
            self.assertEqual(startup_raised.exception.code, "containment_start_failed")
            self.assertIsNone(ownership.posix_pgid)
            with self.assertRaises(self.module.ExecutorError) as cleanup_raised:
                self.module._cleanup_spawn_ownership(ownership)
            self.assertEqual(cleanup_raised.exception.code, "process_identity_lost")
            observed = self.module._record_terminal_result(journal, run, {"status": "ambiguous", "exitCode": None, "releaseState": "prepared"}, cleanup_raised.exception)
            self.assertEqual(journal.read()["phase"], "observed")
            self.assertEqual(observed["cleanup"]["code"], "process_identity_lost")
            self.assertIsNotNone(ownership.process)
            self.assertIsNotNone(ownership.process.poll())
            with self.assertRaises(self.module.ExecutorError) as quiescent:
                journal.require("quiescent")
            self.assertEqual(quiescent.exception.code, "journal_phase_invalid")

    @unittest.skipIf(os.name == "nt", "POSIX spawn-callback cleanup-proof fixture")
    def test_posix_spawn_callback_cleanup_proof_failure_stays_observed(self):
        ownership = self.module._SpawnOwnership()
        original = RuntimeError("journal failed")
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run-fixture"
            run.mkdir()
            journal = self.module.Journal(run)
            journal.create("a" * 64)
            journal.advance("contained", capabilities=self.trusted_capabilities())
            journal.advance("launching")
            with self.assertRaises(RuntimeError) as raised:
                self.module._compatibility_spawn([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), {"AF_EXECUTOR_UMASK": "0022"}, lambda: (_ for _ in ()).throw(original), owned=ownership.own_posix)
            self.assertIs(raised.exception, original)
            cleanup = self.module.ExecutorError("output_not_quiescent", "group proof failed")
            with mock.patch.object(self.module, "_quiesce_process_group", side_effect=cleanup):
                with self.assertRaises(self.module.ExecutorError) as cleanup_raised:
                    self.module._cleanup_spawn_ownership(ownership)
            observed = self.module._record_terminal_result(journal, run, {"status": "ambiguous", "exitCode": None, "releaseState": "launching"}, cleanup_raised.exception)
            self.assertEqual(journal.read()["phase"], "observed")
            self.assertEqual(observed["cleanup"]["code"], "output_not_quiescent")
            self.assertIsNotNone(ownership.process)
            ownership.process.wait(timeout=5)

    def test_windows_spawn_callback_cleanup_proof_failure_stays_observed(self):
        class Kernel:
            def CreateProcessW(self, _application, _command, _process_security, _thread_security, _inherit, _flags, _environment, _cwd, _startup, process_info):
                process_info._obj.hProcess = 101
                process_info._obj.hThread = 102
                process_info._obj.dwProcessId = 103
                process_info._obj.dwThreadId = 104
                return True

            def AssignProcessToJobObject(self, _job, _process):
                return True

            def ResumeThread(self, _thread):
                return 0

            def TerminateJobObject(self, _job, _code):
                return True

            def WaitForSingleObject(self, _process, _timeout):
                return 0

        backend = object.__new__(self.module.WindowsJobBackend)
        backend.kernel32 = Kernel()
        ownership = self.module._SpawnOwnership(job_backend=backend, job_handle=100)
        original = RuntimeError("journal failed")
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run-fixture"
            run.mkdir()
            journal = self.module.Journal(run)
            journal.create("a" * 64)
            journal.advance("contained", capabilities=self.trusted_capabilities())
            journal.advance("launching")
            with self.assertRaises(RuntimeError) as raised:
                backend.spawn_suspended(100, ["fixture.exe"], Path(directory), {}, contained=lambda: (_ for _ in ()).throw(original), owned=ownership.own_windows)
            self.assertIs(raised.exception, original)
            self.assertTrue(ownership.windows_assigned)
            cleanup = self.module.ExecutorError("output_not_quiescent", "Job proof failed")
            with mock.patch.object(backend, "active_processes", side_effect=cleanup):
                with self.assertRaises(self.module.ExecutorError) as cleanup_raised:
                    self.module._cleanup_spawn_ownership(ownership)
            observed = self.module._record_terminal_result(journal, run, {"status": "ambiguous", "exitCode": None, "releaseState": "launching"}, cleanup_raised.exception)
            self.assertEqual(journal.read()["phase"], "observed")
            self.assertEqual(observed["cleanup"]["code"], "output_not_quiescent")

    @unittest.skipIf(os.name == "nt", "POSIX descendant process-group fixture")
    def test_leader_exit_still_quiesces_and_proves_descendant_group_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            child = "import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])"
            process, pgid = self.module._compatibility_spawn([sys.executable, "-c", child], Path(directory), {"AF_EXECUTOR_UMASK": "0022"}, lambda: None)
            self.assertEqual(process.wait(timeout=10), 0)
            try:
                self.assertTrue(self.module._process_group_exists(pgid))
            finally:
                self.module._quiesce_process_group(process, pgid)
            self.assertFalse(self.module._process_group_exists(pgid))

    @unittest.skipIf(os.name == "nt", "POSIX journal fixture")
    def test_cleanup_failure_is_durable_and_never_advances_quiescent(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run-fixture"
            run.mkdir()
            journal = self.module.Journal(run)
            journal.create("a" * 64)
            journal.advance("contained", capabilities=self.trusted_capabilities())
            journal.advance("launching")
            journal.advance("launched")
            payload = {"status": "failed", "exitCode": 7}
            cleanup = self.module.ExecutorError("output_not_quiescent", "descendant survived")
            observed = self.module._record_terminal_result(journal, run, payload, cleanup)
            self.assertEqual(journal.read()["phase"], "observed")
            self.assertEqual(observed["cleanup"]["code"], "output_not_quiescent")
            with self.assertRaises(self.module.ExecutorError) as raised:
                journal.require("quiescent")
            self.assertEqual(raised.exception.code, "journal_phase_invalid")

    @unittest.skipIf(os.name == "nt", "POSIX descriptor publication fixture")
    def test_journal_ambiguity_and_prepared_manifest_substitution_fail_closed(self):
        for release_state in ("prepared", "launching", "launched"):
            with self.subTest(release_state=release_state), tempfile.TemporaryDirectory() as directory:
                run = Path(directory) / "run-fixture"
                run.mkdir()
                value = manifest(self.module)
                encoded = self.module.canonical_bytes(value)
                fixed = run / "execution.manifest.json"
                fixed.write_bytes(encoded)
                journal = self.module.Journal(run)
                journal.create(self.module.digest_bytes(encoded))
                capabilities = self.trusted_capabilities()
                if release_state != "prepared":
                    journal.advance("contained", capabilities=capabilities)
                    journal.advance("launching")
                if release_state == "launched":
                    journal.advance("launched")
                result = {"status": "ambiguous", "exitCode": None, "releaseState": release_state}
                terminal = self.module._terminal_observation(run, result)
                journal.advance("observed", result=result, terminal_digest=terminal)
                self.assertEqual(journal.read()["terminalObservationDigest"], terminal)
                alternate = run / "alternate.json"
                alternate.write_bytes(encoded)
                with self.assertRaises(self.module.ExecutorError) as raised:
                    self.module._bound_manifest(run, alternate)
                self.assertEqual(raised.exception.code, "provenance_policy_mismatch")

    def test_windows_job_handle_width_limit_readback_and_active_count(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("CreateJobObjectW.restype = ctypes.c_void_p", source)
        self.assertIn("return int(value.ActiveProcesses)", source)
        if sys.platform == "win32":
            backend = self.module.WindowsJobBackend()
            job = backend.create({"cpu": "50000 100000", "memoryBytes": 268435456, "pids": 4})
            try:
                self.assertEqual(backend.active_processes(job), 0)
            finally:
                backend.kernel32.CloseHandle(job)

    def test_backend_matrix_never_promotes_unenforced_controls(self):
        fixture = manifest(self.module, grade="hermetic")
        cases = (
            {"grade": "best-effort-tree", "networkIsolation": "none", "filesystemIsolation": "none"},
            {"grade": "contained", "networkIsolation": "none", "filesystemIsolation": "none"},
        )
        for observed in cases:
            with self.subTest(grade=observed["grade"]):
                with self.assertRaises(self.module.ExecutorError) as raised:
                    self.module.require_capabilities(fixture, observed)
                self.assertEqual(raised.exception.code, "capability_unsatisfied")

    def test_foreign_backends_are_import_safe_and_stably_refuse(self):
        if sys.platform != "win32":
            with self.assertRaises(self.module.ExecutorError) as windows:
                self.module.WindowsJobBackend()
            self.assertEqual(windows.exception.code, "capability_unsatisfied")
        if sys.platform != "darwin":
            with self.assertRaises(self.module.ExecutorError) as macos:
                self.module.MacOSProcessBackend()
            self.assertEqual(macos.exception.code, "capability_unsatisfied")


class TrustedExecutorFixtureDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture_module()

    def test_fixture_is_the_single_creator_of_the_exact_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            run = project / ".agent-factory" / "agent" / "fixture" / "runs" / "run-a"
            self.assertEqual(self.fixture.prepare_run_directory(project, run, "run-a"), run)
            self.assertTrue(run.is_dir())
            self.assertEqual(list(run.iterdir()), [])

    def test_existing_nonempty_run_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            run = project / ".agent-factory" / "agent" / "fixture" / "runs" / "run-a"
            run.mkdir(parents=True)
            (run / "unexpected").write_text("occupied", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                self.fixture.prepare_run_directory(project, run, "run-a")

    def test_existing_empty_run_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            run = project / ".agent-factory" / "agent" / "fixture" / "runs" / "run-a"
            run.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                self.fixture.prepare_run_directory(project, run, "run-a")

    @unittest.skipIf(os.name == "nt", "symlink creation is not generally available on Windows runners")
    def test_symlink_run_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            runs = project / ".agent-factory" / "agent" / "fixture" / "runs"
            runs.mkdir(parents=True)
            target = project / "target"
            target.mkdir()
            run = runs / "run-a"
            run.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                self.fixture.prepare_run_directory(project, run, "run-a")

    def test_out_of_root_run_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as project_directory, tempfile.TemporaryDirectory() as other_directory:
            project = Path(project_directory).resolve()
            run = Path(other_directory).resolve() / ".agent-factory" / "agent" / "fixture" / "runs" / "run-a"
            with self.assertRaisesRegex(ValueError, "beneath the project root"):
                self.fixture.prepare_run_directory(project, run, "run-a")


class TrustedExecutorWorkflowTests(unittest.TestCase):
    def test_reproducibility_refusal_fails_and_records_are_always_uploaded(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        reproducibility = workflow.split("  reproducibility:\n", 1)[1]
        self.assertEqual(reproducibility.count("--expect-refusal-record"), 2)
        self.assertIn("if refusal_paths:", reproducibility)
        refusal_branch = reproducibility.split("if refusal_paths:", 1)[1].split("if fixture_statuses", 1)[0]
        self.assertIn("'status':'refused'", refusal_branch)
        self.assertIn("raise SystemExit(1)", refusal_branch)
        self.assertIn("compare-executions", reproducibility)
        self.assertIn("--left-index", reproducibility)
        self.assertIn("--right-index", reproducibility)
        upload = reproducibility.split("uses: actions/upload-artifact@", 1)[1]
        self.assertIn("if: always()", upload)
        self.assertIn("path: run-records", upload)


if __name__ == "__main__":
    unittest.main()
