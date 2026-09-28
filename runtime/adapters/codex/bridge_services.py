"""Explicit services consumed by the native bridge; no CLI orchestrator import."""
import paths as runtime_paths
from . import policy as execution_policy
from .control import record_goal_uncertainty
from runtime_errors import ContractError
from runtime_storage import atomic_write, atomic_write_json, safe_read_json, session_file, update_json
from process_containment import now
from process_transport import inline_result, validate_terminal_result
