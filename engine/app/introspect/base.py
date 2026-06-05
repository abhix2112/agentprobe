"""Shared, framework-agnostic AST helpers for static agent introspection.

Hard rule: we NEVER import or execute cloned repo code. Everything here works
on the `ast` tree produced by `ast.parse`, which only reads source text.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

# Annotations that mean "this parameter is injected by the framework at runtime
# and is NOT part of the schema the model sees." Used to drop hidden tool args.
INJECTED_TYPE_NAMES = {
    "InjectedToolArg",
    "InjectedState",
    "InjectedStore",
    "RunnableConfig",
    "RunContextWrapper",
    "ToolContext",
    "BaseStore",
}

# Directories we never descend into while scanning a repo.
SKIP_DIRS = {
    ".git", ".hg", ".venv", "venv", "env", "__pycache__", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache", "site-packages",
}


# ---------------------------------------------------------------------------
# File discovery & parsing
# ---------------------------------------------------------------------------


@dataclass
class ParsedModule:
    path: str
    tree: ast.Module
    source: str


def iter_python_files(root: str) -> Iterator[str]:
    """Yield .py files under `root`, skipping vendored/irrelevant dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def parse_module(path: str) -> Optional[ParsedModule]:
    """Parse one file. Returns None on read/syntax error (never raises)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        return ParsedModule(path=path, tree=ast.parse(source), source=source)
    except (OSError, SyntaxError, ValueError):
        return None


def parse_repo(root: str) -> list[ParsedModule]:
    mods = []
    for p in iter_python_files(root):
        m = parse_module(p)
        if m is not None:
            mods.append(m)
    return mods


# ---------------------------------------------------------------------------
# Names, calls, decorators
# ---------------------------------------------------------------------------


def dotted_name(node: ast.AST) -> Optional[str]:
    """`foo` -> 'foo', `a.b.c` -> 'a.b.c'. None if not a name/attribute."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def last_name(node: ast.AST) -> Optional[str]:
    """Trailing identifier: `tools.upsert_memory` -> 'upsert_memory'."""
    dn = dotted_name(node)
    return dn.split(".")[-1] if dn else None


def call_func_name(call: ast.Call) -> Optional[str]:
    """Trailing identifier of a call target: `StateGraph(...)` -> 'StateGraph',
    `builder.compile()` -> 'compile'."""
    return last_name(call.func)


FuncDef = (ast.FunctionDef, ast.AsyncFunctionDef)


def decorator_calls(fn: ast.AST) -> list[tuple[str, Optional[ast.Call]]]:
    """For a function def, return (decorator_name, call_or_None) for each
    decorator. `@tool` -> ('tool', None); `@tool("x")` -> ('tool', <Call>)."""
    out: list[tuple[str, Optional[ast.Call]]] = []
    for dec in getattr(fn, "decorator_list", []):
        if isinstance(dec, ast.Call):
            name = last_name(dec.func)
            if name:
                out.append((name, dec))
        else:
            name = last_name(dec)
            if name:
                out.append((name, None))
    return out


def has_decorator(fn: ast.AST, names: set[str]) -> Optional[ast.Call]:
    for name, call in decorator_calls(fn):
        if name in names:
            return call if call is not None else ast.Call(func=ast.Name(id=name), args=[], keywords=[])
    return None


def kwarg(call: ast.Call, name: str) -> Optional[ast.AST]:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def list_elements(node: Optional[ast.AST]) -> list[ast.AST]:
    """Elements of a list/tuple literal, else []."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return list(node.elts)
    return []


# ---------------------------------------------------------------------------
# String literal extraction (incl. simple f-strings and concatenation)
# ---------------------------------------------------------------------------


def extract_string(node: Optional[ast.AST]) -> Optional[str]:
    """Best-effort static string value. Handles plain literals, implicit/`+`
    concatenation, and f-strings (format fields rendered as `{...}`)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f-string
        parts: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                parts.append("{" + (last_name(v.value) or "...") + "}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = extract_string(node.left)
        right = extract_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


# ---------------------------------------------------------------------------
# Cross-file string resolver: module constants + dataclass field defaults
# ---------------------------------------------------------------------------


class StringResolver:
    """Resolves identifiers to string literals across a whole package.

    Captures two real-world indirections seen in LangGraph templates:
      1. module-level  `SYSTEM_PROMPT = "..."`
      2. dataclass     `system_prompt: str = field(default=prompts.SYSTEM_PROMPT)`
    """

    def __init__(self) -> None:
        # simple name -> string literal
        self.constants: dict[str, str] = {}
        # dataclass field name -> string (resolved through field default)
        self.fields: dict[str, str] = {}

    def index(self, modules: list[ParsedModule]) -> "StringResolver":
        # Pass 1: module-level string constants.
        for mod in modules:
            for node in mod.tree.body:
                if isinstance(node, ast.Assign):
                    s = extract_string(node.value)
                    if s is not None:
                        for tgt in node.targets:
                            if isinstance(tgt, ast.Name):
                                self.constants[tgt.id] = s
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    s = extract_string(node.value)
                    if s is not None:
                        self.constants[node.target.id] = s
        # Pass 2: dataclass fields (defaults may reference pass-1 constants).
        for mod in modules:
            for node in ast.walk(mod.tree):
                if isinstance(node, ast.ClassDef):
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            val = self._resolve_field_default(stmt.value)
                            if val is not None:
                                self.fields[stmt.target.id] = val
        return self

    def _resolve_field_default(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return None
        # direct literal
        s = extract_string(node)
        if s is not None:
            return s
        # `field(default=...)` / `field(default_factory=lambda: "...")`
        if isinstance(node, ast.Call) and last_name(node.func) == "field":
            default = kwarg(node, "default")
            return self.resolve(default) if default is not None else None
        # bare reference to a constant: `prompts.SYSTEM_PROMPT` or `SYSTEM_PROMPT`
        return self.resolve(node)

    def resolve(self, node: Optional[ast.AST]) -> Optional[str]:
        """Resolve an expression to a string if statically possible."""
        if node is None:
            return None
        s = extract_string(node)
        if s is not None:
            return s
        name = last_name(node)  # handles `prompts.SYSTEM_PROMPT` -> 'SYSTEM_PROMPT'
        if name and name in self.constants:
            return self.constants[name]
        if name and name in self.fields:
            return self.fields[name]
        return None


# ---------------------------------------------------------------------------
# Function signature -> JSON-schema-like params_schema
# ---------------------------------------------------------------------------


def _is_injected_annotation(ann: Optional[ast.AST]) -> bool:
    if ann is None:
        return False
    name = last_name(ann)
    if name in INJECTED_TYPE_NAMES:
        return True
    # Annotated[T, InjectedToolArg] / Annotated[T, InjectedToolArg()]
    if isinstance(ann, ast.Subscript) and last_name(ann.value) == "Annotated":
        meta = ann.slice
        elts = meta.elts if isinstance(meta, ast.Tuple) else [meta]
        for e in elts[1:]:  # elts[0] is the real type
            if last_name(e) in INJECTED_TYPE_NAMES:
                return True
    return False


def annotation_to_schema(ann: Optional[ast.AST]) -> tuple[dict[str, Any], bool]:
    """Map a type annotation to a JSON-schema fragment.

    Returns (schema, is_optional). `is_optional` is True for Optional[T] / `T |
    None`, which makes the param non-required even without a default.
    """
    scalar = {
        "str": "string", "int": "integer", "float": "number",
        "bool": "boolean", "bytes": "string",
    }
    if ann is None:
        return {}, False

    if isinstance(ann, ast.Name):
        t = scalar.get(ann.id)
        if t:
            return {"type": t}, False
        if ann.id in {"list", "List"}:
            return {"type": "array"}, False
        if ann.id in {"dict", "Dict"}:
            return {"type": "object"}, False
        return {}, False

    if isinstance(ann, ast.Constant) and ann.value is None:
        return {}, True

    if isinstance(ann, ast.Subscript):
        head = last_name(ann.value)
        inner = ann.slice
        elts = inner.elts if isinstance(inner, ast.Tuple) else [inner]
        if head == "Optional":
            schema, _ = annotation_to_schema(elts[0])
            return schema, True
        if head == "Annotated":
            return annotation_to_schema(elts[0])
        if head in {"List", "list", "Sequence", "Iterable", "tuple", "Tuple"}:
            item_schema, _ = annotation_to_schema(elts[0]) if elts else ({}, False)
            out: dict[str, Any] = {"type": "array"}
            if item_schema:
                out["items"] = item_schema
            return out, False
        if head in {"Dict", "dict", "Mapping"}:
            return {"type": "object"}, False
        return {}, False

    # `str | None` (PEP 604)
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        left, lopt = annotation_to_schema(ann.left)
        right, ropt = annotation_to_schema(ann.right)
        none_on_right = isinstance(ann.right, ast.Constant) and ann.right.value is None
        none_on_left = isinstance(ann.left, ast.Constant) and ann.left.value is None
        if none_on_right:
            return left, True
        if none_on_left:
            return right, True
        return (left or right), (lopt or ropt)

    return {}, False


def signature_to_params_schema(fn: ast.AST) -> dict[str, Any]:
    """Turn a function def's signature into a JSON-schema `object`.

    Skips injected/hidden params (InjectedToolArg etc.) and the conventional
    self/cls/ctx leading params. Params without a default (and not Optional)
    are marked required.
    """
    args = fn.args  # type: ignore[attr-defined]
    properties: dict[str, Any] = {}
    required: list[str] = []

    # Build a (arg, default, keyword_only) work list.
    posonly = list(getattr(args, "posonlyargs", []))
    pos = list(args.args)
    all_positional = posonly + pos
    pos_defaults = list(args.defaults)
    # defaults align to the TAIL of all_positional
    default_for: dict[int, ast.AST] = {}
    if pos_defaults:
        offset = len(all_positional) - len(pos_defaults)
        for i, d in enumerate(pos_defaults):
            default_for[offset + i] = d

    items: list[tuple[ast.arg, Optional[ast.AST], bool]] = []
    for i, a in enumerate(all_positional):
        items.append((a, default_for.get(i), False))
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        items.append((a, d, True))

    for idx, (a, default, _kwonly) in enumerate(items):
        name = a.arg
        if idx == 0 and name in {"self", "cls", "ctx", "context_wrapper", "wrapper"}:
            # leading framework/context handle (but NOT a real param named 'context')
            if name != "context":
                continue
        if _is_injected_annotation(a.annotation):
            continue
        schema, optional = annotation_to_schema(a.annotation)
        properties[name] = schema if schema else {}
        if default is None and not optional:
            required.append(name)

    out: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        out["required"] = required
    return out


def docstring_summary(fn: ast.AST) -> Optional[str]:
    """First paragraph of a function's docstring, whitespace-collapsed."""
    doc = ast.get_docstring(fn)
    if not doc:
        return None
    first = doc.strip().split("\n\n")[0]
    return " ".join(first.split())


def schema_dict_literal_to_params(node: Optional[ast.AST]) -> Optional[dict[str, Any]]:
    """Convert a dict literal used as a tool input schema into params_schema.

    Accepts BOTH forms used by the Claude Agent SDK:
      - shorthand  {"a": float, "b": float}     -> typed properties
      - full JSON schema  {"type": "object", "properties": {...}}  -> passthrough
    """
    if not isinstance(node, ast.Dict):
        return None
    # Detect an already-formed JSON schema.
    keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
    if "type" in keys or "properties" in keys:
        return _literal_to_py(node)  # passthrough best-effort
    properties: dict[str, Any] = {}
    required: list[str] = []
    for k, v in zip(node.keys, node.values):
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
            continue
        schema, optional = annotation_to_schema(v)
        properties[k.value] = schema if schema else {}
        if not optional:
            required.append(k.value)
    out: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        out["required"] = required
    return out


def _literal_to_py(node: ast.AST) -> Any:
    """Best-effort conversion of a literal AST (dict/list/str/num/bool/None)."""
    try:
        return ast.literal_eval(node)  # safe: only literals, no execution
    except (ValueError, SyntaxError, TypeError):
        # Fall back to a shallow walk for dicts containing type names.
        if isinstance(node, ast.Dict):
            d: dict[str, Any] = {}
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant):
                    d[k.value] = _literal_to_py(v)
            return d
        if isinstance(node, ast.Constant):
            return node.value
        name = last_name(node)
        return name or None
