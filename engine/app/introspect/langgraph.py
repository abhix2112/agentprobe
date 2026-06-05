"""LangGraph static introspection.

Handles the patterns confirmed in the official templates (react-agent,
memory-agent, retrieval-agent-template):

  - entrypoint declared in langgraph.json  ("file.py:variable")
  - StateGraph(...).compile()  and  prebuilt create_react_agent(...)
  - tools as: a module-level TOOLS list, an inline bind_tools([...]) list,
    ToolNode(...), create_react_agent(tools=...), or @tool-decorated fns
  - system prompt indirected through dataclass field defaults / prompt
    constants / ChatPromptTemplate ("system", ...) tuples
"""

from __future__ import annotations

import ast
import json
import os
from typing import Any, Optional

from ..contract import AgentSpec, Framework, ToolSpec
from . import base
from .errors import AgentNotFound

GRAPH_CTORS = {"StateGraph", "create_react_agent", "MessageGraph"}
TOOL_DECORATORS = {"tool"}


def introspect(repo_path: str) -> AgentSpec:
    modules = base.parse_repo(repo_path)
    if not modules:
        raise AgentNotFound("no Python files found in repo", "langgraph")

    by_path = {m.path: m for m in modules}
    resolver = base.StringResolver().index(modules)

    # --- entry_file + agent_variable_name ---------------------------------
    entry_file, var_name = _locate_entrypoint(repo_path, modules, by_path)

    # --- index module-level list assignments (for TOOLS = [...]) ----------
    list_assigns = _collect_list_assignments(modules)
    func_index = _collect_functions(modules)

    # --- tools ------------------------------------------------------------
    tool_refs = _collect_tool_references(modules, list_assigns)
    decorated = _collect_decorated_tools(modules)

    tools: list[ToolSpec] = []
    seen: set[str] = set()
    # Decorator-defined tools first (richest metadata), then referenced fns.
    for fn, call in decorated:
        spec = _tool_spec_from_fn(fn, call)
        if spec.name not in seen:
            tools.append(spec)
            seen.add(spec.name)
    for ref in tool_refs:
        fn = func_index.get(ref)
        if fn is None:
            continue
        call = base.has_decorator(fn, TOOL_DECORATORS)
        spec = _tool_spec_from_fn(fn, call)
        if spec.name not in seen:
            tools.append(spec)
            seen.add(spec.name)

    # --- system prompt ----------------------------------------------------
    system_prompt = _extract_system_prompt(modules, resolver)

    return AgentSpec(
        framework=Framework.langgraph,
        entry_file=entry_file,
        agent_variable_name=var_name,
        tools=tools,
        system_prompt=system_prompt,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _locate_entrypoint(
    repo_path: str, modules: list[base.ParsedModule], by_path: dict[str, base.ParsedModule]
) -> tuple[str, str]:
    # 1. langgraph.json is authoritative.
    cfg = os.path.join(repo_path, "langgraph.json")
    if os.path.isfile(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            graphs = data.get("graphs", {})
            for _name, target in graphs.items():
                # "./src/pkg/graph.py:graph"
                rel, _, var = str(target).partition(":")
                rel = rel.lstrip("./")
                abspath = os.path.join(repo_path, rel)
                if os.path.isfile(abspath) and var:
                    return rel, var
        except (OSError, ValueError):
            pass

    # 2. Fall back to scanning for `X = create_react_agent(...)` / `.compile()`.
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                fname = base.call_func_name(node.value)
                if fname == "create_react_agent" or fname == "compile":
                    if node.targets and isinstance(node.targets[0], ast.Name):
                        rel = os.path.relpath(mod.path, repo_path)
                        return rel, node.targets[0].id

    raise AgentNotFound(
        "couldn't locate a LangGraph agent — no langgraph.json and no "
        "create_react_agent(...)/compile() assignment found; specify the file",
        "langgraph",
    )


# ---------------------------------------------------------------------------
# Tool collection
# ---------------------------------------------------------------------------


def _collect_functions(modules: list[base.ParsedModule]) -> dict[str, ast.AST]:
    index: dict[str, ast.AST] = {}
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, base.FuncDef):
                index.setdefault(node.name, node)
    return index


def _collect_list_assignments(modules: list[base.ParsedModule]) -> dict[str, list[ast.AST]]:
    out: dict[str, list[ast.AST]] = {}
    for mod in modules:
        for node in mod.tree.body:
            target = None
            value = None
            if isinstance(node, ast.Assign) and node.targets:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            if isinstance(target, ast.Name) and isinstance(value, (ast.List, ast.Tuple)):
                out[target.id] = list(value.elts)
    return out


def _resolve_tool_arg(node: Optional[ast.AST], list_assigns: dict[str, list[ast.AST]]) -> list[str]:
    """A tools argument -> list of referenced function names."""
    if node is None:
        return []
    if isinstance(node, (ast.List, ast.Tuple)):
        return [n for n in (base.last_name(e) for e in node.elts) if n]
    if isinstance(node, ast.Name) and node.id in list_assigns:
        return [n for n in (base.last_name(e) for e in list_assigns[node.id]) if n]
    return []


def _collect_tool_references(
    modules: list[base.ParsedModule], list_assigns: dict[str, list[ast.AST]]
) -> list[str]:
    refs: list[str] = []
    for mod in modules:
        for node in ast.walk(mod.tree):
            if not isinstance(node, ast.Call):
                continue
            fname = base.call_func_name(node)
            if fname == "bind_tools":
                refs += _resolve_tool_arg(node.args[0] if node.args else None, list_assigns)
            elif fname == "ToolNode":
                refs += _resolve_tool_arg(node.args[0] if node.args else None, list_assigns)
            elif fname == "create_react_agent":
                arg = base.kwarg(node, "tools")
                if arg is None and len(node.args) >= 2:
                    arg = node.args[1]
                refs += _resolve_tool_arg(arg, list_assigns)
    # de-dupe, preserve order
    seen: set[str] = set()
    ordered = []
    for r in refs:
        if r not in seen:
            ordered.append(r)
            seen.add(r)
    return ordered


def _collect_decorated_tools(modules: list[base.ParsedModule]) -> list[tuple[ast.AST, Optional[ast.Call]]]:
    out = []
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, base.FuncDef):
                call = base.has_decorator(node, TOOL_DECORATORS)
                if call is not None:
                    out.append((node, call))
    return out


def _tool_spec_from_fn(fn: ast.AST, dec_call: Optional[ast.Call]) -> ToolSpec:
    name = fn.name  # type: ignore[attr-defined]
    description = base.docstring_summary(fn) or ""
    if dec_call is not None:
        # @tool("name", description="...")
        if dec_call.args:
            override = base.extract_string(dec_call.args[0])
            if override:
                name = override
        desc_kw = base.kwarg(dec_call, "description")
        if desc_kw is not None:
            d = base.extract_string(desc_kw)
            if d:
                description = d
    return ToolSpec(
        name=name,
        description=description,
        params_schema=base.signature_to_params_schema(fn),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def _extract_system_prompt(
    modules: list[base.ParsedModule], resolver: base.StringResolver
) -> Optional[str]:
    candidates: list[str] = []

    for mod in modules:
        for node in ast.walk(mod.tree):
            if not isinstance(node, ast.Call):
                continue
            fname = base.call_func_name(node)

            # ChatPromptTemplate.from_messages([("system", X), ...])
            if fname == "from_messages":
                for arg in node.args:
                    for elt in base.list_elements(arg):
                        if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                            role = base.extract_string(elt.elts[0])
                            if role == "system":
                                s = resolver.resolve(elt.elts[1])
                                if s:
                                    candidates.append(s)

            # create_react_agent(prompt=... / state_modifier=...)
            if fname == "create_react_agent":
                for key in ("prompt", "state_modifier", "messages_modifier"):
                    val = base.kwarg(node, key)
                    if val is not None:
                        s = resolver.resolve(val)
                        if s:
                            candidates.append(s)

            # {"role": "system", "content": X}
            if isinstance(node, ast.Call):
                pass  # (dict literals handled below)

        # dict literals {"role": "system", "content": X}
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Dict):
                kv = {
                    k.value: v
                    for k, v in zip(node.keys, node.values)
                    if isinstance(k, ast.Constant)
                }
                if kv.get("role") is not None:
                    role = base.extract_string(kv["role"])
                    if role == "system" and "content" in kv:
                        s = resolver.resolve(kv["content"])
                        if s:
                            candidates.append(s)

    # dataclass field default named system_prompt (react-agent / memory-agent)
    if "system_prompt" in resolver.fields:
        candidates.append(resolver.fields["system_prompt"])
    # any *_system_prompt fields (retrieval-agent-template has two)
    for fname, val in resolver.fields.items():
        if fname.endswith("system_prompt") and fname != "system_prompt":
            candidates.append(val)
    # bare SYSTEM_PROMPT constants as a last resort
    for cname, val in resolver.constants.items():
        if cname.endswith("SYSTEM_PROMPT"):
            candidates.append(val)

    return _dedupe_join(candidates)


def _dedupe_join(candidates: list[str]) -> Optional[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        c = c.strip()
        if c and c not in seen:
            ordered.append(c)
            seen.add(c)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    # Single-string contract: join multiple prompts with a clear separator.
    return "\n\n--- (additional system prompt) ---\n\n".join(ordered)
