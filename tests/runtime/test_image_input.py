from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from native_fixtures import native, native_fixture, runtime

image_input = runtime.image_input
capability_contracts = runtime.capability_contracts
ContractError = runtime.ContractError
build_codex_command = runtime.build_codex_command
runtime_test_home = __import__("runtime_test_home")


class ImageInputContractTests(unittest.TestCase):
    def write_contract(self, root: Path, images: list[dict[str, str]]) -> Path:
        path = root / "input.json"
        path.write_text(json.dumps({"schemaVersion": "0.1.0", "kind": "agent-input", "message": "inspect image", "images": images}), encoding="utf-8")
        return path

    def test_contract_captures_bounded_sibling_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\ncontent")
            request, images = image_input.read_agent_input(self.write_contract(root, [{"path": "sample.png", "mediaType": "image/png"}]))
            self.assertEqual(request, b"inspect image")
            self.assertEqual(images[0]["content"], b"\x89PNG\r\n\x1a\ncontent")
            (root / "sample.png").write_bytes(b"changed")
            self.assertEqual(images[0]["content"], b"\x89PNG\r\n\x1a\ncontent")

    def test_contract_bytes_reach_managed_state_cli_and_app_server_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            content = b"\x89PNG\r\n\x1a\nconnected-content"
            (root / "sample.png").write_bytes(content)
            request, images = image_input.read_agent_input(
                self.write_contract(root, [{"path": "sample.png", "mediaType": "image/png"}])
            )
            runtime.runtime_paths.resolve(root, create=True)
            state = runtime.create_run(
                project_root=root, agent_id="main-image", actor="human", request=request,
                session={"role": "main", "maxAttempts": 2}, images=images,
            )
            stored = state["imageInputs"][0]
            self.assertEqual(stored["size"], len(content))
            self.assertEqual(stored["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(Path(stored["path"]).read_bytes(), content)

            cli_session = {
                "codex": "codex", "projectRoot": str(root),
                "executionPolicy": runtime_test_home.policy("read-only"),
            }
            command = build_codex_command(cli_session, state, None)
            self.assertEqual(command[command.index("--image") + 1], stored["path"])

            native_root = root / "native"
            native_root.mkdir()
            fixture_bridge, rpc, fixture_state = native_fixture(native_root, goal=False)
            fixture_state["imageInputs"] = state["imageInputs"]
            native.Bridge(runtime, fixture_bridge.session, fixture_state, rpc).setup("inspect image")
            turn = next(params for method, params in rpc.calls if method == "turn/start")
            self.assertIn({"type": "localImage", "path": stored["path"]}, turn["input"])

    def test_contract_rejects_traversal_mime_mismatch_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.png"
            target.write_bytes(b"image")
            (root / "linked.png").symlink_to(target)
            cases = [
                {"path": "../target.png", "mediaType": "image/png"},
                {"path": "target.png", "mediaType": "image/jpeg"},
                {"path": "linked.png", "mediaType": "image/png"},
                {"path": "target.png", "mediaType": "image/png"},
            ]
            for image in cases:
                with self.subTest(image=image), self.assertRaises(ContractError):
                    image_input.read_agent_input(self.write_contract(root, [image]))

    def test_contract_rejects_image_changed_during_same_descriptor_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sample.png"
            target.write_bytes(b"\x89PNG\r\n\x1a\ncontent")
            contract = self.write_contract(root, [{"path": "sample.png", "mediaType": "image/png"}])
            original_read = capability_contracts.os.read
            mutated = False

            def racing_read(descriptor: int, size: int) -> bytes:
                nonlocal mutated
                content = original_read(descriptor, size)
                if content.startswith(b"\x89PNG") and not mutated:
                    mutated = True
                    target.write_bytes(b"\x89PNG\r\n\x1a\nchanged-content")
                return content

            with mock.patch.object(capability_contracts.os, "read", side_effect=racing_read), self.assertRaises(ContractError) as raised:
                image_input.read_agent_input(contract)
            self.assertEqual(raised.exception.code, "input_image_invalid")

    def test_exec_initial_and_resume_use_supported_image_argument(self) -> None:
        state = {"responseSchemaPath": "/tmp/schema", "statePath": "/tmp/run/state.json", "imageInputs": [{"path": "/tmp/run/images/00.png"}]}
        session = {"codex": "codex", "projectRoot": "/tmp", "executionPolicy": runtime_test_home.policy("read-only")}
        for thread in (None, "exact-thread"):
            with self.subTest(thread=thread):
                command = build_codex_command(session, state, thread)
                self.assertEqual(command[command.index("--image") + 1], "/tmp/run/images/00.png")

    def test_goal_mode_rejects_images_before_run_creation(self) -> None:
        with self.assertRaises(ContractError) as raised:
            image_input.validate_execution([{"content": b"image"}], {"goalMode": True})
        self.assertEqual(raised.exception.code, "image_goal_unsupported")

    def test_capabilities_advertise_image_transport_for_submit_and_send(self) -> None:
        capabilities = {
            "schemaVersion": "0.1.0",
            "kind": "execution-capabilities",
            "submit": {"model": False, "reasoning": False, "fast": False, "goal": False},
            "send": {"model": False, "reasoning": False, "fast": False, "goal": False},
            "diagnostic": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            runtime.runtime_paths.resolve(Path(directory), create=True)
            with mock.patch.object(runtime.native_codex, "inspect_capabilities", return_value=capabilities), \
                    mock.patch.object(runtime, "require_managed_platform"), \
                    mock.patch.object(runtime, "emit") as emit, redirect_stdout(io.StringIO()):
                runtime.main(["capabilities", "--project-root", directory])
        emitted = emit.call_args.args[0]
        self.assertIs(emitted["submit"]["images"], True)
        self.assertIs(emitted["send"]["images"], True)


if __name__ == "__main__":
    unittest.main()
