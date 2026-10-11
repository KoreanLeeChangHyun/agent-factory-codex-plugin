#!/usr/bin/env python3
"""Read-only Task/Session/Decision/Observation lookup and search over existing runtime records."""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser, add_project_argument  # noqa: E402
from storage import paths as runtime_paths  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from storage.files import emit, error_document  # noqa: E402
from tasks import operation_records, supervision  # noqa: E402


def build_parser():
    parser = JsonArgumentParser(prog="operation_records.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    query = commands.add_parser("query", help="Structural lookup by task, session, loop, state and update time")
    add_project_argument(query)
    query.add_argument("--task-id")
    query.add_argument("--session-id", help="Agent ID of a conductor, Work or Verification session")
    query.add_argument("--loop-id")
    query.add_argument("--state", choices=operation_records.STATES)
    query.add_argument("--updated-since", help="ISO-8601 UTC lower bound for a task's latest recorded update")
    query.add_argument("--detail", action="store_true", help="Return the full records instead of the summary")
    search = commands.add_parser("search", help="Filter records, run results and lessons, then match words; hits cite sources")
    add_project_argument(search)
    search.add_argument("--text", help="Words to find in requests, results, decisions and lessons (case-insensitive)")
    search.add_argument("--match", choices=("all", "any"), default="all", help="Require all words (default) or any word")
    search.add_argument("--kind", action="append", choices=operation_records.SEARCH_KINDS,
                        help="Record kind to search; repeat to combine (default: all kinds)")
    search.add_argument("--task-id")
    search.add_argument("--session-id", help="Agent ID of a conductor, Work or Verification session")
    search.add_argument("--loop-id")
    search.add_argument("--state", choices=operation_records.STATES)
    search.add_argument("--role", help="Session role (conductor, work, verification) or Work profile")
    search.add_argument("--model", help="Exact model ID recorded on the run")
    search.add_argument("--since", help="ISO-8601 date or time lower bound (UTC when no zone)")
    search.add_argument("--until", help="ISO-8601 date or time upper bound (UTC when no zone)")
    search.add_argument("--limit", type=int, default=50, help="Maximum hits returned (default 50)")
    supervise = commands.add_parser(
        "supervise", help="Judge unfinished loops (normal, delayed, stuck, decision-needed) and record due one-line reports")
    add_project_argument(supervise)
    supervise.add_argument("--loop-id")
    supervise.add_argument("--interval-minutes", type=int,
                           help="Periodic report interval (default 10); stuck and decision-needed are reported at once")
    supervise.add_argument("--delay-minutes", type=int, help="No recorded activity for this long is delayed (default 20)")
    supervise.add_argument("--stuck-minutes", type=int, help="No recorded activity for this long is stuck (default 60)")
    supervise.add_argument("--repeat-limit", type=int,
                           help="Repeats of one control-plane error or failed Verification that are reported (default 3)")
    supervise.add_argument("--save-settings", action="store_true",
                           help="Persist the resulting values as this runtime's defaults, also used by the loop driver")
    supervise.add_argument("--dry-run", action="store_true", help="Return verdicts without appending reports")
    return parser


def failure_class(error):
    import loop  # Loaded only for its failure taxonomy, the single owner of those classes.
    return loop.failure_class(error)


def lesson_records(project_root):
    """Lessons through the lesson CLI's own reader, each with its Markdown body path."""
    import lessons
    from storage import lessons as body_store
    found = []
    for record in lessons.records(project_root):
        meta = body_store.metadata_path(project_root, record["id"])
        stored = runtime_paths.read(meta) if meta is not None and meta.is_file() else {}
        found.append({**record, "path": str(Path(project_root) / stored["documentPath"])
                      if stored.get("documentPath") else None})
    return found


def run_search(args, agents_root):
    kinds = tuple(args.kind or operation_records.SEARCH_KINDS)
    found, errors = [], []
    if "lesson" in kinds:
        try:
            found = lesson_records(runtime_paths.absolute(args.project_root).resolve())
        except Exception as error:  # noqa: BLE001 - lesson storage problems must not hide record hits
            errors.append({"source": "lessons", "error": f"{type(error).__name__}: {error}"})
    result = operation_records.search(
        agents_root, text=args.text, match=args.match, kinds=kinds, lessons=found, task_id=args.task_id,
        session_id=args.session_id, loop_id=args.loop_id, state=args.state, role=args.role, model=args.model,
        since=args.since, until=args.until, limit=args.limit, failure_class=failure_class)
    result["errors"] += errors
    return result


def compact(result):
    def pick(item, keys):
        return {key: item.get(key) for key in keys}
    tasks = [{**pick(task, ("loopId", "title", "updatedAt")), "taskId": task["id"],
              **{role: (owned or {}).get("agentId") for role, owned in task["sessions"].items()},
              # The work completion facet must not overwrite the Work session column.
              **{"workCompletion" if key == "work" else key: value for key, value in task["status"].items()},
              "requestRevision": task["revision"]["number"],
              "decisions": task["decisionIds"], "observations": task["observationIds"]}
             for task in result["tasks"]]
    sessions = [{**pick(session, ("id", "role", "provider", "model", "running", "activeRunId", "latestRunId",
                                  "latestRunStatus", "handoff")), "ownedTasks": len(session["ownedTasks"])}
                for session in result["sessions"]]
    decisions = [pick(item, ("id", "source", "decisionKind", "status", "decided", "loopId", "taskId", "sessionId",
                             "runId", "target", "reason", "impact", "alternatives", "updatedAt"))
                 for item in result["decisions"]]
    observations = [pick(item, ("id", "taskId", "sessionId", "role", "runStatus", "verdict", "currentRevision",
                                "assessment", "observedAt")) for item in result["observations"]]
    return {"schemaVersion": result["schemaVersion"], "kind": "operations-records-summary",
            "filters": result["filters"], "tasks": tasks, "sessions": sessions, "decisions": decisions,
            "observations": observations, "errors": result["errors"]}


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        binding = runtime_paths.resolve(args.project_root, home=args.runtime_home, project_id=args.project_id)
        if not binding["registered"]:
            raise ContractError("project_uninitialized", "project has no registered runtime")
        if args.command == "search":
            # Pass the current stdout: emit's default stream is bound at import time.
            emit(run_search(args, binding["agentsRoot"]), sys.stdout)
            return 0
        if args.command == "supervise":
            settings = supervision.load_settings(
                binding["runtimeRoot"], intervalMinutes=args.interval_minutes, delayMinutes=args.delay_minutes,
                stuckMinutes=args.stuck_minutes, repeatLimit=args.repeat_limit)
            if args.save_settings:
                supervision.save_settings(binding["runtimeRoot"], settings)
            emit(supervision.tick(binding["agentsRoot"], settings=settings, loop_id=args.loop_id,
                                  failure_class=failure_class, record=not args.dry_run), sys.stdout)
            return 0
        result = operation_records.query(binding["agentsRoot"], task_id=args.task_id, session_id=args.session_id,
                                         loop_id=args.loop_id, state=args.state, updated_since=args.updated_since,
                                         failure_class=failure_class)
        emit(result if args.detail else compact(result), sys.stdout)
        return 0
    except (ContractError, OSError, ValueError) as error:
        emit(error_document(getattr(error, "code", "operation_records_failed"), str(error)), sys.stdout)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
