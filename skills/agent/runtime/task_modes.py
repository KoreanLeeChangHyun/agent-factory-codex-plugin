"""Per-request execution routes; missing historical values retain the fixed graph."""
from runtime_errors import ContractError

TASK_MODES = ("direct", "work", "work-verification", "plan-work-verification")
LEGACY_MODE = "work-verification"


def validate_mode(mode):
    if mode not in TASK_MODES:
        raise ContractError("task_mode_invalid", "Unknown task mode")
    return mode


def route_instruction(mode, role):
    validate_mode(mode)
    if role != "main":
        return ""
    routes = {
        "direct": "Perform the bounded task directly as Main, including appropriate own checks. Do not dispatch Work or Verification for this task.",
        "work": "Delegate bounded implementation to Work using exec.py or loop.py start --task-mode work. After completed Work and its receipt, perform appropriate own checks and integrate. Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "work-verification": "Use loop.py start --task-mode work-verification. Work then separate Verification. On fail, reuse the same Work and Verification sessions until pass or an explicitly evidenced Human skip.",
        "plan-work-verification": "Use loop.py start --task-mode plan-work-verification. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session, then separate Verification. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Reuse Work and Verification sessions on failure.",
    }
    return (f"\nCaptured task mode: {mode}. This applies to this request; later selections cannot change it.\n"
            + routes[mode] + "\nConversation always remains direct Main. Mode selection grants no Human approval or permission expansion. Apply the independent approval policy.\n")
