"""Compatibility import; implementation is owned by adapters.codex.preflight."""
import sys
from adapters.codex import preflight as _implementation
sys.modules[__name__] = _implementation
