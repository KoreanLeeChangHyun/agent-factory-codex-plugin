"""Argument parser and option validation for the public exec.py CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import execution_policy
from runtime_errors import ContractError

ACTORS = ("main", "human")
HUMAN_APPROVAL_POLICIES = ("required", "bypass")


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError("invalid_arguments", message)


def add_project_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-home", type=Path)
    parser.add_argument("--project-id")


def add_request_arguments(parser: argparse.ArgumentParser) -> None:
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--request-file", type=Path)
    request.add_argument("--message")
    parser.add_argument("--actor", choices=ACTORS, default="main")
    parser.add_argument(
        "--human-approval-policy", choices=HUMAN_APPROVAL_POLICIES,
        help="Main delegation approval policy; omitted sends preserve the session policy",
    )
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", choices=("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"))
    parser.add_argument("--fast", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--goal-mode", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--goal-objective", help="Native persisted objective, 1–4000 characters; omitted on send preserves the existing objective")
    parser.add_argument(
        "--receipt-request-hash",
        help="SHA-256 identity the role receipt must bind (defaults to this run request)",
    )
    parser.add_argument(
        "--verified-work-run-id",
        help="exact Work run checked by a Verification Agent (required for Verification runs)",
    )
    parser.add_argument("--reporting-config", type=Path, help="Explicit private cloud recipient configuration; per run")
    parser.add_argument("--reporting-loop-id", help="Exact owning loop identity for cloud reporting")
    parser.add_argument("--dispatch-id", help="idempotency key scoped to this managed Agent")
    parser.add_argument(
        "--capability-binding-file", type=Path,
        help="strict Agent capability/authority/effects binding to preserve in this run",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(prog="exec.py")
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "location", "projects", "rebind", "map-path"):
        location_parser = commands.add_parser(name)
        add_project_argument(location_parser)
        if name == "map-path":
            location_parser.add_argument("--path", type=Path, required=True)
        if name == "rebind":
            location_parser.add_argument("--from-root", type=Path, required=True)

    commands.add_parser("doctor", help="Inspect host sandbox prerequisites; use doctor --help for options")

    submit_parser = commands.add_parser("submit")
    add_project_argument(submit_parser)
    add_request_arguments(submit_parser)
    submit_parser.add_argument("--agent", required=True)
    submit_parser.add_argument("--role", required=True)
    submit_parser.add_argument("--codex", default="codex")
    execution_policy.add_policy_arguments(submit_parser)
    submit_parser.add_argument("--heartbeat-interval", type=float, default=5.0)
    submit_parser.add_argument("--heartbeat-timeout", type=float, default=20.0)
    submit_parser.add_argument("--start-timeout", type=float, default=60.0)
    submit_parser.add_argument("--turn-timeout", type=float, default=1800.0)
    submit_parser.add_argument("--max-attempts", type=int, default=2)

    send_parser = commands.add_parser("send")
    add_project_argument(send_parser)
    add_request_arguments(send_parser)
    send_parser.add_argument("--agent", required=True)
    execution_policy.add_policy_arguments(send_parser)

    for name in ("status", "result", "cancel"):
        command_parser = commands.add_parser(name)
        add_project_argument(command_parser)
        command_parser.add_argument("--agent", required=True)
        if name == "status":
            identity = command_parser.add_mutually_exclusive_group(required=True)
            identity.add_argument("--run-id")
            identity.add_argument("--dispatch-id")
        else:
            command_parser.add_argument("--run-id", required=True)
        if name == "result":
            command_parser.add_argument("--ack", action="store_true")

    capability_parser = commands.add_parser("capabilities")
    add_project_argument(capability_parser)
    capability_parser.add_argument("--codex", default="codex")
    capability_parser.add_argument("--agent")

    goal_parser = commands.add_parser("goal")
    add_project_argument(goal_parser)
    goal_parser.add_argument("--agent", required=True)
    goal_parser.add_argument("action", choices=("get", "refresh", "pause", "cancel", "clear", "disable", "resume", "reopen"))

    list_parser = commands.add_parser("list")
    add_project_argument(list_parser)

    inbox_parser = commands.add_parser("inbox")
    add_project_argument(inbox_parser)
    inbox_parser.add_argument("--agent")
    inbox_parser.add_argument("--ack", action="store_true")

    reconcile_parser = commands.add_parser("reconcile")
    add_project_argument(reconcile_parser)
    reconcile_parser.add_argument("--agent")

    for name in ("reporting-deliver", "_report-send"):
        reporting_parser = commands.add_parser(name, help="Deliver pending reports" if name == "reporting-deliver" else argparse.SUPPRESS)
        add_project_argument(reporting_parser)
        reporting_parser.add_argument("--agent", required=True)
        reporting_parser.add_argument("--run-id", required=True)
        if name == "_report-send":
            reporting_parser.add_argument("--entry", type=int, required=True)

    worker_parser = commands.add_parser("_worker", help=argparse.SUPPRESS)
    add_project_argument(worker_parser)
    worker_parser.add_argument("--agent", required=True)
    worker_parser.add_argument("--run-id", required=True)

    bootstrap_parser = commands.add_parser("_bootstrap", help=argparse.SUPPRESS)
    bootstrap_parser.add_argument("--ready-fd", required=True, type=int)
    bootstrap_parser.add_argument("--release-fd", required=True, type=int)
    bootstrap_parser.add_argument("target", nargs=argparse.REMAINDER)

    return parser.parse_args(argv)


def validate_submit_options(args: argparse.Namespace) -> None:
    positive = {
        "heartbeat interval": args.heartbeat_interval,
        "heartbeat timeout": args.heartbeat_timeout,
        "start timeout": args.start_timeout,
        "turn timeout": args.turn_timeout,
    }
    for label, value in positive.items():
        if value <= 0:
            raise ContractError("invalid_timeout", f"{label} must be positive")
    if args.heartbeat_timeout <= args.heartbeat_interval:
        raise ContractError(
            "invalid_timeout", "heartbeat timeout must exceed heartbeat interval"
        )
    if args.max_attempts < 1 or args.max_attempts > 10:
        raise ContractError("invalid_attempts", "max attempts must be between 1 and 10")



