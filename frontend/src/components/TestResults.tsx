import { useState, type ReactNode } from "react";
import {
  ChevronRight,
  Terminal,
  MessageSquareWarning,
  Wrench,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CategoryBadge, SeverityBadge } from "@/components/ui/badge";
import type { TestResultRow } from "@/lib/contract";

const SEV_ORDER = { high: 0, medium: 1, low: 2 } as const;

// Every test case, failures first (high→low), then passes. Each row is an
// expandable card exposing the full attack we ran, the agent's actual response,
// the exact tool call it made, and the judge's verbatim verdict — so a viewer
// can see these are real, specific attacks, not canned strings.
export function TestResults({ results }: { results: TestResultRow[] }) {
  if (results.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6 text-center text-sm text-muted-foreground">
        No test results.
      </div>
    );
  }
  const sorted = [...results].sort((a, b) => {
    const fa = a.passed ? 1 : 0;
    const fb = b.passed ? 1 : 0;
    if (fa !== fb) return fa - fb; // failures first
    return SEV_ORDER[a.severity] - SEV_ORDER[b.severity]; // then by severity
  });

  return (
    <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
      {sorted.map((r) => (
        <ResultRow key={r.id} r={r} />
      ))}
    </div>
  );
}

function formatToolCall(call: Record<string, unknown>): string {
  const name = (call.name as string) || (call.tool as string) || "tool";
  const args = (call.args ?? call.arguments ?? call.input ?? {}) as unknown;
  let argStr: string;
  try {
    argStr = JSON.stringify(args);
  } catch {
    argStr = String(args);
  }
  return `${name}(${argStr})`;
}

function ResultRow({ r }: { r: TestResultRow }) {
  const failed = r.passed === false;
  const highFail = failed && r.severity === "high";
  const [open, setOpen] = useState(highFail); // high-severity failures expanded by default

  return (
    <div className={cn(highFail && "bg-danger/[0.05]")}>
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
        {failed ? (
          <ShieldAlert className="h-4 w-4 shrink-0 text-danger" />
        ) : (
          <ShieldCheck className="h-4 w-4 shrink-0 text-success" />
        )}
        <SeverityBadge severity={r.severity} />
        <CategoryBadge category={r.category} />
        <span className="mono truncate text-sm text-foreground/90">
          {r.attack_prompt || "(empty input)"}
        </span>
        <span
          className={cn(
            "ml-auto shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider",
            failed ? "bg-danger/15 text-danger" : "bg-success/15 text-success",
          )}
        >
          {failed ? "Fail" : "Pass"}
        </span>
      </button>

      {open && (
        <div className="space-y-3 px-4 pb-4 pl-11 text-sm">
          <Field icon={<Terminal className="h-3.5 w-3.5" />} label="Attack prompt">
            <pre className="mono whitespace-pre-wrap break-words text-foreground/90">
              {r.attack_prompt || "(empty input)"}
            </pre>
          </Field>

          {r.tool_calls && r.tool_calls.length > 0 && (
            <Field icon={<Wrench className="h-3.5 w-3.5" />} label="Tool call the agent made">
              <pre className="mono whitespace-pre-wrap break-words text-amber-300/90">
                {r.tool_calls.map(formatToolCall).join("\n")}
              </pre>
            </Field>
          )}

          {r.agent_output && (
            <Field icon={<MessageSquareWarning className="h-3.5 w-3.5" />} label="Agent response">
              <pre className="mono whitespace-pre-wrap break-words text-foreground/80">
                {r.agent_output}
              </pre>
            </Field>
          )}

          {failed ? (
            <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-danger">
              <span className="font-medium">Judge verdict — failed: </span>
              {r.failure_reason || "The agent exhibited the targeted failure mode."}
            </div>
          ) : (
            <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-success/90">
              <span className="font-medium">Judge verdict — passed: </span>
              The agent resisted this attack and behaved safely.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
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
