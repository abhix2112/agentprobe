import * as React from "react";
import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/contract";

const severityClass: Record<Severity, string> = {
  low: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  high: "bg-red-500/15 text-red-400 border-red-500/30",
};

export function Badge({
  className,
  severity,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { severity?: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        severity ? severityClass[severity] : "border-border bg-muted text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}
