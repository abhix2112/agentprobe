import { useState } from "react";
import { ShieldAlert, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Framework, RunReport } from "@/lib/contract";

const FRAMEWORKS: Framework[] = ["langgraph", "openai", "claude"];

export default function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [framework, setFramework] = useState<Framework>("langgraph");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<RunReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setReport(null);
    setLoading(true);
    try {
      const created = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, framework }),
      });
      if (!created.ok) throw new Error(`create failed: ${created.status}`);
      const { id } = await created.json();

      // Poll until the run finishes.
      let attempts = 0;
      while (attempts++ < 30) {
        await new Promise((r) => setTimeout(r, 1000));
        const res = await fetch(`/api/runs/${id}`);
        if (!res.ok) continue;
        const data: RunReport = await res.json();
        if (data.run.status === "done" || data.run.status === "error") {
          setReport(data);
          break;
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <header className="mb-8 flex items-center gap-3">
        <ShieldAlert className="h-7 w-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">agentprobe</h1>
          <p className="text-sm text-muted-foreground">
            Adversarial security &amp; reliability testing for AI agents.
          </p>
        </div>
      </header>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>New probe run</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            placeholder="https://github.com/owner/agent-repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
          <div className="flex gap-2">
            {FRAMEWORKS.map((f) => (
              <Button
                key={f}
                variant={framework === f ? "default" : "outline"}
                size="sm"
                onClick={() => setFramework(f)}
              >
                {f}
              </Button>
            ))}
          </div>
          <Button onClick={submit} disabled={loading || !repoUrl}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Probing…" : "Run probe"}
          </Button>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </CardContent>
      </Card>

      {report && (
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            {report.run.overall_passed ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            ) : (
              <XCircle className="h-5 w-5 text-red-400" />
            )}
            <span className="font-medium">
              {report.run.summary?.summary ?? report.run.status}
            </span>
          </div>

          {report.results.map((r) => (
            <Card key={r.id}>
              <CardContent className="space-y-2 pt-5">
                <div className="flex items-center gap-2">
                  <Badge>{r.category}</Badge>
                  <Badge severity={r.severity}>{r.severity}</Badge>
                  {r.passed ? (
                    <span className="text-xs text-emerald-400">passed</span>
                  ) : (
                    <span className="text-xs text-red-400">failed</span>
                  )}
                </div>
                <p className="text-sm">
                  <span className="text-muted-foreground">Attack: </span>
                  {r.attack_prompt || <em>(empty input)</em>}
                </p>
                {r.agent_output && (
                  <p className="text-sm">
                    <span className="text-muted-foreground">Output: </span>
                    {r.agent_output}
                  </p>
                )}
                {r.failure_reason && (
                  <p className="text-sm text-red-400">{r.failure_reason}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
