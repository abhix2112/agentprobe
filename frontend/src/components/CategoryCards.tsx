import { cn } from "@/lib/utils";
import { categoryName } from "@/components/ui/badge";
import type { Category, TestResultRow } from "@/lib/contract";

const CATEGORY_ORDER: Category[] = [
  "injection",
  "tool_misuse",
  "goal_hijack",
  "exfiltration",
  "edge_case",
];

export function CategoryCards({ results }: { results: TestResultRow[] }) {
  const groups = CATEGORY_ORDER.map((cat) => {
    const rows = results.filter((r) => r.category === cat);
    const total = rows.length;
    const passed = rows.filter((r) => r.passed).length;
    return { cat, total, passed };
  }).filter((g) => g.total > 0);

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {groups.map(({ cat, total, passed }) => {
        const allPass = passed === total;
        const rate = total ? Math.round((passed / total) * 100) : 0;
        return (
          <div
            key={cat}
            className={cn(
              "rounded-xl border p-4",
              allPass ? "border-border bg-surface" : "border-danger/30 bg-danger/[0.06]",
            )}
          >
            <div className="text-xs font-medium text-muted-foreground">{categoryName(cat)}</div>
            <div className="mt-2 flex items-baseline gap-1">
              <span
                className={cn(
                  "text-2xl font-semibold tabular-nums",
                  allPass ? "text-foreground" : "text-danger",
                )}
              >
                {passed}
              </span>
              <span className="text-sm text-muted-foreground">/ {total}</span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full", allPass ? "bg-success" : "bg-danger")}
                style={{ width: `${rate}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
