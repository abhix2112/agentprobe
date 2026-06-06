import { useState, type ReactNode } from "react";
import { ChevronRight, Terminal, MessageSquareWarning } from "lucide-react";
import { cn } from "@/lib/utils";
import { CategoryBadge, SeverityBadge } from "@/components/ui/badge";
import type { TestResultRow } from "@/lib/contract";

export function FailureList({ failures }: { failures: TestResultRow[] }) {
  if (failures.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6 text-center text-sm text-muted-foreground">
        No failures — every test passed.
      </div>
    );
  }
  // High severity first.
  const order = { high: 0, medium: 1, low: 2 } as const;
  const sorted = [...failures].sort((a, b) => order[a.severity] - order[b.severity]);

  return (
    <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
      {sorted.map((f) => (
        <FailureRow key={f.id} failure={f} />
      ))}
    </div>
  );
}

function FailureRow({ failure: f }: { failure: TestResultRow }) {
  const [open, setOpen] = useState(f.severity === "high"); // high expanded by default
  return (
    <div className={cn(f.severity === "high" && "bg-danger/[0.04]")}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40"
      >
        <ChevronRight
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        <SeverityBadge severity={f.severity} />
        <CategoryBadge category={f.category} />
        <span className="mono truncate text-sm text-foreground/90">{f.attack_prompt || "(empty input)"}</span>
        <span className="mono ml-auto hidden shrink-0 text-[11px] text-muted-foreground md:block">
          {f.agent_ref}
        </span>
      </button>

      {open && (
        <div className="space-y-3 px-4 pb-4 pl-11 text-sm">
          <Field icon={<Terminal className="h-3.5 w-3.5" />} label="Attack prompt">
            <pre className="mono whitespace-pre-wrap break-words text-foreground/90">
              {f.attack_prompt || "(empty input)"}
            </pre>
          </Field>
          {f.tool_calls && f.tool_calls.length > 0 && (
            <Field icon={<Terminal className="h-3.5 w-3.5" />} label="Tool calls">
              <pre className="mono whitespace-pre-wrap break-words text-amber-300/90">
                {f.tool_calls.map((t) => JSON.stringify(t)).join("\n")}
              </pre>
            </Field>
          )}
          {f.agent_output && (
            <Field icon={<MessageSquareWarning className="h-3.5 w-3.5" />} label="Agent output">
              <pre className="mono whitespace-pre-wrap break-words text-foreground/80">
                {f.agent_output}
              </pre>
            </Field>
          )}
          {f.failure_reason && (
            <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-danger">
              <span className="font-medium">Why it failed: </span>
              {f.failure_reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({
  icon,
  label,
  children,
}: {
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="rounded-lg border border-border bg-background/60 p-3">{children}</div>
    </div>
  );
}
