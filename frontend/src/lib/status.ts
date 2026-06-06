// Run status lifecycle, shared by the stepper and the dashboard.
export const STATUS_ORDER = [
  "pending",
  "cloning",
  "introspecting",
  "generating",
  "running",
  "scoring",
  "done",
] as const;

export type RunStatus = (typeof STATUS_ORDER)[number] | "error";

export function statusRank(s: string): number {
  return (STATUS_ORDER as readonly string[]).indexOf(s);
}

export function isTerminal(s: string): boolean {
  return s === "done" || s === "error";
}

export const PIPELINE_STEPS: { key: string; label: string }[] = [
  { key: "cloning", label: "Clone" },
  { key: "introspecting", label: "Introspect" },
  { key: "generating", label: "Generate" },
  { key: "running", label: "Run" },
  { key: "scoring", label: "Score" },
];

export type StepState = "done" | "active" | "pending" | "idle";

export function stepState(stepKey: string, status: string): StepState {
  if (status === "error") return "idle";
  if (status === "done") return "done";
  const cur = statusRank(status);
  const step = statusRank(stepKey);
  if (cur > step) return "done";
  if (cur === step) return "active";
  return "pending";
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleDateString();
}
