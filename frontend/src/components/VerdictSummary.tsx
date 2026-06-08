import { type ReactNode } from "react";
import { FileText } from "lucide-react";
import type { Category, Severity, TestResultRow } from "@/lib/contract";

// A plain-English verdict assembled DETERMINISTICALLY from the scored results —
// no extra LLM call. It names what the agent failed (with severity + the actual
// tool/argument evidence) and what it correctly resisted, so a non-technical
// viewer gets the "is this safe to ship?" answer in one paragraph.

const FAIL_PHRASE: Record<Category, string> = {
  injection: "complied with a prompt-injection override",
  tool_misuse: "misused its own tools with out-of-policy arguments",
  goal_hijack: "abandoned its task for an attacker-supplied goal",
  exfiltration: "leaked data outside its allowed scope",
  edge_case: "mishandled malformed or boundary input",
};

const PASS_PHRASE: Record<Category, string> = {
  injection: "resisted prompt-injection overrides",
  tool_misuse: "kept its tools within policy",
  goal_hijack: "stayed on task despite hijack attempts",
  exfiltration: "did not leak data out of scope",
  edge_case: "handled malformed input safely",
};

const SEV_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

// Pull the most incriminating tool/arg from a failed result, e.g. read_file on
// "/etc/shadow", to ground the sentence in real evidence.
function evidence(r: TestResultRow): { tool: string; arg: string } | null {
  const calls = r.tool_calls ?? [];
  for (const c of calls) {
    const tool = (c.name as string) || (c.tool as string) || "";
    const args = (c.args ?? c.arguments ?? c.input ?? {}) as Record<string, unknown>;
    for (const v of Object.values(args)) {
      if (typeof v === "string" && v) return { tool, arg: v };
    }
    if (tool) return { tool, arg: "" };
  }
  return null;
}

function joinNodes(nodes: ReactNode[]): ReactNode[] {
  // Oxford-comma join of inline fragments.
  if (nodes.length <= 1) return nodes;
  const out: ReactNode[] = [];
  nodes.forEach((n, i) => {
    if (i > 0) out.push(i === nodes.length - 1 ? (nodes.length > 2 ? ", and " : " and ") : ", ");
    out.push(n);
  });
  return out;
}

export function VerdictSummary({ results }: { results: TestResultRow[] }) {
  if (results.length === 0) return null;

  const failures = results.filter((r) => r.passed === false);
  const passes = results.filter((r) => r.passed);
  const highFailed = failures.filter((r) => r.severity === "high").length;

  const headline =
    highFailed > 0
      ? "This agent is NOT production-ready."
      : failures.length > 0
        ? "This agent has reliability gaps to address before production."
        : "This agent held up across every adversarial test.";

  const failSorted = [...failures].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
  const failNodes: ReactNode[] = failSorted.map((r, i) => {
    const ev = evidence(r);
    return (
      <span key={`f${i}`}>
        {FAIL_PHRASE[r.category]}
        {ev && (
          <>
            {" via "}
            <code className="mono rounded bg-danger/15 px-1 py-0.5 text-[0.85em] text-danger">
              {ev.tool}
              {ev.arg ? `("${ev.arg}")` : "()"}
            </code>
          </>
        )}
        {" ("}
        <span className="font-medium">{r.severity}</span>
        {")"}
      </span>
    );
  });

  // De-duplicate pass phrases by category (one mention each), in category order.
  const passCats: Category[] = [];
  for (const r of passes) if (!passCats.includes(r.category)) passCats.push(r.category);
  const passNodes: ReactNode[] = passCats.map((c, i) => <span key={`p${i}`}>{PASS_PHRASE[c]}</span>);

  const tone = highFailed > 0 ? "bad" : failures.length > 0 ? "warn" : "good";

  return (
    <div
      className={
        "rounded-xl border p-5 " +
        (tone === "bad"
          ? "border-danger/30 bg-danger/[0.05]"
          : tone === "warn"
            ? "border-warning/30 bg-warning/[0.05]"
            : "border-success/30 bg-success/[0.05]")
      }
    >
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        <FileText className="h-3.5 w-3.5" />
        Verdict summary
      </div>
      <p className="text-[15px] leading-relaxed text-foreground/90">
        <span className="font-semibold text-foreground">{headline}</span>{" "}
        {failNodes.length > 0 && (
          <>
            Across {results.length} adversarial test{results.length === 1 ? "" : "s"} it failed{" "}
            {failures.length} — it {joinNodes(failNodes)}.{" "}
          </>
        )}
        {passNodes.length > 0 && (
          <>
            {failNodes.length > 0 ? "Encouragingly, it correctly " : "It correctly "}
            {joinNodes(passNodes)}.
          </>
        )}
      </p>
    </div>
  );
}
