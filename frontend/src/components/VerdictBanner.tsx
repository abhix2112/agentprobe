import { ShieldCheck, ShieldAlert, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export function VerdictBanner({
  passed,
  total,
  failed,
  highFailed,
  truncated,
  truncatedReason,
}: {
  passed: boolean | null;
  total: number;
  failed: number;
  highFailed: number;
  truncated?: boolean;
  truncatedReason?: string | null;
}) {
  const fail = passed === false;
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border p-6",
        fail
          ? "border-danger/40 bg-danger/10"
          : "border-success/35 bg-success/10",
      )}
    >
      <div
        className={cn(
          "pointer-events-none absolute inset-0 opacity-60",
          fail
            ? "bg-[radial-gradient(40rem_18rem_at_15%_-6rem,hsl(0_72%_55%/.25),transparent)]"
            : "bg-[radial-gradient(40rem_18rem_at_15%_-6rem,hsl(152_60%_45%/.22),transparent)]",
        )}
      />
      <div className="relative flex items-center gap-4">
        <div
          className={cn(
            "flex h-14 w-14 shrink-0 items-center justify-center rounded-xl",
            fail ? "bg-danger/20 text-danger" : "bg-success/20 text-success",
          )}
        >
          {fail ? <ShieldAlert className="h-7 w-7" /> : <ShieldCheck className="h-7 w-7" />}
        </div>
        <div className="flex-1">
          <div
            className={cn(
              "text-2xl font-semibold tracking-tight",
              fail ? "text-danger" : "text-success",
            )}
          >
            {fail ? "Vulnerabilities found" : "No high-severity failures"}
          </div>
          <div className="mt-0.5 text-sm text-muted-foreground">
            {fail ? (
              <>
                <span className="font-medium text-foreground">{highFailed}</span> high-severity
                failure{highFailed === 1 ? "" : "s"} · {failed}/{total} tests failed
              </>
            ) : (
              <>
                {total - failed}/{total} tests passed · the agent resisted every high-severity
                attack
              </>
            )}
          </div>
        </div>
        <div
          className={cn(
            "rounded-lg px-3 py-1.5 text-sm font-bold uppercase tracking-wider",
            fail ? "bg-danger text-white" : "bg-success text-white",
          )}
        >
          {fail ? "Fail" : "Pass"}
        </div>
      </div>

      {truncated && (
        <div className="relative mt-4 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Run truncated — the LLM-call budget was reached.{" "}
            {truncatedReason && <span className="text-warning/80">{truncatedReason}</span>}
          </span>
        </div>
      )}
    </div>
  );
}
