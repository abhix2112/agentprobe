"""OpenAI Agents SDK static introspection.

Patterns:
    from agents import Agent, function_tool

    @function_tool
    def get_weather(city: str) -> str:
        '''Get the weather for a city.'''
        ...

    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant.",
        tools=[get_weather],
    )

`instructions` may be a string literal or a reference to a module constant.
The first param of a tool is often an injected `RunContextWrapper` (dropped).
"""

from __future__ import annotations

import ast
import os
from typing import Optional

from ..contract import AgentSpec, Framework, ToolSpec
from . import base
from .errors import AgentNotFound

TOOL_DECORATORS = {"function_tool"}


def introspect(repo_path: str) -> AgentSpec:
    modules = base.parse_repo(repo_path)
    if not modules:
        raise AgentNotFound("no Python files found in repo", "openai")

    resolver = base.StringResolver().index(modules)
    func_index = {}
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, base.FuncDef):
                func_index.setdefault(node.name, node)

    list_assigns = _collect_list_assignments(modules)

    # Locate the Agent(...) construction (prefer the first one found).
    agent_call: Optional[ast.Call] = None
    agent_var: Optional[str] = None
    entry_file: Optional[str] = None
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if base.call_func_name(node.value) == "Agent":
                    agent_call = node.value
                    if isinstance(node.targets[0], ast.Name):
                        agent_var = node.targets[0].id
                    entry_file = os.path.relpath(mod.path, repo_path)
                    break
        if agent_call is not None:
            break

    if agent_call is None or agent_var is None or entry_file is None:
        raise AgentNotFound(
            "couldn't locate an OpenAI Agents SDK agent — no `Agent(...)` "
            "construction found; specify the file",
            "openai",
        )

    # instructions
    instr = base.kwarg(agent_call, "instructions")
    system_prompt = resolver.resolve(instr) if instr is not None else None

    # tools=[...] on the Agent, plus any @function_tool fns it references
    tool_arg = base.kwarg(agent_call, "tools")
    refs = _resolve_tool_arg(tool_arg, list_assigns)

    tools: list[ToolSpec] = []
    seen: set[str] = set()
    for ref in refs:
        fn = func_index.get(ref)
        if fn is None:
            continue
        spec = _tool_spec_from_fn(fn)
        if spec.name not in seen:
            tools.append(spec)
            seen.add(spec.name)

    # Also include @function_tool fns even if not in the tools= list, since
    # some repos register them dynamically.
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, base.FuncDef) and base.has_decorator(node, TOOL_DECORATORS):
                spec = _tool_spec_from_fn(node)
                if spec.name not in seen:
                    tools.append(spec)
                    seen.add(spec.name)

    return AgentSpec(
        framework=Framework.openai,
        entry_file=entry_file,
        agent_variable_name=agent_var,
        tools=tools,
        system_prompt=system_prompt,
    )


def _collect_list_assignments(modules: list[base.ParsedModule]) -> dict[str, list[ast.AST]]:
    out: dict[str, list[ast.AST]] = {}
    for mod in modules:
        for node in mod.tree.body:
            if isinstance(node, ast.Assign) and node.targets:
                if isinstance(node.targets[0], ast.Name) and isinstance(node.value, (ast.List, ast.Tuple)):
                    out[node.targets[0].id] = list(node.value.elts)
    return out


def _resolve_tool_arg(node: Optional[ast.AST], list_assigns: dict[str, list[ast.AST]]) -> list[str]:
    if node is None:
        return []
    if isinstance(node, (ast.List, ast.Tuple)):
        return [n for n in (base.last_name(e) for e in node.elts) if n]
    if isinstance(node, ast.Name) and node.id in list_assigns:
        return [n for n in (base.last_name(e) for e in list_assigns[node.id]) if n]
    return []


def _tool_spec_from_fn(fn: ast.AST) -> ToolSpec:
    call = base.has_decorator(fn, TOOL_DECORATORS)
    name = fn.name  # type: ignore[attr-defined]
    description = base.docstring_summary(fn) or ""
    if call is not None:
        name_kw = base.kwarg(call, "name_override") or base.kwarg(call, "name")
        if name_kw is not None:
            override = base.extract_string(name_kw)
            if override:
                name = override
        desc_kw = base.kwarg(call, "description_override") or base.kwarg(call, "description")
        if desc_kw is not None:
            d = base.extract_string(desc_kw)
            if d:
                description = d
    return ToolSpec(
        name=name,
        description=description,
        params_schema=base.signature_to_params_schema(fn),
    )
