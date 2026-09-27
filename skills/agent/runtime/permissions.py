"""Compatibility import; implementation is owned by adapters.codex.permissions."""
import sys
from adapters.codex import permissions as _implementation
sys.modules[__name__] = _implementation
