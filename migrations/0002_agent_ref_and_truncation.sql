-- 0002: per-agent result attribution + run-level budget truncation accounting.
--
-- A single run now fans out over every agent in IntrospectResult.agents and
-- generates/runs/scores each one. Two new pieces of state:
--   1. test_results.agent_ref  — which agent a result belongs to, as a stable,
--      human-readable id "<entry_file>::<agent_variable_name>" so the report UI
--      can group failures by agent (e.g. "src/react_search/graph.py::graph").
--   2. runs.truncated / runs.truncated_reason — set when the run's hard LLM-call
--      budget was hit and some agents/test-cases were intentionally skipped,
--      rather than silently overspending.

ALTER TABLE test_results
    ADD COLUMN agent_ref TEXT NOT NULL DEFAULT '';

ALTER TABLE runs
    ADD COLUMN truncated BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE runs
    ADD COLUMN truncated_reason TEXT;

-- Group results by (run, agent) for the report view.
CREATE INDEX IF NOT EXISTS idx_test_results_run_agent
    ON test_results(run_id, agent_ref);
