import { useEffect, useRef, useState, type ReactNode } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { PipelineStepper } from "@/components/PipelineStepper";
import { VerdictBanner } from "@/components/VerdictBanner";
import { Scoreboard } from "@/components/Scoreboard";
import { VerdictSummary } from "@/components/VerdictSummary";
import { CategoryCards } from "@/components/CategoryCards";
import { TestResults } from "@/components/TestResults";
import { getRun } from "@/lib/api";
import { isTerminal } from "@/lib/status";
import type { RunReport } from "@/lib/contract";

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<RunReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;

    async function poll() {
      try {
        const r = await getRun(id!);
        if (!alive) return;
        setReport(r);
        if (isTerminal(r.run.status) && timer.current) {
          clearInterval(timer.current);
          timer.current = null;
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    }

    poll();
    timer.current = setInterval(poll, 2000); // live pipeline polling
    return () => {
      alive = false;
      if (timer.current) clearInterval(timer.current);
    };
  }, [id]);

  if (error) {
    return <Shell><div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div></Shell>;
  }
  if (!report) {
    return (
      <Shell>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading run…
        </div>
      </Shell>
    );
  }

  const { run, results } = report;
  const done = isTerminal(run.status);
  const failures = results.filter((r) => !r.passed);
  const highFailed = failures.filter((r) => r.severity === "high").length;

  return (
    <Shell>
      <div className="mb-1 flex items-center gap-2">
        <h1 className="mono truncate text-lg font-semibold tracking-tight">
          {run.repo_url.replace(/^https?:\/\/(www\.)?github\.com\//, "")}
        </h1>
        <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          {run.framework}
        </span>
      </div>
      <p className="mb-6 text-xs text-muted-foreground">Run {run.id}</p>

      {/* Pipeline stepper */}
      <div className="mb-8 rounded-xl border border-border bg-surface p-5">
        <PipelineStepper status={run.status} />
        {!done && (
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {labelFor(run.status)}
          </div>
        )}
      </div>

      {done && run.status === "error" && (
        <div className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          This run errored before completing. {run.summary?.summary}
        </div>
      )}

      {done && run.status === "done" && (
        <div className="space-y-6">
          <Scoreboard
            total={results.length}
            passed={results.length - failures.length}
            failed={failures.length}
            highFailed={highFailed}
          />

          <VerdictBanner
            passed={run.overall_passed}
            total={results.length}
            failed={failures.length}
            highFailed={highFailed}
            truncated={run.truncated}
            truncatedReason={run.truncated_reason}
          />

          <VerdictSummary results={results} />

          <section>
            <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Coverage by category</h2>
            <CategoryCards results={results} />
          </section>

          <section>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              Test results
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {results.length}
              </span>
              {failures.length > 0 && (
                <span className="rounded-full bg-danger/15 px-2 py-0.5 text-xs text-danger">
                  {failures.length} failed
                </span>
              )}
            </h2>
            <TestResults results={results} />
          </section>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div>
      <Link to="/" className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> All runs
      </Link>
      {children}
    </div>
  );
}

function labelFor(status: string): string {
  const map: Record<string, string> = {
    pending: "Queued…",
    cloning: "Cloning repository…",
    introspecting: "Statically mapping the agent…",
    generating: "Generating adversarial tests…",
    running: "Running tests in the sandbox…",
    scoring: "Scoring results…",
  };
  return map[status] ?? "Working…";
}
