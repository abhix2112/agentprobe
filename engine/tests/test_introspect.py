"""Extraction tests for the static introspection engine.

Run from engine/:  pytest -q
"""

from __future__ import annotations

import os

import pytest

from app.contract import Framework
from app.introspect import AgentNotFound, introspect

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(framework: str, name: str) -> str:
    return os.path.join(FIXTURES, framework, name)


def only_agent(framework, path):
    """Introspect a single-agent fixture and return its one AgentSpec."""
    result = introspect(path, framework)
    assert len(result.agents) == 1, "single-agent fixture should yield exactly one"
    return result.agents[0]


def tools_by_name(spec) -> dict:
    return {t.name: t for t in spec.tools}


# ---------------------------------------------------------------------------
# LangGraph
# ---------------------------------------------------------------------------


def test_langgraph_react_search():
    spec = only_agent(Framework.langgraph, fx("langgraph", "react_search"))
    assert spec.framework == Framework.langgraph
    # entrypoint comes from langgraph.json
    assert spec.entry_file == "src/react_search/graph.py"
    assert spec.agent_variable_name == "graph"

    tools = tools_by_name(spec)
    assert set(tools) == {"search", "fetch_url"}
    # bare-function tool: schema inferred from signature
    assert tools["search"].params_schema["properties"]["query"] == {"type": "string"}
    assert tools["search"].params_schema["required"] == ["query"]
    # optional param is not required
    assert "max_results" not in tools["search"].params_schema.get("required", [])
    assert "research assistant" in (spec.system_prompt or "")


def test_langgraph_memory_injected_excludes_injected_args():
    spec = only_agent(Framework.langgraph, fx("langgraph", "memory_injected"))
    tools = tools_by_name(spec)
    assert set(tools) == {"upsert_memory"}
    props = tools["upsert_memory"].params_schema["properties"]
    # InjectedToolArg params must be hidden from the model
    assert "user_id" not in props
    assert "store" not in props
    assert set(props) == {"content", "context", "memory_id"}
    assert set(tools["upsert_memory"].params_schema["required"]) == {"content", "context"}
    assert "long-term memory" in (spec.system_prompt or "")


def test_langgraph_create_react_agent_not_confused_by_re_compile():
    # The e2e react_fake agent has a module-level `_PATH_RE = re.compile(...)`;
    # the entrypoint scan must pick `graph = create_react_agent(...)`, not the
    # regex (the `.compile()` heuristic must not match `re.compile`).
    e2e = os.path.join(os.path.dirname(__file__), "e2e", "react_fake")
    spec = introspect(e2e, Framework.langgraph).agents[0]
    assert spec.agent_variable_name == "graph"
    assert spec.entry_file == "agent.py"
    assert {t.name for t in spec.tools} == {"read_file"}


def test_langgraph_prebuilt_calc_fallback_no_config():
    # No langgraph.json -> falls back to scanning for create_react_agent(...)
    spec = only_agent(Framework.langgraph, fx("langgraph", "prebuilt_calc"))
    assert spec.entry_file == "agent.py"
    assert spec.agent_variable_name == "graph"
    tools = tools_by_name(spec)
    assert set(tools) == {"add", "multiply", "power"}
    # name override from @tool("multiply", ...)
    assert "multiply" in tools
    # description override from decorator kwarg
    assert tools["multiply"].description == "Multiply two numbers together."
    # default value -> optional
    assert "exponent" not in tools["power"].params_schema.get("required", [])
    assert spec.system_prompt == "You are a precise calculator. Show each step of your work."


# ---------------------------------------------------------------------------
# OpenAI Agents SDK
# ---------------------------------------------------------------------------


def test_openai_weather():
    spec = only_agent(Framework.openai, fx("openai", "weather"))
    assert spec.framework == Framework.openai
    assert spec.entry_file == "agent.py"
    assert spec.agent_variable_name == "agent"
    tools = tools_by_name(spec)
    assert set(tools) == {"get_weather", "get_forecast"}
    assert tools["get_weather"].params_schema["required"] == ["city"]
    assert "units" not in tools["get_weather"].params_schema.get("required", [])
    assert "weather assistant" in (spec.system_prompt or "").lower()


def test_openai_support_ctx_excludes_run_context():
    spec = only_agent(Framework.openai, fx("openai", "support_ctx"))
    assert spec.agent_variable_name == "support_agent"
    tools = tools_by_name(spec)
    # @function_tool(name_override="issue_refund")
    assert set(tools) == {"lookup_order", "issue_refund"}
    # injected RunContextWrapper leading arg dropped
    assert "ctx" not in tools["lookup_order"].params_schema["properties"]
    assert tools["lookup_order"].params_schema["required"] == ["order_id"]
    assert set(tools["issue_refund"].params_schema["properties"]) == {"order_id", "amount"}
    # instructions resolved from a module constant
    assert "customer support" in (spec.system_prompt or "")


# ---------------------------------------------------------------------------
# Claude Agent SDK
# ---------------------------------------------------------------------------


def test_claude_calculator_shorthand_schema():
    spec = only_agent(Framework.claude, fx("claude", "calculator"))
    assert spec.framework == Framework.claude
    assert spec.agent_variable_name == "options"
    tools = tools_by_name(spec)
    assert set(tools) == {"add", "divide"}
    # shorthand {"a": float, "b": float} -> typed JSON schema
    assert tools["add"].params_schema["properties"]["a"] == {"type": "number"}
    assert set(tools["add"].params_schema["required"]) == {"a", "b"}
    # description from decorator, not docstring
    assert tools["add"].description == "Add two numbers and return the sum"
    assert "calculator assistant" in (spec.system_prompt or "")


def test_claude_file_ops_full_json_schema():
    spec = only_agent(Framework.claude, fx("claude", "file_ops"))
    tools = tools_by_name(spec)
    assert set(tools) == {"read_file", "write_file"}
    # full JSON schema passed through verbatim
    wf = tools["write_file"].params_schema
    assert wf["properties"]["overwrite"] == {"type": "boolean"}
    assert wf["required"] == ["path", "contents"]
    # system prompt resolved from module constant
    assert "filesystem assistant" in (spec.system_prompt or "")


# ---------------------------------------------------------------------------
# No agent -> 422-worthy error
# ---------------------------------------------------------------------------


def test_no_agent_raises_agent_not_found():
    with pytest.raises(AgentNotFound):
        introspect(fx("empty", ""), Framework.langgraph)


def test_introspect_endpoint_returns_422():
    """The HTTP layer maps AgentNotFound -> 422 with a clear message."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/introspect",
        json={"repo_path": fx("empty", ""), "framework": "langgraph"},
    )
    assert resp.status_code == 422
    assert "couldn't locate" in resp.json()["detail"]


def test_introspect_endpoint_returns_agents_container():
    """A valid repo returns {"agents": [AgentSpec, ...]} over HTTP."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/introspect",
        json={"repo_path": fx("openai", "weather"), "framework": "openai"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert list(body.keys()) == ["agents"]
    assert len(body["agents"]) == 1
    assert body["agents"][0]["agent_variable_name"] == "agent"
