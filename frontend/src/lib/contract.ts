// TypeScript mirror of the Rust ↔ Python contract (see README.md).
// Kept in sync with orchestrator/src/contract.rs and engine/app/contract.py.

export type Framework = "langgraph" | "openai" | "claude";
export type Category =
  | "injection"
  | "tool_misuse"
  | "goal_hijack"
  | "exfiltration"
  | "edge_case";
export type Severity = "low" | "medium" | "high";

export interface ToolSpec {
  name: string;
  description: string;
  params_schema: Record<string, unknown>;
}

export interface AgentSpec {
  framework: Framework;
  entry_file: string;
  agent_variable_name: string;
  tools: ToolSpec[];
  system_prompt: string | null;
}

// A repo may expose more than one agent/graph, each with its own tools and
// prompt. Introspection returns a list; single-agent repos yield a one-element
// list. Never empty — the engine returns 422 (AgentNotFound) instead.
export interface IntrospectResult {
  agents: AgentSpec[];
}

export type DetectionMethod =
  | "tool_call"
  | "output_contains"
  | "output_absent"
  | "error_or_crash"
  | "judge_only";

// How a scorer detects this test's failure from the agent's runtime output.
// Empty-string fields are "not applicable" for the chosen method. Transient
// generate->score data — not persisted to test_results.
export interface Detection {
  method: DetectionMethod;
  tool_name: string;
  arg_name: string;
  arg_pattern: string;
  needle: string;
  rationale: string;
}

export interface TestCase {
  id: string;
  category: Category;
  prompt: string;
  expected_failure_mode: string;
  severity: Severity;
  detection: Detection;
}

export interface RunResult {
  test_case_id: string;
  agent_output: string;
  tool_calls: Record<string, unknown>[];
  passed: boolean;
  failure_reason: string | null;
  // Set explicitly by the E2B sandbox runner on crash/timeout — never inferred.
  // Read by the `error_or_crash` detection method.
  errored: boolean;
}

// Engine endpoint responses (POST /generate, POST /score). `llm_calls` is the
// actual number of LLM API calls the engine made; the orchestrator reconciles
// its run-level budget against this real count. 0 when run offline (no API key)
// or while an endpoint is still stubbed.
export interface GenerateResponse {
  test_cases: TestCase[];
  llm_calls: number;
}

export interface ScoreResponse {
  scored: RunResult[];
  overall_passed: boolean;
  summary: string;
  llm_calls: number;
}

// Orchestrator API shapes
export interface Run {
  id: string;
  repo_url: string;
  framework: string;
  status: string;
  created_at: string;
  overall_passed: boolean | null;
  summary: { summary?: string } | null;
  // True when the run hit its LLM-call budget and some agents/test-cases were
  // intentionally skipped. `truncated_reason` explains what was dropped.
  truncated: boolean;
  truncated_reason: string | null;
}

export interface TestResultRow {
  id: number;
  run_id: string;
  // Stable "<entry_file>::<agent_variable_name>" id; group results by this in
  // the report UI to separate failures per agent.
  agent_ref: string;
  category: Category;
  severity: Severity;
  attack_prompt: string;
  agent_output: string | null;
  tool_calls: Record<string, unknown>[] | null;
  passed: boolean | null;
  failure_reason: string | null;
}

export interface RunReport {
  run: Run;
  results: TestResultRow[];
}
