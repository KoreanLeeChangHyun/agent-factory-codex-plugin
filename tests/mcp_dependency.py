"""Explicit development dependency on the owning MCP package, never a copied validator."""
import os
from pathlib import Path
import sys

source = Path(os.environ.get("AGENT_FACTORY_MCP_SOURCE", Path(__file__).resolve().parents[2] / "mcp"))
if (source / "app/modules/document/pair.py").is_file():
    sys.path.insert(0, str(source))
try:
    from app.modules.document.cloud_schemas import Pair
    from app.modules.document.pair import tree_hash, validate_pair
    from app.common.errors import ApplicationError
except ImportError as exc:
    raise RuntimeError(
        "Final plugin checks require the agent-factory-mcp development dependency. "
        "Install its dev dependencies and set AGENT_FACTORY_MCP_SOURCE to its source root "
        "or install the owning package in this test environment."
    ) from exc


def fixture_pair(files, name, ai=None, human=None):
    """Synthetic review input for structural tests; never publication/semantic evidence."""
    ai = ai or f"skills/{name}"
    human = human or f".agent-factory/document/specification/{name}"
    return Pair(specification_id=name, ai_root=ai, human_root=human,
                git_repository="https://example.invalid/structural-test", git_commit="0" * 40,
                review={"reviewer": "structural-test-fixture", "evidence": "Synthetic test only; independent semantic review remains required.",
                        "authority_reference": "test-fixture-not-publication", "verdict": "aligned",
                        "ai_sha256": tree_hash(files, ai), "human_sha256": tree_hash(files, human)})


def source_files(root, name):
    result = {}
    for prefix in (f"skills/{name}", f".agent-factory/document/specification/{name}"):
        for path in (root / prefix).rglob("*"):
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink():
                raise AssertionError(f"Unexpected publication-source symlink: {path}")
            if path.is_file():
                result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result
