#!/usr/bin/env python3
"""Check or perform a Main-owned receipt-bound ordinary local commit."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from tasks.commits import bound_main, execute  # noqa: E402
from tasks.orchestrator_guard import ENV, has_symlink, inside  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from storage.files import safe_read_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Exact approved commit manifest inside this Main run")
    parser.add_argument("--apply", action="store_true", help="Perform the approved ordinary local commit; default checks only")
    args = parser.parse_args()
    try:
        config = json.loads(os.environ.get(ENV, "{}"))
        root, state = bound_main(config)
        if has_symlink(args.input) or not inside(args.input, Path(state["statePath"]).parent, None):
            raise ContractError("commit_scope_invalid", "Manifest must belong to this Main run")
        print(json.dumps(execute(root, state, safe_read_json(Path(args.input)), apply=args.apply)))
        return 0
    except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "blocked", "code": getattr(error, "code", "commit_scope_invalid"), "message": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
