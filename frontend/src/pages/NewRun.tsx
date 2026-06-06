import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Github } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { createRun } from "@/lib/api";
import type { Framework } from "@/lib/contract";

const FRAMEWORKS: { value: Framework; label: string }[] = [
  { value: "langgraph", label: "LangGraph" },
  { value: "openai", label: "OpenAI Agents" },
  { value: "claude", label: "Claude Agent SDK" },
];

export default function NewRun() {
  const navigate = useNavigate();
  const [repoUrl, setRepoUrl] = useState("");
  const [framework, setFramework] = useState<Framework>("langgraph");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const { id } = await createRun(repoUrl.trim(), framework);
      navigate(`/runs/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-xl font-semibold tracking-tight">New probe run</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Point agentprobe at an agent repo. It clones the code, statically maps the agent and its
        tools, generates adversarial tests, runs them in a sandbox, and scores the result.
      </p>

      <form onSubmit={submit} className="mt-6 space-y-5 rounded-xl border border-border bg-surface p-5">
        <div>
          <label className="mb-1.5 block text-sm font-medium">Repository</label>
          <div className="relative">
            <Github className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/agent-repo"
              className="mono w-full rounded-lg border border-border-strong bg-background py-2.5 pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground/60 focus:border-primary"
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium">Framework</label>
          <div className="grid grid-cols-3 gap-2">
            {FRAMEWORKS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => setFramework(f.value)}
                className={cn(
                  "rounded-lg border px-3 py-2.5 text-sm transition-colors",
                  framework === f.value
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border-strong bg-background text-muted-foreground hover:text-foreground",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <Button type="submit" disabled={submitting || !repoUrl.trim()} className="w-full" size="lg">
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {submitting ? "Starting…" : "Run probe"}
        </Button>
      </form>
    </div>
  );
}
