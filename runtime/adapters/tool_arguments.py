"""Shared tool-call items for adapters whose providers name tools instead of typing them.

Only the arguments a reader needs to follow an action (path, line window, pattern, query,
URL) are kept, each bounded, so the timeline can show what a tool touched without
carrying whole tool inputs."""
from __future__ import annotations

from urllib.parse import urlsplit

MAX_ARGUMENT_CHARACTERS = 200
# Provider argument names (compared case-insensitively) -> normalized argument names. The agy
# names are those agy 1.2.16 stream-json reports; it omits line windows and include filters.
ARGUMENT_ALIASES = {
    "file_path": "file_path", "absolutepath": "file_path", "notebook_path": "file_path",
    "path": "path", "directorypath": "path", "searchpath": "path", "searchdirectory": "path",
    "pattern": "pattern", "query": "query", "glob": "glob",
    "url": "url",
    "offset": "offset", "limit": "limit",
}
NUMERIC_ARGUMENTS = {"offset", "limit"}
WEB_SEARCH_TOOLS = {"WebSearch", "search_web"}
WEB_PAGE_TOOLS = {"WebFetch", "read_url_content"}


def summarize_arguments(arguments):
    """Bounded copy of the arguments that identify a tool's target; empty when none apply."""
    if not isinstance(arguments, dict):
        return {}
    summary = {}
    for key, value in arguments.items():
        name = ARGUMENT_ALIASES.get(str(key).lower())
        if not name or name in summary:
            continue
        if name in NUMERIC_ARGUMENTS:
            if type(value) is int and value >= 0:
                summary[name] = value
        elif isinstance(value, str) and value.strip():
            summary[name] = value[:MAX_ARGUMENT_CHARACTERS]
    return summary


def tool_item(identity, server, name, arguments):
    """Runtime item for a provider tool: web tools become web_search, others mcp_tool_call."""
    summary = summarize_arguments(arguments)
    if name in WEB_SEARCH_TOOLS and summary.get("query"):
        return {"id": identity, "type": "web_search", "action": {"type": "search", "query": summary["query"]}}
    if name in WEB_PAGE_TOOLS and summary.get("url") and urlsplit(summary["url"]).scheme in ("http", "https"):
        return {"id": identity, "type": "web_search", "action": {"type": "openPage", "url": summary["url"]}}
    tool = str(name or "")
    if tool.startswith("mcp__") and tool.count("__") >= 2:
        # Claude names connected MCP tools mcp__<server>__<tool>.
        server, tool = tool[5:].split("__", 1)
    item = {"id": identity, "type": "mcp_tool_call", "server": server, "tool": tool}
    if summary:
        item["arguments"] = summary
    return item
