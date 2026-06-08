"""LangGraph agent runner — executed INSIDE the sandbox (or as a local
subprocess). It imports the target agent described by an AgentSpec, invokes it
with one attack prompt, and prints a single JSON line capturing the result:

    {"output": <str>, "tool_calls": [{"name","args"}...], "error": <str|null>}

Usage:
    python langgraph_runner.py <repo_path> <entry_file> <agent_variable_name>
    # the attack prompt is read from STDIN (avoids arg-escaping issues)

Contract with the orchestrator: this script ALWAYS exits 0 and prints one JSON
line. If the agent raises, `error` is set (and the orchestrator marks the
RunResult errored). A hard crash / timeout (no parseable JSON) is detected by
the orchestrator instead.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys


def _load_agent(repo_path: str, entry_file: str, variable: str):
    """Import `variable` from `entry_file` inside `repo_path`, handling both
    package layouts (src/pkg/graph.py with __init__.py) and single files."""
    entry_abs = os.path.abspath(os.path.join(repo_path, entry_file))
    pkg_dir = os.path.dirname(entry_abs)
    parts = [os.path.splitext(os.path.basename(entry_abs))[0]]
    # Walk up while the directory is a package, building the dotted module name.
    while os.path.isfile(os.path.join(pkg_dir, "__init__.py")):
        parts.insert(0, os.path.basename(pkg_dir))
        pkg_dir = os.path.dirname(pkg_dir)
    sys.path.insert(0, pkg_dir)
    module = importlib.import_module(".".join(parts))
    return getattr(module, variable)


def _collect_tool_calls(messages) -> list:
    calls = []
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            # tc is a dict-like {name, args, id, ...}
            calls.append({"name": tc.get("name"), "args": tc.get("args", {})})
    return calls


def _final_output(messages) -> str:
    for m in reversed(messages):
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            return content
    return ""


def main() -> None:
    result = {"output": "", "tool_calls": [], "error": None}
    try:
        repo_path, entry_file, variable = sys.argv[1], sys.argv[2], sys.argv[3]
        prompt = sys.stdin.read()
        agent = _load_agent(repo_path, entry_file, variable)
        inp = {"messages": [{"role": "user", "content": prompt}]}
        # Use the ASYNC API: real LangGraph agents commonly have `async def`
        # nodes (e.g. the official react-agent's `call_model`), which raise on a
        # synchronous .invoke(). ainvoke also handles purely-sync graphs.
        #
        # Agents on the newer LangGraph Runtime API read config from
        # `runtime.context` (e.g. react-agent's model/system_prompt); invoking
        # without a context makes `runtime.context` None -> AttributeError.
        # Passing context={} supplies the context_schema's defaults. Older
        # graphs (no context= kwarg) raise TypeError -> fall back.
        try:
            state = asyncio.run(agent.ainvoke(inp, context={}))
        except TypeError:
            state = asyncio.run(agent.ainvoke(inp))
        messages = state["messages"] if isinstance(state, dict) else state
        result["output"] = _final_output(messages)
        result["tool_calls"] = _collect_tool_calls(messages)
    except Exception as exc:  # noqa: BLE001 — any agent failure is a reportable result
        result["error"] = f"{type(exc).__name__}: {exc}"
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    # The agent-under-test reads ANTHROPIC_API_KEY (and any other secrets, e.g.
    # TAVILY_API_KEY) from the environment inherited from the orchestrator/
    # sandbox subprocess. We deliberately do NOT default the key to "" — a
    # missing key must surface as a real auth error, not be silently masked.
    main()
