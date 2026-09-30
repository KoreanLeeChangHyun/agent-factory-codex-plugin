#!/usr/bin/env python3
"""PreToolUse hook that keeps an orchestrator-mode Main from changing the project.

Codex and Antigravity run this for Main tool calls. It is inert unless the provider process
carries AGENT_FACTORY_ORCHESTRATOR_GUARD, which the runtime sets only for orchestrate Main runs.
Allowed: reading, Agent Factory scripts, read-only Git and file writes inside the run directory.
Standard library only: hooks start a fresh interpreter for every tool call.
"""
import json
import os
from pathlib import Path
import shlex
import sys

ENV = "AGENT_FACTORY_ORCHESTRATOR_GUARD"
REASON = ("Orchestrator mode: Main may only read, write inside its run directory and run Agent Factory "
          "scripts. Delegate project changes to Work; commits and direct edits need worker mode (direct).")
READ_COMMANDS = {"cat", "head", "tail", "ls", "pwd", "wc", "grep", "rg", "nl", "stat", "file", "tree", "jq",
                 "diff", "basename", "dirname", "realpath", "readlink", "date", "echo", "printf", "true", "test",
                 "sort", "uniq", "cut", "tr", "column", "which", "command"}
GIT_READS = {"status", "diff", "log", "show", "rev-parse", "ls-files", "blame", "grep", "branch", "describe"}
OPERATORS = {";", "&", "&&", "||", "<", ">", ">>", "<<", "<<<", ">|", "&>", ">&", "<&", "(", ")"}
# Antigravity tools that only read or report.
# Web search and URL reads are research, which orchestrator Main delegates.
AGY_READS = {"view_file", "list_dir", "find_by_name", "grep_search", "finish"}
AGY_WRITES = {"write_to_file", "replace_file_content", "multi_replace_file_content", "notebook_edit"}
PATH_ARGUMENTS = ("TargetFile", "AbsolutePath", "FilePath", "Path", "NotebookPath")


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
# A fixed interpreter name keeps the hook definition (and its Codex trust hash) stable across hosts.
HOOK_COMMAND = "python3 " + shlex.quote(str(Path(__file__).resolve()))


def orchestrating(state, session=None):
    """True for an orchestrate-mode Main run, the only run the guard constrains."""
    role = state.get("role") or (session or {}).get("role")
    return role == "main" and state.get("taskMode") == "orchestrate"


def environment(state):
    """Provider-process variables that arm the guard for this run."""
    return {ENV: json.dumps({"pluginRoot": str(PLUGIN_ROOT), "writeRoot": str(Path(state["statePath"]).parent)},
                            sort_keys=True)}


def inside(path, root, cwd):
    candidate = Path(path) if Path(path).is_absolute() else Path(cwd or ".") / path
    try:
        Path(os.path.realpath(candidate)).relative_to(os.path.realpath(root))
        return True
    except ValueError:
        return False


def plugin_script(path, config, cwd):
    """A script of this or another installed Agent Factory plugin copy (hosts install their own)."""
    candidate = Path(os.path.realpath(Path(cwd or ".") / path))
    root = candidate.parent.parent
    return (candidate.parent.name == "scripts" and candidate.suffix == ".py"
            and (inside(candidate, Path(config["pluginRoot"]) / "scripts", cwd)
                 or ((root / "skills" / "agent" / "SKILL.md").is_file() and (root / "scripts" / "exec.py").is_file())))


def allowed_segment(words, config, cwd, alone):
    if not words or "=" in words[0]:
        return False  # Environment prefixes could redirect tools.
    name, arguments = os.path.basename(words[0]), words[1:]
    if name in ("python3", "python"):
        # Only a whole command, so no pipe can feed a script's output onward.
        return alone and bool(arguments) and plugin_script(arguments[0], config, cwd)
    if name in ("bash", "sh", "zsh") and len(arguments) == 2 and arguments[0] in ("-c", "-lc"):
        return allowed_command(arguments[1], config, cwd)
    if name == "git":
        return (bool(arguments) and arguments[0] in GIT_READS
                and not any(a.startswith(("--output", "-o")) for a in arguments[1:])
                and (arguments[0] != "branch" or all(a.startswith("-") and a not in ("-d", "-D", "-m", "-M", "-c", "-C")
                                                     for a in arguments[1:])))
    if name == "find":
        return not any(a in ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprintf", "-fls")
                       for a in arguments)
    if name == "sed":
        return (not any(a.startswith(("-i", "--in-place")) for a in arguments)
                and not any(" w " in f" {a} " or a.rstrip().endswith(("w", "e")) for a in arguments if not a.startswith("-")))
    return name in READ_COMMANDS


def allowed_command(command, config, cwd):
    if "`" in command or "$(" in command or "\n" in command:
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
    segments, current = [], []
    for token in tokens:
        if token == "|":
            segments.append(current)
            current = []
        elif token in OPERATORS or (token and set(token) <= set(";&|<>()")):
            return False
        else:
            current.append(token)
    segments.append(current)
    return all(allowed_segment(words, config, cwd, len(segments) == 1) for words in segments)


def patch_paths(patch):
    for line in str(patch).splitlines():
        for prefix in ("*** Add File: ", "*** Update File: ", "*** Delete File: ", "*** Move to: "):
            if line.startswith(prefix):
                yield line[len(prefix):].strip()


def codex_decision(event, config):
    tool, arguments = event.get("tool_name"), event.get("tool_input") or {}
    cwd = event.get("cwd")
    if tool == "Bash":
        return allowed_command(str(arguments.get("command", "")), config, cwd)
    if tool == "apply_patch":
        paths = list(patch_paths(arguments.get("command", "")))
        return bool(paths) and all(inside(path, config["writeRoot"], cwd) for path in paths)
    return True


def agy_decision(event, config):
    call = event.get("toolCall") or {}
    tool, arguments = call.get("name"), call.get("args") or {}
    cwd = arguments.get("Cwd") or next(iter(event.get("workspacePaths") or []), None)
    if tool in AGY_READS:
        return True
    if tool == "run_command":
        return allowed_command(str(arguments.get("CommandLine", "")), config, cwd)
    if tool in AGY_WRITES:
        paths = [arguments[key] for key in PATH_ARGUMENTS if isinstance(arguments.get(key), str)]
        return bool(paths) and all(inside(path, config["writeRoot"], cwd) for path in paths)
    return False


def main():
    event = json.load(sys.stdin)
    agy = "toolCall" in event
    raw = os.environ.get(ENV)
    if not raw:
        allowed = True
    else:
        try:
            config = json.loads(raw)
            allowed = agy_decision(event, config) if agy else codex_decision(event, config)
        except Exception:
            allowed = False  # Fail closed while guarding.
    if agy:
        print(json.dumps({"decision": "allow" if allowed else "deny", **({} if allowed else {"reason": REASON})}))
    elif not allowed:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": REASON}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
