import { Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2, CircleDashed } from "lucide-react";
import { cn } from "@/lib/utils";
import { relativeTime, isTerminal } from "@/lib/status";
import type { Run } from "@/lib/contract";

export function RunsTable({ runs }: { runs: Run[] }) {
  if (runs.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-10 text-center">
        <p className="text-sm text-muted-foreground">No runs yet.</p>
        <Link to="/new" className="mt-2 inline-block text-sm text-primary hover:underline">
          Start your first probe →
        </Link>
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-4 py-2.5 font-medium">Verdict</th>
            <th className="px-4 py-2.5 font-medium">Repository</th>
            <th className="px-4 py-2.5 font-medium">Framework</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 text-right font-medium">When</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {runs.map((r) => (
            <tr key={r.id} className="group hover:bg-muted/40">
              <td className="px-4 py-3">
                <Link to={`/runs/${r.id}`} className="block">
                  <Verdict run={r} />
                </Link>
              </td>
              <td className="px-4 py-3">
                <Link to={`/runs/${r.id}`} className="mono block truncate text-foreground/90 group-hover:text-foreground">
                  {shortRepo(r.repo_url)}
                </Link>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{r.framework}</td>
              <td className="px-4 py-3">
                <StatusPill status={r.status} />
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">
                {relativeTime(r.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Verdict({ run }: { run: Run }) {
  if (!isTerminal(run.status)) return <span className="text-xs text-muted-foreground">—</span>;
  if (run.status === "error")
    return <span className="text-xs font-medium text-warning">errored</span>;
  return run.overall_passed ? (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success">
      <CheckCircle2 className="h-4 w-4" /> Pass
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger">
      <XCircle className="h-4 w-4" /> Fail
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
  const running = !isTerminal(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs",
        status === "done" && "border-border bg-muted text-muted-foreground",
        status === "error" && "border-warning/30 bg-warning/10 text-warning",
        running && "border-primary/30 bg-primary/10 text-primary",
      )}
    >
      {running ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <CircleDashed className="h-3 w-3" />
      )}
      {status}
    </span>
  );
}

function shortRepo(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?github\.com\//, "").replace(/\.git$/, "").replace(/\/$/, "");
}
