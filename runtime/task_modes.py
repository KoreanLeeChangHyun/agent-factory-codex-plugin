"""Per-request execution routes; missing historical values retain the fixed graph."""
from runtime_errors import ContractError

TASK_MODES = ("direct", "work", "plan", "verification", "plan-work", "work-verification", "plan-work-verification")
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
        "plan": "Dispatch role work using exec.py submit --role work --task-mode plan. The runtime uses actual Codex Plan collaboration mode and stops after planning. Return that plan without implementation, verification, or an automatic execution transition. Do not send literal /plan text as a substitute.",
        "verification": "Resolve the inspection target from explicit input first, otherwise prior completed work in this current chat. If neither supplies an unambiguous target, ask the Human for the target; never invent Work evidence. Dispatch a managed Verification agent using exec.py submit --role verification --task-mode verification with a bounded request identifying the exact target and authorized checks. Do not pass --verified-work-run-id or --receipt-request-hash: standalone receipts bind their own target request and cannot satisfy a Work loop. Report its findings without repair or a Work dispatch.",
        "work": "Delegate bounded implementation to Work using exec.py or loop.py start --task-mode work. Work uses native Goal to finish the bounded task and necessary own checks. After completion, acknowledge the exact result/receipt and report; do not review implementation or rerun checks. Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "plan-work": "Use loop.py start --task-mode plan-work. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Work uses native Goal to finish the bounded task and necessary own checks. After completion, acknowledge the exact result/receipt and report; do not review implementation or rerun checks. Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "work-verification": "Use loop.py start --task-mode work-verification. Work then separate Verification. On fail, reuse the same Work and Verification sessions until pass or an explicitly evidenced Human skip.",
        "plan-work-verification": "Use loop.py start --task-mode plan-work-verification. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session, then separate Verification. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Reuse Work and Verification sessions on failure.",
    }
    return (f"\nCaptured task mode: {mode}. This applies to this request; later selections cannot change it.\n"
            + routes[mode] + "\nConversation always remains direct Main. Mode selection grants no Human approval or permission expansion. Apply the independent approval policy.\n")


def work_goal_options(options, request_text):
    """Bind Goal to this Work request, leaving plan-only read-only and finite."""
    options = dict(options)
    if options.get("taskMode") == "plan":
        if options.get("goalMode") is True:
            raise ContractError("goal_role_invalid", "Plan-only cannot execute a Goal")
        options["goalMode"] = False
        return options
    if options.get("goalMode") is False:
        raise ContractError("goal_required", "Work execution requires native Goal support")
    options["goalMode"] = True
    options.setdefault("goalObjective", request_text if len(request_text) <= 4000 else
                       "Complete this run's bounded request supplied in the developer instructions, "
                       "including necessary own checks and the exact result/receipt contract. "
                       "Stop on failure or a required unresolved Human decision.")
    return options
