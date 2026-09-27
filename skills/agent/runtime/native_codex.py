"""Compatibility import; implementation is owned by adapters.codex.transport."""
import sys
from adapters.codex import transport as _implementation
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys.modules[__name__] = _implementation
