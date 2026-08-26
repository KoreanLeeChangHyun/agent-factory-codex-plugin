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
    def test_generated_result_path_schema_has_string_type_and_exact_path(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            state = module.create_run(
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


if __name__ == "__main__":
    unittest.main()
