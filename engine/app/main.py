"""agentprobe engine — FastAPI service.

Three endpoints implement the contract: /introspect, /generate, /score.
All three are STUBBED for now: they return fake-but-valid data matching the
contract so the orchestrator can be wired end-to-end before the real static
analysis / test generation / scoring lands.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import introspect as introspector
from .contract import (
    GenerateRequest,
    GenerateResponse,
    IntrospectRequest,
    IntrospectResult,
    ScoreRequest,
    ScoreResponse,
)
from .generate import GenerationFailed, generate_test_cases
from .introspect import AgentNotFound
from .score import score_results

app = FastAPI(title="agentprobe engine", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/introspect", response_model=IntrospectResult)
def introspect(req: IntrospectRequest) -> IntrospectResult:
    """Statically parse the cloned repo and describe the agent(s).

    Pure `ast` analysis — cloned repo code is NEVER imported or executed.
    Returns {"agents": [AgentSpec, ...]} (a one-element list for single-agent
    repos), or 422 when no agent can be located so the caller can specify a file.
    """
    try:
        return introspector.introspect(req.repo_path, req.framework)
    except AgentNotFound as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate adversarial test cases tailored to the agent spec.

    LLM-backed (Claude) when ANTHROPIC_API_KEY is set; a deterministic,
    agent-tailored fallback otherwise. `llm_calls` reports the ACTUAL number of
    API calls made (0 on the offline path) so the orchestrator reconciles its
    run-level budget against the real count.
    """
    try:
        test_cases, llm_calls = generate_test_cases(req.agent_spec)
    except GenerationFailed as exc:
        # The model could not produce a valid, grounded battery. Fail honestly
        # (502) rather than returning boilerplate; the orchestrator marks the run
        # as errored. `llm_calls` spent is reported in the detail for accounting.
        raise HTTPException(
            status_code=502,
            detail={"error": exc.message, "llm_calls": exc.llm_calls},
        ) from exc
    return GenerateResponse(test_cases=test_cases, llm_calls=llm_calls)


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    """Score (TestCase, RunResult) pairs.

    Per test: a deterministic `detection` signal feeds into exactly ONE
    claude-sonnet-4-6 judge call; a fired HIGH-severity signal forces
    `passed=false` (the judge cannot overturn it). `overall_passed` is the
    high-severity AND. `llm_calls` == number of judge calls. Without an API key,
    a deterministic-only offline judge is used (0 llm_calls) so the service runs
    key-free.
    """
    return score_results(req.test_cases, req.results)
