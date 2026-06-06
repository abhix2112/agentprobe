import * as React from "react";
import { cn } from "@/lib/utils";
import type { Category, Severity } from "@/lib/contract";

const base =
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium leading-none";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(base, "border-border bg-muted text-muted-foreground", className)}
      {...props}
    />
  );
}

const severityStyles: Record<Severity, string> = {
  low: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  medium: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  high: "border-red-500/30 bg-red-500/12 text-red-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={cn(base, "uppercase tracking-wide", severityStyles[severity])}>
      {severity}
    </span>
  );
}

const categoryLabel: Record<Category, string> = {
  injection: "Injection",
  tool_misuse: "Tool misuse",
  goal_hijack: "Goal hijack",
  exfiltration: "Exfiltration",
  edge_case: "Edge case",
};

export function CategoryBadge({ category }: { category: Category }) {
  return (
    <span className={cn(base, "border-border-strong bg-surface-2 text-foreground/80")}>
      {categoryLabel[category] ?? category}
    </span>
  );
}

export function categoryName(category: Category): string {
  return categoryLabel[category] ?? category;
}
