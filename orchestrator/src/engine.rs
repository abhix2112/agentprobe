//! HTTP client for the Python engine. Thin wrappers over the three contract
//! endpoints; all (de)serialization goes through `contract.rs`.

use crate::contract::*;

#[derive(Clone)]
pub struct EngineClient {
    http: reqwest::Client,
    base_url: String,
}

impl EngineClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            http: reqwest::Client::new(),
            base_url: base_url.into(),
        }
    }

    pub async fn introspect(
        &self,
        repo_path: &str,
        framework: Framework,
    ) -> anyhow::Result<IntrospectResult> {
        let body = IntrospectRequest {
            repo_path: repo_path.to_string(),
            framework,
        };
        Ok(self
            .http
            .post(format!("{}/introspect", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?
            .json::<IntrospectResult>()
            .await?)
    }

    pub async fn generate(&self, agent_spec: AgentSpec) -> anyhow::Result<GenerateResponse> {
        let body = GenerateRequest { agent_spec };
        Ok(self
            .http
            .post(format!("{}/generate", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?
            .json::<GenerateResponse>()
            .await?)
    }

    pub async fn score(
        &self,
        test_cases: Vec<TestCase>,
        results: Vec<RunResult>,
    ) -> anyhow::Result<ScoreResponse> {
        let body = ScoreRequest {
            test_cases,
            results,
        };
        Ok(self
            .http
            .post(format!("{}/score", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?
            .json::<ScoreResponse>()
            .await?)
    }
}
