-- agentprobe initial schema.
-- Applied by the orchestrator on boot via sqlx::migrate!.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS runs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_url       TEXT        NOT NULL,
    framework      TEXT        NOT NULL,  -- "langgraph" | "openai" | "claude"
    status         TEXT        NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    overall_passed BOOLEAN,
    summary        JSONB
);

CREATE TABLE IF NOT EXISTS test_results (
    id             BIGSERIAL   PRIMARY KEY,
    run_id         UUID        NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    category       TEXT        NOT NULL,  -- injection | tool_misuse | goal_hijack | exfiltration | edge_case
    severity       TEXT        NOT NULL,  -- low | medium | high
    attack_prompt  TEXT        NOT NULL,
    agent_output   TEXT,
    tool_calls     JSONB,
    passed         BOOLEAN,
    failure_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_test_results_run_id ON test_results(run_id);
