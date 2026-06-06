import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { PIPELINE_STEPS, stepState, isTerminal } from "@/lib/status";

export function PipelineStepper({ status }: { status: string }) {
  const errored = status === "error";
  return (
    <div className="flex items-center">
      {PIPELINE_STEPS.map((step, i) => {
        const state = stepState(step.key, status);
        const last = i === PIPELINE_STEPS.length - 1;
        return (
          <div key={step.key} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-2">
              <div
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full border text-xs transition-colors",
                  state === "done" && "border-success/40 bg-success/15 text-success",
                  state === "active" && "border-primary/50 bg-primary/15 text-primary",
                  (state === "pending" || state === "idle") &&
                    "border-border bg-surface-2 text-muted-foreground",
                  errored && "border-danger/40 bg-danger/10 text-danger/70",
                )}
              >
                {state === "done" ? (
                  <Check className="h-4 w-4" />
                ) : state === "active" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                )}
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium",
                  state === "active" ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
            </div>
            {!last && (
              <div
                className={cn(
                  "mx-2 mb-5 h-px flex-1 transition-colors",
                  state === "done" ? "bg-success/40" : "bg-border",
                )}
              />
            )}
          </div>
        );
      })}
      {/* terminal marker */}
      <div className="ml-2 flex flex-col items-center gap-2">
        <div
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-full border text-xs",
            status === "done" && "border-success/40 bg-success/15 text-success",
            errored && "border-danger/50 bg-danger/15 text-danger",
            !isTerminal(status) && "border-border bg-surface-2 text-muted-foreground",
          )}
        >
          {status === "done" ? (
            <Check className="h-4 w-4" />
          ) : errored ? (
            <span className="font-bold">!</span>
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
          )}
        </div>
        <span className="text-[11px] font-medium text-muted-foreground">
          {errored ? "Failed" : "Done"}
        </span>
      </div>
    </div>
  );
}
