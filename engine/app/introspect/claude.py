"""Claude Agent SDK static introspection.

Patterns:
    from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

    @tool("add", "Add two numbers", {"a": float, "b": float})
    async def add(args):
        ...

    server = create_sdk_mcp_server(name="calc", version="1.0.0", tools=[add])

    options = ClaudeAgentOptions(
        system_prompt="You are a calculator assistant.",
        mcp_servers={"calc": server},
        allowed_tools=["mcp__calc__add"],
    )

Tool name/description/input_schema come from the @tool decorator's three
positional args. input_schema may be shorthand ({"a": float}) or a full JSON
schema. system_prompt may be a plain string, a module constant, or a preset
dict with an `append` field. AgentDefinition(prompt=...) is also supported.
"""

from __future__ import annotations

import ast
import os
from typing import Optional

from ..contract import AgentSpec, Framework, ToolSpec
from . import base
from .errors import AgentNotFound

TOOL_DECORATORS = {"tool"}
OPTIONS_CTORS = ["ClaudeAgentOptions", "ClaudeCodeOptions"]  # current + legacy name


def introspect(repo_path: str) -> AgentSpec:
    modules = base.parse_repo(repo_path)
    if not modules:
        raise AgentNotFound("no Python files found in repo", "claude")

    resolver = base.StringResolver().index(modules)

    # Locate the options/agent construction → entry_file + variable name.
    entry_file: Optional[str] = None
    var_name: Optional[str] = None
    options_call: Optional[ast.Call] = None

    for ctor in OPTIONS_CTORS + ["ClaudeSDKClient", "create_sdk_mcp_server"]:
        for mod in modules:
            for node in ast.walk(mod.tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    if base.call_func_name(node.value) == ctor and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        entry_file = os.path.relpath(mod.path, repo_path)
                        if ctor in OPTIONS_CTORS:
                            options_call = node.value
                        break
            if var_name is not None:
                break
        if var_name is not None:
            break

    if var_name is None or entry_file is None:
        raise AgentNotFound(
            "couldn't locate a Claude Agent SDK agent — no ClaudeAgentOptions/"
            "ClaudeSDKClient/create_sdk_mcp_server construction found; specify "
            "the file",
            "claude",
        )

    # --- tools: every @tool-decorated function in the repo ----------------
    tools: list[ToolSpec] = []
    seen: set[str] = set()
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, base.FuncDef):
                call = base.has_decorator(node, TOOL_DECORATORS)
                if call is not None:
                    spec = _tool_spec_from_decorator(node, call)
                    if spec.name not in seen:
                        tools.append(spec)
                        seen.add(spec.name)

    # --- system prompt ----------------------------------------------------
    system_prompt = _extract_system_prompt(modules, options_call, resolver)

    return AgentSpec(
        framework=Framework.claude,
        entry_file=entry_file,
        agent_variable_name=var_name,
        tools=tools,
        system_prompt=system_prompt,
    )


def _tool_spec_from_decorator(fn: ast.AST, call: ast.Call) -> ToolSpec:
    name = fn.name  # type: ignore[attr-defined]
    description = base.docstring_summary(fn) or ""
    params = base.signature_to_params_schema(fn)

    # @tool("name", "description", {schema})
    if len(call.args) >= 1:
        s = base.extract_string(call.args[0])
        if s:
            name = s
    if len(call.args) >= 2:
        s = base.extract_string(call.args[1])
        if s:
            description = s
    if len(call.args) >= 3:
        schema = base.schema_dict_literal_to_params(call.args[2])
        if schema is not None:
            params = schema
    # keyword forms
    for k, setter in (("name", "name"), ("description", "desc"), ("input_schema", "schema")):
        v = base.kwarg(call, k)
        if v is None:
            continue
        if setter == "name":
            s = base.extract_string(v)
            if s:
                name = s
        elif setter == "desc":
            s = base.extract_string(v)
            if s:
                description = s
        else:
            schema = base.schema_dict_literal_to_params(v)
            if schema is not None:
                params = schema

    return ToolSpec(name=name, description=description, params_schema=params)


def _extract_system_prompt(
    modules: list[base.ParsedModule],
    options_call: Optional[ast.Call],
    resolver: base.StringResolver,
) -> Optional[str]:
    candidates: list[str] = []

    def from_system_prompt_value(val: Optional[ast.AST]) -> None:
        if val is None:
            return
        s = resolver.resolve(val)
        if s:
            candidates.append(s)
            return
        # preset dict: {"type": "preset", "preset": "...", "append": "..."}
        if isinstance(val, ast.Dict):
            kv = {
                k.value: v
                for k, v in zip(val.keys, val.values)
                if isinstance(k, ast.Constant)
            }
            if "append" in kv:
                s2 = resolver.resolve(kv["append"])
                if s2:
                    candidates.append(s2)

    if options_call is not None:
        from_system_prompt_value(base.kwarg(options_call, "system_prompt"))

    # AgentDefinition(prompt=...) and any stray ClaudeAgentOptions/system_prompt
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call):
                fname = base.call_func_name(node)
                if fname == "AgentDefinition":
                    from_system_prompt_value(base.kwarg(node, "prompt"))
                elif fname in OPTIONS_CTORS and node is not options_call:
                    from_system_prompt_value(base.kwarg(node, "system_prompt"))

    return _join_prompts(candidates)


def _join_prompts(candidates: list[str]) -> Optional[str]:
    seen: set[str] = set()
    ordered = []
    for c in candidates:
        c = c.strip()
        if c and c not in seen:
            ordered.append(c)
            seen.add(c)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    return "\n\n--- (additional system prompt) ---\n\n".join(ordered)
