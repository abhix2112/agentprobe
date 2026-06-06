import type { Framework, Run, RunReport } from "./contract";

// All calls go through Vite's /api proxy → orchestrator.
async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? ` — ${body}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export async function createRun(repo_url: string, framework: Framework): Promise<{ id: string }> {
  return json(
    await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url, framework }),
    }),
  );
}

export async function listRuns(): Promise<Run[]> {
  return json(await fetch("/api/runs"));
}

export async function getRun(id: string): Promise<RunReport> {
  return json(await fetch(`/api/runs/${id}`));
}
