"""The Rust ↔ Python contract.

These models are the Pydantic mirror of `orchestrator/src/contract.rs` (serde)
and the JSON shapes documented in `README.md`. All three must stay in sync.

Wire format is snake_case (field names as-is) with enums serialized to their
lowercase string value.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Enums  (str-mixin so they serialize to their lowercase string value)
# ---------------------------------------------------------------------------


class Framework(str, Enum):
    langgraph = "langgraph"
    openai = "openai"
    claude = "claude"


class Category(str, Enum):
    injection = "injection"
    tool_misuse = "tool_misuse"
    goal_hijack = "goal_hijack"
    exfiltration = "exfiltration"
    edge_case = "edge_case"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DetectionMethod(str, Enum):
    tool_call = "tool_call"
    output_contains = "output_contains"
    output_absent = "output_absent"
    error_or_crash = "error_or_crash"
    judge_only = "judge_only"


# ---------------------------------------------------------------------------
# Core shapes
# ---------------------------------------------------------------------------


class ToolSpec(BaseModel):
    name: str
    description: str
    params_schema: dict[str, Any]


class AgentSpec(BaseModel):
    framework: Framework
    entry_file: str
    agent_variable_name: str
    tools: list[ToolSpec]
    system_prompt: Optional[str]


class IntrospectResult(BaseModel):
    """A repo may expose more than one agent/graph (e.g. a retrieval template
    with a separate indexer graph), each with its own tools and prompt. The
    introspection result is therefore a list. Single-agent repos return a
    one-element list. An empty list is never returned — the engine raises
    AgentNotFound (HTTP 422) instead."""

    agents: list[AgentSpec]


class Detection(BaseModel):
    """How a scorer should detect this test's failure from the agent's runtime
    output. `tool_name`/`arg_name`/`arg_pattern`/`needle` use "" when not
    applicable to the chosen method. Transient generate->score data — NOT
    persisted to test_results."""

    method: DetectionMethod
    tool_name: str = ""
    arg_name: str = ""
    arg_pattern: str = ""  # regex; validated to compile at generation time
    needle: str = ""
    rationale: str


class TestCase(BaseModel):
    id: str
    category: Category
    prompt: str
    expected_failure_mode: str
    severity: Severity
    detection: Detection


class RunResult(BaseModel):
    test_case_id: str
    agent_output: str
    tool_calls: list[dict[str, Any]]
    passed: bool
    failure_reason: Optional[str]


# ---------------------------------------------------------------------------
# Engine request/response envelopes
# ---------------------------------------------------------------------------


class IntrospectRequest(BaseModel):
    repo_path: str
    framework: Framework


class GenerateRequest(BaseModel):
    agent_spec: AgentSpec


class GenerateResponse(BaseModel):
    test_cases: list[TestCase]
    # Actual number of LLM API calls made while generating these test cases.
    # The orchestrator reconciles its run-level budget against this real count
    # instead of a fixed estimate. 0 when generated offline (no API key).
    llm_calls: int = 0


class ScoreRequest(BaseModel):
    test_cases: list[TestCase]
    results: list[RunResult]


class ScoreResponse(BaseModel):
    scored: list[RunResult]
    overall_passed: bool
    summary: str
    # Actual number of LLM API calls made while judging (0 while /score is
    # stubbed; ready for when scoring becomes a real LLM judge).
    llm_calls: int = 0
