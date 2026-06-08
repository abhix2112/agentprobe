import { cn } from "@/lib/utils";

// Big at-a-glance counts for the top of the report. Reads like a security
// scoreboard: how many real attacks ran, how many the agent survived, how many
// it failed, and how many of those failures are high-severity.
export function Scoreboard({
  total,
  passed,
  failed,
  highFailed,
}: {
  total: number;
  passed: number;
  failed: number;
  highFailed: number;
}) {
  const tiles = [
    { label: "Tests run", value: total, tone: "neutral" as const },
    { label: "Passed", value: passed, tone: "good" as const },
    { label: "Failed", value: failed, tone: failed > 0 ? "bad" : "neutral" },
    {
      label: "High-severity",
      value: highFailed,
      tone: highFailed > 0 ? "bad" : "neutral",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {tiles.map((t) => (
        <div
          key={t.label}
          className={cn(
            "rounded-xl border p-4",
            t.tone === "bad" && "border-danger/35 bg-danger/[0.07]",
            t.tone === "good" && "border-success/30 bg-success/[0.06]",
            t.tone === "neutral" && "border-border bg-surface",
          )}
        >
          <div
            className={cn(
              "text-4xl font-semibold tabular-nums tracking-tight",
              t.tone === "bad" && "text-danger",
              t.tone === "good" && "text-success",
              t.tone === "neutral" && "text-foreground",
            )}
          >
            {t.value}
          </div>
          <div className="mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t.label}
          </div>
        </div>
      ))}
    </div>
  );
}
