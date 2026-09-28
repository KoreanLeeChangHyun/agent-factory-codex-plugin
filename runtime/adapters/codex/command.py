"""Codex CLI and app-server launch commands."""
import json
import sys
from pathlib import Path
from typing import Any
from . import policy as execution_policy

def build_codex_command(
    session: dict[str, Any], state: dict[str, Any], session_id: str | None,
    *, prompt_parts: bool = False,
) -> list[str]:
    codex = str(session["codex"])
    common = []
    for image in state.get("imageInputs", []):
        common.extend(["--image", str(image["path"])])
    common.extend(["--json", "--output-schema", str(state["responseSchemaPath"])])
    if session.get("backend") == "app-server":
        return [sys.executable, str(Path(__file__).with_name("transport.py")), str(state["statePath"]),
                *(["--prompt-parts"] if prompt_parts else [])]
    policy = execution_policy.session_policy(session)
    common.extend(execution_policy.arguments(policy, Path(state["statePath"]).parent))
    if session.get("fast") is False:
        common.extend(["-c", 'service_tier="default"'])
    if session.get("reasoningEffort"):
        common.extend(["-c", "model_reasoning_effort=" + json.dumps(session["reasoningEffort"])])
    # Bounded roles must never inherit native goal auto-continuation from config.
    common.extend(["-c", "features.goals=false"])
    model = session.get("model")
    if model:
        common.extend(["--model", str(model)])
    if session_id is None:
        return [
            codex,
            "exec",
            "--cd",
            str(session.get("workingDirectory", session["projectRoot"])),
            *common,
            "-",
        ]
    return [
        codex,
        "exec",
        "--cd",
        str(session.get("workingDirectory", session["projectRoot"])),
        "resume",
        *common,
        session_id,
        "-",
    ]

