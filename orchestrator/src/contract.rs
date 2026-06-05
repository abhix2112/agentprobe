//! The Rust ↔ Python contract.
//!
//! These types are the serde mirror of `engine/app/contract.py` (Pydantic) and
//! the JSON shapes documented in `README.md`. All three must stay in sync.
//!
//! Wire format is `snake_case` (field names as-is) with enums serialized to
//! their lowercase string value.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Framework {
    Langgraph,
    Openai,
    Claude,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Category {
    Injection,
    ToolMisuse,
    GoalHijack,
    Exfiltration,
    EdgeCase,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DetectionMethod {
    ToolCall,
    OutputContains,
    OutputAbsent,
    ErrorOrCrash,
    JudgeOnly,
}

// ---------------------------------------------------------------------------
// Core shapes
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    /// Free-form JSON Schema object.
    pub params_schema: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSpec {
    pub framework: Framework,
    pub entry_file: String,
    pub agent_variable_name: String,
    pub tools: Vec<ToolSpec>,
    pub system_prompt: Option<String>,
}

/// A repo may expose more than one agent/graph, each with its own tools and
/// prompt. Introspection therefore returns a list; single-agent repos yield a
/// one-element list. The list is never empty — the engine returns 422
/// (AgentNotFound) instead.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntrospectResult {
    pub agents: Vec<AgentSpec>,
}

/// How a scorer detects this test's failure from the agent's runtime output.
/// Empty-string fields are "not applicable" for the chosen method. Transient
/// generate->score data — NOT persisted to `test_results`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Detection {
    pub method: DetectionMethod,
    #[serde(default)]
    pub tool_name: String,
    #[serde(default)]
    pub arg_name: String,
    #[serde(default)]
    pub arg_pattern: String,
    #[serde(default)]
    pub needle: String,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestCase {
    pub id: String,
    pub category: Category,
    pub prompt: String,
    pub expected_failure_mode: String,
    pub severity: Severity,
    pub detection: Detection,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunResult {
    pub test_case_id: String,
    pub agent_output: String,
    /// Array of free-form tool-call objects.
    pub tool_calls: Vec<serde_json::Value>,
    pub passed: bool,
    pub failure_reason: Option<String>,
}

// ---------------------------------------------------------------------------
// Engine request/response envelopes
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntrospectRequest {
    pub repo_path: String,
    pub framework: Framework,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerateRequest {
    pub agent_spec: AgentSpec,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerateResponse {
    pub test_cases: Vec<TestCase>,
    /// Actual number of LLM API calls made while generating these test cases.
    /// The orchestrator reconciles its run-level budget against this real count
    /// instead of a fixed estimate. 0 when generated offline (no API key).
    #[serde(default)]
    pub llm_calls: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreRequest {
    pub test_cases: Vec<TestCase>,
    pub results: Vec<RunResult>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreResponse {
    pub scored: Vec<RunResult>,
    pub overall_passed: bool,
    pub summary: String,
    /// Actual number of LLM API calls made while judging (0 while /score is
    /// stubbed; ready for when scoring becomes a real LLM judge).
    #[serde(default)]
    pub llm_calls: u32,
}
