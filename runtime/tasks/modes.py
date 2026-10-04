"""Per-request execution routes; missing historical values retain the fixed graph."""
from storage.errors import ContractError

TASK_MODES = ("orchestrate", "direct", "work", "plan", "verification", "plan-work", "work-verification", "plan-work-verification")
LEGACY_MODE = "work-verification"
# Display label for the Work profile Main chose; it selects no model, permission or agent.
WORK_PROFILES = ("work", "workLight")
# What orchestrator Main does with a stopped loop's `failureClass`. Guidance only: the runtime never re-dispatches Work.
FAILURE_CLASS_ACTIONS = ("A stopped loop reports failureClass; act on it: contract - the runtime's automatic receipt recovery already ran, so report a run that still ended failed; "
                         "transient - run loop.py reconcile, read the status once more, then decide; environment - stop and report the cause to the Human; "
                         "human - pass the decision to the Human; provider - report the provider's message and do not dispatch again unless the Human asks. ")


def validate_mode(mode):
    if mode not in TASK_MODES:
        raise ContractError("task_mode_invalid", "Unknown task mode")
    return mode


def route_instruction(mode, role):
    validate_mode(mode)
    if role != "main":
        return ""
    routes = {
        "orchestrate": ("Orchestrator mode. Handle conversation, planning, Interview, requirement shaping, routing and light lookups of local project files and state directly as Main. "
                        "A project change the Human explicitly requests, and any web search, URL fetch or external lookup (research, however small), is delegated with a brief, not a work contract: write one request file containing Goal (one or two sentences), Scope (target files or research topic, and what not to do, e.g. no commits), Done (what must be true when finished) and Report (result summary, changed paths, sources for research), then run "
                        "`python3 <plugin-root>/scripts/loop.py start --project-root PROJECT --task-mode work --work-agent UNIQUE_ID --request-file BRIEF` plus the Work profile flags. No task-list JSON, announce-tasks, task-flow block, contract, progress document or lesson retrieval is needed; the runtime derives the single task shown in the panel. "
                        "Choose the profile: workLight for bounded, already-decided changes and simple lookups; work for multi-file, design, unknown-cause or multi-source research; pass --work-profile work or --work-profile workLight naming that choice, together with the profile's exact model ID and effort as --work-model/--work-reasoning-effort, and retry a failed workLight attempt once with the work profile (--work-profile work) only when its failureClass is contract or absent. --work-profile only records the choice for the task panel; never pass a profile word such as light or heavy as a model, and without configured profile models omit --work-model but keep --work-profile. "
                        "Start separate Verification only when the Human explicitly requests it (--task-mode work-verification with --verification-agent). After acceptance, finish this turn with the accepted IDs; on the completion notification, acknowledge the exact result/receipt and report without reviewing or rerunning checks. Report separate Verification as not requested unless it ran. "
                        + FAILURE_CLASS_ACTIONS +
                        "The runtime enforces Main's tool limits: read with read tools or single read-only shell commands (no redirection, chaining or substitution); write only the brief and other files inside this run's directory; run each Agent Factory script as its own `python3 <plugin-root>/scripts/` command; never edit project files or commit. If the Human asks for a commit or a direct edit, ask them to resend it in direct mode. The work-contract procedure (announcements, contract files, progress documents) belongs to Human-selected contract workflows only."),
        "direct": "When this message explicitly requests work, perform the bounded task directly as Main, including appropriate own checks. Do not dispatch Work or Verification for this task.",
        "plan": "Dispatch role work using exec.py submit --role work --task-mode plan. The runtime uses actual Codex Plan collaboration mode and stops after planning. Return that plan without implementation, verification, or an automatic execution transition. Do not send literal /plan text as a substitute.",
        "verification": "Resolve the inspection target from explicit input first, otherwise prior completed work in this current chat. If neither supplies an unambiguous target, ask the Human for the target; never invent Work evidence. Dispatch a managed Verification agent using exec.py submit --role verification --task-mode verification with a bounded request identifying the exact target and authorized checks. Do not pass --verified-work-run-id or --receipt-request-hash: standalone receipts bind their own target request and cannot satisfy a Work loop. Report its findings without repair or a Work dispatch.",
        "work": "Delegate bounded implementation to Work using exec.py or loop.py start --task-mode work. Work uses native Goal to finish the bounded task and necessary own checks. After completion, acknowledge the exact result/receipt and report; do not review implementation or rerun checks. Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "plan-work": "Use loop.py start --task-mode plan-work. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Work uses native Goal to finish the bounded task and necessary own checks. After completion, acknowledge the exact result/receipt and report; do not review implementation or rerun checks. Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "work-verification": "Use loop.py start --task-mode work-verification. Work then separate Verification. On fail, reuse the same Work and Verification sessions until pass, an explicitly evidenced Human skip, or the loop's revision limit, where the Human decides whether to extend or close.",
        "plan-work-verification": "Use loop.py start --task-mode plan-work-verification. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session, then separate Verification. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Reuse Work and Verification sessions on failure.",
    }
    return (f"\nCaptured task mode: {mode}. This applies to this request; later selections cannot change it.\n"
            + routes[mode] + "\nConversation always remains direct Main: answer questions, consultation, discussion, planning and unclear messages without editing files, running changes or delegating changes. Mode selection grants no Human approval or permission expansion. Apply the independent approval policy.\n")


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
