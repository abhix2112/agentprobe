mod contract;
mod engine;

use std::time::Duration;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;
use uuid::Uuid;

use crate::contract::{Framework, Severity};
use crate::engine::EngineClient;

#[derive(Clone)]
struct AppState {
    db: PgPool,
    engine: EngineClient,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,orchestrator=debug".into()),
        )
        .init();

    let database_url =
        std::env::var("DATABASE_URL").unwrap_or_else(|_| "postgres://agentprobe:agentprobe@postgres:5432/agentprobe".into());
    let engine_url = std::env::var("ENGINE_URL").unwrap_or_else(|_| "http://engine:8000".into());

    let db = PgPoolOptions::new()
        .max_connections(5)
        .acquire_timeout(Duration::from_secs(10))
        .connect(&database_url)
        .await?;

    // Apply migrations on boot.
    sqlx::migrate!("../migrations").run(&db).await?;

    let state = AppState {
        db,
        engine: EngineClient::new(engine_url),
    };

    let app = Router::new()
        .route("/health", get(health))
        .route("/runs", post(create_run))
        .route("/runs/:id", get(get_run))
        .with_state(state)
        .layer(CorsLayer::permissive())
        .layer(TraceLayer::new_for_http());

    let addr = "0.0.0.0:8080";
    tracing::info!("orchestrator listening on {addr}");
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}

async fn health() -> &'static str {
    "ok"
}

// ---------------------------------------------------------------------------
// POST /runs — kick off a probe run
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct CreateRunRequest {
    repo_url: String,
    framework: Framework,
}

#[derive(Debug, Serialize)]
struct CreateRunResponse {
    id: Uuid,
    status: String,
}

async fn create_run(
    State(state): State<AppState>,
    Json(req): Json<CreateRunRequest>,
) -> Result<Json<CreateRunResponse>, AppError> {
    let framework_str = serde_json::to_value(req.framework)?
        .as_str()
        .unwrap_or("unknown")
        .to_string();

    let id: Uuid = sqlx::query_scalar(
        r#"INSERT INTO runs (repo_url, framework, status)
           VALUES ($1, $2, 'pending')
           RETURNING id"#,
    )
    .bind(&req.repo_url)
    .bind(&framework_str)
    .fetch_one(&state.db)
    .await?;

    // The full pipeline (clone → introspect → generate → run → score) runs in
    // the background. The engine endpoints are stubbed for now, so this just
    // exercises the wiring end-to-end.
    let bg = state.clone();
    let repo_url = req.repo_url.clone();
    let framework = req.framework;
    tokio::spawn(async move {
        if let Err(e) = run_pipeline(bg, id, repo_url, framework).await {
            tracing::error!("run {id} failed: {e:#}");
        }
    });

    Ok(Json(CreateRunResponse {
        id,
        status: "pending".into(),
    }))
}

async fn run_pipeline(
    state: AppState,
    run_id: Uuid,
    _repo_url: String,
    framework: Framework,
) -> anyhow::Result<()> {
    // 1. clone (stubbed path) + introspect → list of agents to test.
    set_status(&state.db, run_id, "introspecting").await?;
    let repo_path = format!("/work/clones/{run_id}");
    let introspected = state.engine.introspect(&repo_path, framework).await?;
    if introspected.agents.is_empty() {
        anyhow::bail!("introspection returned no agents");
    }
    let total_agents = introspected.agents.len();

    // --- run-level LLM-call budget ----------------------------------------
    // The ceiling is enforced at the RUN level (NOT per agent): one shared
    // counter spans generate + judge across every agent. Cost model, in
    // "LLM calls": 1 per /generate, 1 per test case judged in /score.
    let mut budget = Budget::from_env();

    // 2..4. Fan out over agents: generate → run → score, accumulating results.
    let mut run_passed = true; // AND across agents: any high-sev failure flips it
    let mut tested_agents = 0usize;
    let mut tests_total = 0usize;
    let mut tests_failed = 0usize;

    set_status(&state.db, run_id, "generating").await?;
    'agents: for (idx, agent) in introspected.agents.into_iter().enumerate() {
        let agent_ref = format!("{}::{}", agent.entry_file, agent.agent_variable_name);

        // BUDGET CHECKPOINT #1 — RESERVE the generate estimate to gate the
        // budget, then reconcile to the real `llm_calls` the engine reports.
        if !budget.try_spend(GENERATE_ESTIMATE) {
            budget.truncate(format!(
                "run LLM-call budget ({}) exhausted before agent `{agent_ref}`; \
                 {} of {total_agents} agent(s) not tested",
                budget.cap,
                total_agents - idx,
            ));
            break 'agents;
        }
        let generated = state.engine.generate(agent).await?;
        budget.reconcile(GENERATE_ESTIMATE, generated.llm_calls);
        let mut test_cases = generated.test_cases;

        // BUDGET CHECKPOINT #2 — cap this agent's test cases to the calls left
        // for judging (estimated at JUDGE_ESTIMATE each); reconcile after /score.
        let affordable = (budget.remaining() / JUDGE_ESTIMATE) as usize;
        if test_cases.len() > affordable {
            budget.truncate(format!(
                "run LLM-call budget ({}) reached while testing agent `{agent_ref}`; \
                 judged {affordable} of {} generated test case(s)",
                budget.cap,
                test_cases.len(),
            ));
            test_cases.truncate(affordable);
        }
        if test_cases.is_empty() {
            break 'agents; // nothing left to judge
        }
        let judge_reservation = test_cases.len() as u32 * JUDGE_ESTIMATE;
        budget.spend(judge_reservation); // reserve; reconciled after /score
        tested_agents += 1;

        // 3. run each test in the sandbox (stubbed: echo a passing result)
        set_status(&state.db, run_id, "running").await?;
        let results: Vec<contract::RunResult> = test_cases
            .iter()
            .map(|tc| contract::RunResult {
                test_case_id: tc.id.clone(),
                agent_output: "(stubbed sandbox output)".into(),
                tool_calls: vec![],
                passed: true,
                failure_reason: None,
            })
            .collect();

        // 4. score (judge) — reconcile the reservation to the real judge calls.
        set_status(&state.db, run_id, "scoring").await?;
        let scored = state.engine.score(test_cases.clone(), results).await?;
        budget.reconcile(judge_reservation, scored.llm_calls);

        // 5. persist results tagged with agent_ref; aggregate run pass/fail.
        let by_id: std::collections::HashMap<_, _> =
            test_cases.iter().map(|tc| (tc.id.clone(), tc)).collect();
        for r in &scored.scored {
            let Some(tc) = by_id.get(&r.test_case_id) else { continue };
            tests_total += 1;
            if !r.passed {
                tests_failed += 1;
                // Run fails iff a HIGH-severity test fails on ANY agent.
                if matches!(tc.severity, Severity::High) {
                    run_passed = false;
                }
            }
            let category = serde_json::to_value(tc.category)?
                .as_str().unwrap_or("").to_string();
            let severity = serde_json::to_value(tc.severity)?
                .as_str().unwrap_or("").to_string();
            sqlx::query(
                r#"INSERT INTO test_results
                   (run_id, agent_ref, category, severity, attack_prompt, agent_output, tool_calls, passed, failure_reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"#,
            )
            .bind(run_id)
            .bind(&agent_ref)
            .bind(category)
            .bind(severity)
            .bind(&tc.prompt)
            .bind(&r.agent_output)
            .bind(serde_json::Value::Array(r.tool_calls.clone()))
            .bind(r.passed)
            .bind(&r.failure_reason)
            .execute(&state.db)
            .await?;
        }

        if budget.truncated {
            break 'agents; // budget was exhausted mid-agent
        }
    }

    // 6. finalize run: aggregate verdict + truncation accounting.
    let mut summary = format!(
        "{tested_agents}/{total_agents} agent(s) tested · {tests_total} test(s) · {tests_failed} failure(s)."
    );
    if let Some(reason) = &budget.reason {
        summary.push_str(&format!(" Truncated: {reason}"));
    }

    sqlx::query(
        r#"UPDATE runs
           SET status = 'done', overall_passed = $2, summary = $3,
               truncated = $4, truncated_reason = $5
           WHERE id = $1"#,
    )
    .bind(run_id)
    .bind(run_passed)
    .bind(serde_json::json!({ "summary": summary }))
    .bind(budget.truncated)
    .bind(budget.reason.clone())
    .execute(&state.db)
    .await?;

    Ok(())
}

/// Pre-call RESERVATION for one /generate call, reconciled afterward to the
/// real `llm_calls` the engine reports. Used only to gate the budget.
const GENERATE_ESTIMATE: u32 = 1;
/// Pre-call RESERVATION per test case judged in /score, reconciled to the real
/// `llm_calls` after scoring.
///
/// LOCKED DESIGN: when /score becomes real it makes exactly ONE LLM call per
/// test case — the judge is never batched across cases. Per-test judging is
/// more reliable than scoring N cases in one call, and it keeps this estimate
/// exact (reservation == real cost), so reconciliation is a no-op in the happy
/// path. Do not change this to a batched judge.
const JUDGE_ESTIMATE: u32 = 1;

/// Run-level budget: a single shared ceiling on LLM calls across all agents.
struct Budget {
    cap: u32,
    spent: u32,
    truncated: bool,
    reason: Option<String>,
}

impl Budget {
    fn from_env() -> Self {
        let cap = std::env::var("AGENTPROBE_MAX_LLM_CALLS")
            .ok()
            .and_then(|s| s.parse::<u32>().ok())
            .unwrap_or(50);
        Self { cap, spent: 0, truncated: false, reason: None }
    }

    fn remaining(&self) -> u32 {
        self.cap.saturating_sub(self.spent)
    }

    /// Spend `n` calls only if affordable; returns false (and spends nothing)
    /// when it would exceed the cap.
    fn try_spend(&mut self, n: u32) -> bool {
        if self.spent + n > self.cap {
            return false;
        }
        self.spent += n;
        true
    }

    /// Unconditional spend (caller has already checked affordability).
    fn spend(&mut self, n: u32) {
        self.spent += n;
    }

    /// Replace a prior reservation with the actual count an endpoint reported:
    /// `spent = spent - reserved + actual`. Keeps the run-level cap honest once
    /// real API calls start, even when a call costs more or fewer than estimated.
    fn reconcile(&mut self, reserved: u32, actual: u32) {
        self.spent = self.spent.saturating_sub(reserved).saturating_add(actual);
    }

    fn truncate(&mut self, reason: String) {
        if !self.truncated {
            self.truncated = true;
            self.reason = Some(reason);
        }
    }
}

async fn set_status(db: &PgPool, id: Uuid, status: &str) -> anyhow::Result<()> {
    sqlx::query("UPDATE runs SET status = $2 WHERE id = $1")
        .bind(id)
        .bind(status)
        .execute(db)
        .await?;
    Ok(())
}

// ---------------------------------------------------------------------------
// GET /runs/:id — fetch a run + its results
// ---------------------------------------------------------------------------

async fn get_run(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, AppError> {
    let run = sqlx::query_as::<_, RunRow>(
        r#"SELECT id, repo_url, framework, status, created_at, overall_passed, summary,
                  truncated, truncated_reason
           FROM runs WHERE id = $1"#,
    )
    .bind(id)
    .fetch_optional(&state.db)
    .await?
    .ok_or(AppError::NotFound)?;

    let results = sqlx::query_as::<_, TestResultRow>(
        r#"SELECT id, run_id, agent_ref, category, severity, attack_prompt, agent_output,
                  tool_calls, passed, failure_reason
           FROM test_results WHERE run_id = $1 ORDER BY agent_ref, id"#,
    )
    .bind(id)
    .fetch_all(&state.db)
    .await?;

    Ok(Json(serde_json::json!({ "run": run, "results": results })))
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct RunRow {
    id: Uuid,
    repo_url: String,
    framework: String,
    status: String,
    created_at: chrono::DateTime<chrono::Utc>,
    overall_passed: Option<bool>,
    summary: Option<serde_json::Value>,
    truncated: bool,
    truncated_reason: Option<String>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
struct TestResultRow {
    id: i64,
    run_id: Uuid,
    agent_ref: String,
    category: String,
    severity: String,
    attack_prompt: String,
    agent_output: Option<String>,
    tool_calls: Option<serde_json::Value>,
    passed: Option<bool>,
    failure_reason: Option<String>,
}

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("not found")]
    NotFound,
    #[error(transparent)]
    Sqlx(#[from] sqlx::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            AppError::NotFound => (StatusCode::NOT_FOUND, "not found".to_string()),
            other => (StatusCode::INTERNAL_SERVER_ERROR, other.to_string()),
        };
        (status, Json(serde_json::json!({ "error": msg }))).into_response()
    }
}
