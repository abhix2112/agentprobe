//! Sandbox execution of the target agent against each TestCase.
//!
//! Three modes, selected by `AGENTPROBE_SANDBOX` (default `mock`):
//! - `mock`: no execution; returns a canned RunResult. Key-free; CI default.
//! - `local`: runs the framework runner as a LOCAL subprocess against the
//!   already-cloned repo. Key-free (no E2B); needs the agent's deps on
//!   `AGENTPROBE_LOCAL_PYTHON` (default `python3`).
//! - `e2b`: provisions an E2B sandbox over the REST API (key from
//!   `E2B_API_KEY`), clones + installs, and runs the runner inside.
//!
//! Test cases run concurrently under a bounded Tokio semaphore
//! (`AGENTPROBE_SANDBOX_CONCURRENCY`, default 5 — well under E2B Hobby's 20),
//! each with a 60s timeout. On crash/timeout the RunResult is marked
//! `errored: true` EXPLICITLY (never inferred elsewhere).

use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use std::time::Duration;

use futures::future::join_all;
use tokio::io::AsyncWriteExt;
use tokio::sync::Semaphore;

use crate::contract::{AgentSpec, Framework, RunResult};
use crate::contract::TestCase;

/// The LangGraph runner script, embedded so the orchestrator can write it into a
/// sandbox or run it locally. (First framework supported; others come later.)
const RUNNER_LANGGRAPH: &str = include_str!("../runners/langgraph_runner.py");

const TEST_TIMEOUT: Duration = Duration::from_secs(60);
const DEFAULT_CONCURRENCY: usize = 5;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SandboxMode {
    Mock,
    Local,
    E2b,
}

impl SandboxMode {
    fn from_env() -> Self {
        match std::env::var("AGENTPROBE_SANDBOX")
            .unwrap_or_default()
            .to_lowercase()
            .as_str()
        {
            "local" => Self::Local,
            "e2b" => Self::E2b,
            _ => Self::Mock,
        }
    }
}

pub struct Sandbox {
    mode: SandboxMode,
    concurrency: usize,
}

impl Sandbox {
    pub fn from_env() -> Self {
        let concurrency = std::env::var("AGENTPROBE_SANDBOX_CONCURRENCY")
            .ok()
            .and_then(|s| s.parse::<usize>().ok())
            .filter(|n| *n > 0)
            .unwrap_or(DEFAULT_CONCURRENCY);
        Self {
            mode: SandboxMode::from_env(),
            concurrency,
        }
    }

    /// Run every test case against the agent — concurrently (bounded), 60s each.
    /// Order of the returned results matches `test_cases`.
    pub async fn run_battery(
        &self,
        spec: &AgentSpec,
        repo_path: &str,
        test_cases: &[TestCase],
    ) -> Vec<RunResult> {
        let prepared = Arc::new(self.prepare(spec, repo_path).await);
        let sem = Arc::new(Semaphore::new(self.concurrency));

        let futs = test_cases.iter().map(|tc| {
            let sem = sem.clone();
            let prepared = prepared.clone();
            let mode = self.mode;
            async move {
                let _permit = sem.acquire().await.expect("semaphore is never closed");
                match tokio::time::timeout(
                    TEST_TIMEOUT,
                    run_one(mode, &prepared, spec, repo_path, tc),
                )
                .await
                {
                    Ok(rr) => rr,
                    Err(_) => errored_result(&tc.id, "timed out after 60s"),
                }
            }
        });
        join_all(futs).await
    }

    async fn prepare(&self, spec: &AgentSpec, repo_path: &str) -> Prepared {
        match self.mode {
            SandboxMode::Mock => Prepared::Mock,
            SandboxMode::Local => match write_runner_for(spec).await {
                Ok(Some(path)) => Prepared::Local { runner_path: path },
                Ok(None) => Prepared::Failed(format!(
                    "no local runner for framework {:?} yet (langgraph only)",
                    spec.framework
                )),
                Err(e) => Prepared::Failed(format!("failed to stage runner: {e}")),
            },
            SandboxMode::E2b => match e2b::provision(spec, repo_path).await {
                Ok(sb) => Prepared::E2b(sb),
                Err(e) => Prepared::Failed(format!("E2B provisioning failed: {e}")),
            },
        }
    }
}

enum Prepared {
    Mock,
    Local { runner_path: PathBuf },
    E2b(e2b::Sandbox),
    /// Preparation failed; every test for this run is marked errored.
    Failed(String),
}

async fn run_one(
    _mode: SandboxMode,
    prepared: &Prepared,
    spec: &AgentSpec,
    repo_path: &str,
    tc: &TestCase,
) -> RunResult {
    match prepared {
        Prepared::Mock => RunResult {
            test_case_id: tc.id.clone(),
            agent_output: "(mock sandbox — no agent executed)".into(),
            tool_calls: vec![],
            passed: true,
            failure_reason: None,
            errored: false,
        },
        Prepared::Local { runner_path } => {
            run_local(runner_path, spec, repo_path, tc).await
        }
        Prepared::E2b(sandbox) => sandbox.run_test(spec, tc).await,
        Prepared::Failed(reason) => errored_result(&tc.id, reason),
    }
}

// ---------------------------------------------------------------------------
// Local subprocess mode
// ---------------------------------------------------------------------------

/// Stage the framework runner to a temp file; None if the framework is
/// unsupported (langgraph only for now).
async fn write_runner_for(spec: &AgentSpec) -> std::io::Result<Option<PathBuf>> {
    let script = match spec.framework {
        Framework::Langgraph => RUNNER_LANGGRAPH,
        _ => return Ok(None),
    };
    let path = std::env::temp_dir().join("agentprobe_langgraph_runner.py");
    tokio::fs::write(&path, script).await?;
    Ok(Some(path))
}

async fn run_local(
    runner_path: &PathBuf,
    spec: &AgentSpec,
    repo_path: &str,
    tc: &TestCase,
) -> RunResult {
    let python = std::env::var("AGENTPROBE_LOCAL_PYTHON").unwrap_or_else(|_| "python3".into());
    let spawn = tokio::process::Command::new(python)
        .arg(runner_path)
        .arg(repo_path)
        .arg(&spec.entry_file)
        .arg(&spec.agent_variable_name)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn();

    let mut child = match spawn {
        Ok(c) => c,
        Err(e) => return errored_result(&tc.id, &format!("failed to spawn runner: {e}")),
    };

    if let Some(mut stdin) = child.stdin.take() {
        if let Err(e) = stdin.write_all(tc.prompt.as_bytes()).await {
            return errored_result(&tc.id, &format!("failed to write prompt: {e}"));
        }
        // drop `stdin` -> EOF so the runner's sys.stdin.read() returns.
    }

    match child.wait_with_output().await {
        Ok(out) => parse_runner_output(
            &tc.id,
            out.status.success(),
            &String::from_utf8_lossy(&out.stdout),
            &String::from_utf8_lossy(&out.stderr),
        ),
        Err(e) => errored_result(&tc.id, &format!("runner wait failed: {e}")),
    }
}

/// Parse the runner's single JSON line `{output, tool_calls, error}` into a
/// RunResult. `errored` is set on nonzero exit, unparseable output, or a
/// non-null `error` field.
fn parse_runner_output(
    test_case_id: &str,
    success: bool,
    stdout: &str,
    stderr: &str,
) -> RunResult {
    let parsed: Option<serde_json::Value> = stdout
        .lines()
        .rev()
        .find(|l| !l.trim().is_empty())
        .and_then(|l| serde_json::from_str(l).ok());

    match parsed {
        Some(v) => {
            let error = v.get("error").and_then(|e| e.as_str());
            let tool_calls = v
                .get("tool_calls")
                .and_then(|t| t.as_array())
                .cloned()
                .unwrap_or_default();
            let output = v
                .get("output")
                .and_then(|o| o.as_str())
                .unwrap_or("")
                .to_string();
            RunResult {
                test_case_id: test_case_id.to_string(),
                agent_output: output,
                tool_calls,
                passed: true, // scoring decides pass/fail; this is the raw run
                failure_reason: None,
                errored: !success || error.is_some(),
            }
        }
        None => errored_result(
            test_case_id,
            &format!(
                "runner produced no parseable JSON (success={success}); stderr: {}",
                stderr.chars().take(300).collect::<String>()
            ),
        ),
    }
}

fn errored_result(test_case_id: &str, reason: &str) -> RunResult {
    RunResult {
        test_case_id: test_case_id.to_string(),
        agent_output: reason.to_string(),
        tool_calls: vec![],
        passed: false,
        failure_reason: Some(reason.to_string()),
        errored: true,
    }
}

// ---------------------------------------------------------------------------
// E2B mode
// ---------------------------------------------------------------------------

mod e2b {
    use std::time::Duration;

    use crate::contract::{AgentSpec, TestCase};
    use crate::sandbox::{errored_result, RunResult};

    const API_BASE: &str = "https://api.e2b.app";
    const MAX_RETRIES: u32 = 5;

    /// A provisioned E2B sandbox (repo cloned + deps installed + runner staged).
    pub struct Sandbox {
        #[allow(dead_code)]
        sandbox_id: String,
        #[allow(dead_code)]
        http: reqwest::Client,
    }

    /// Create the sandbox over REST, clone the repo, install requirements, stage
    /// the runner. The sandbox-create call retries on 429 with bounded backoff.
    pub async fn provision(_spec: &AgentSpec, _repo_path: &str) -> anyhow::Result<Sandbox> {
        let api_key = std::env::var("E2B_API_KEY")
            .map_err(|_| anyhow::anyhow!("E2B_API_KEY not set"))?;
        let http = reqwest::Client::new();

        let sandbox_id = create_sandbox(&http, &api_key).await?;
        // NOTE: in-sandbox exec/filesystem (clone, pip install, run the runner)
        // goes through the per-sandbox envd service (Connect-RPC), which is the
        // step that must be validated against a real E2B_API_KEY before it can
        // be trusted. Until then `run_test` reports an errored RunResult with a
        // clear reason rather than fabricating output.
        Ok(Sandbox { sandbox_id, http })
    }

    /// POST /sandboxes with bounded exponential backoff on 429 / transient errors
    /// — a rate limit NEVER crashes the run.
    async fn create_sandbox(http: &reqwest::Client, api_key: &str) -> anyhow::Result<String> {
        let body = serde_json::json!({ "templateID": "base" });
        let mut attempt = 0u32;
        loop {
            let resp = http
                .post(format!("{API_BASE}/sandboxes"))
                .header("X-API-Key", api_key)
                .json(&body)
                .send()
                .await;

            match resp {
                Ok(r) if r.status().is_success() => {
                    let v: serde_json::Value = r.json().await?;
                    let id = v
                        .get("sandboxID")
                        .and_then(|s| s.as_str())
                        .ok_or_else(|| anyhow::anyhow!("create response missing sandboxID"))?;
                    return Ok(id.to_string());
                }
                Ok(r) if r.status().as_u16() == 429 || r.status().is_server_error() => {
                    if attempt >= MAX_RETRIES {
                        anyhow::bail!("E2B create rate-limited/unavailable after {MAX_RETRIES} retries");
                    }
                    backoff(attempt).await;
                    attempt += 1;
                }
                Ok(r) => anyhow::bail!("E2B create failed: HTTP {}", r.status()),
                Err(e) if attempt < MAX_RETRIES => {
                    backoff(attempt).await;
                    attempt += 1;
                    let _ = e;
                }
                Err(e) => return Err(e.into()),
            }
        }
    }

    /// Exponential backoff with a deterministic per-attempt step (no rng dep):
    /// 0.5s, 1s, 2s, 4s, 8s (capped).
    async fn backoff(attempt: u32) {
        let secs = (0.5_f64 * 2f64.powi(attempt as i32)).min(8.0);
        tokio::time::sleep(Duration::from_secs_f64(secs)).await;
    }

    impl Sandbox {
        pub async fn run_test(&self, _spec: &AgentSpec, tc: &TestCase) -> RunResult {
            // See provision(): the envd exec path is pending validation with a
            // real E2B_API_KEY. Local mode is the validated execution path today.
            errored_result(
                &tc.id,
                "E2B in-sandbox exec not yet validated (envd Connect-RPC); use AGENTPROBE_SANDBOX=local",
            )
        }
    }
}
