"""Opt-in installed Codex against a loopback-only fake Responses provider."""
import runtime_test_home
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from mock_responses_provider import MockResponsesProvider
from native_fixtures import native, native_fixture
from prompt_delivery import PromptParts
from token_usage import UsageAccumulator


class TokenDeliveryTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("AF_VERIFY_LOCAL_CODEX") == "1", "installed Codex fixture opt-in")
    def test_resume_preserves_user_rules_without_repeating_fixed_prompt(self):
        codex = shutil.which("codex")
        self.assertIsNotNone(codex)
        with tempfile.TemporaryDirectory(prefix="af-token-delivery-") as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            home = root / "codex-home"
            home.mkdir()
            fixture, _, state = native_fixture(project, goal=False, existing=False)
            # No tools are emitted by the fake provider. This fixture verifies
            # transport, not OS sandbox enforcement (which has separate tests).
            fixture.session.update(model="fixture-model", sandbox="danger-full-access",
                executionPolicy=runtime_test_home.policy("danger-full-access"), nativeCapabilities={
                "instructionDelivery": True, "goal": False, "fast": False})
            with MockResponsesProvider(state["resultPath"]) as provider:
                provider.mode = "answer"
                (home / "config.toml").write_text(
                    'model = "fixture-model"\nmodel_provider = "fixture"\napproval_policy = "never"\n'
                    'developer_instructions = "USER_RULE_TOKEN_FIXTURE"\n'
                    '[analytics]\nenabled = false\n'
                    '[features]\nenable_request_compression = false\n'
                    '[model_providers.fixture]\nname = "Owned local fixture"\nbase_url = '
                    + json.dumps(provider.base_url) + '\nwire_api = "responses"\nrequires_openai_auth = false\n'
                    'supports_websockets = false\nenv_key = "AF_LOCAL_DUMMY_TOKEN"\n')
                env = {"PATH": os.environ["PATH"], "HOME": str(root), "CODEX_HOME": str(home),
                       "AF_LOCAL_DUMMY_TOKEN": "fixture-only", "LANG": "C.UTF-8"}
                session = dict(fixture.session)
                for index in range(2):
                    process = subprocess.Popen([codex, "app-server", "--listen", "stdio://"],
                        cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True)
                    timer = threading.Timer(30, process.kill)
                    timer.start()
                    try:
                        rpc = native.Rpc(process)
                        bridge = native.Bridge(fixture.runtime, session, state, rpc)
                        with redirect_stdout(io.StringIO()) as output:
                            bridge.run(PromptParts("FIXED_RULE_TOKEN_FIXTURE", f"Bounded request {index}"))
                        events = [json.loads(line) for line in output.getvalue().splitlines()]
                        usage = UsageAccumulator()
                        for event in events:
                            usage.observe(event)
                        self.assertEqual(usage.snapshot()["inputTokens"], 100)
                        self.assertEqual(usage.snapshot()["outputTokens"], 10)
                        session["sessionId"] = bridge.thread_id
                    finally:
                        timer.cancel()
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                        process.stdin.close()
                        process.stdout.close()
                self.assertEqual(provider.errors, [])
                self.assertEqual(len(provider.requests), 2)
                for request in provider.requests:
                    text = json.dumps(request)
                    self.assertEqual(text.count("USER_RULE_TOKEN_FIXTURE"), 1)
                    self.assertEqual(text.count("FIXED_RULE_TOKEN_FIXTURE"), 1)
