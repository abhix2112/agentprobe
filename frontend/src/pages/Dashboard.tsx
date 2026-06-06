import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RunsTable } from "@/components/RunsTable";
import { listRuns } from "@/lib/api";
import type { Run } from "@/lib/contract";

export default function Dashboard() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setRuns(await listRuns());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // keep the list fresh while runs progress
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Runs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Adversarial security &amp; reliability probes of AI agents.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={load} aria-label="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Link to="/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> New run
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      {runs === null ? (
        <div className="rounded-xl border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
          Loading…
        </div>
      ) : (
        <RunsTable runs={runs} />
      )}
    </div>
  );
}
