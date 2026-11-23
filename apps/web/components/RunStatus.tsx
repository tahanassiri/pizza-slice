import { fa } from "@/lib/i18n/fa";
import type { RunStatus as Status } from "@/types";

const tone: Record<Status, string> = {
  idle: "bg-fog text-ink-soft",
  queued: "bg-[var(--accent-soft)] text-accent",
  running: "bg-[var(--accent-soft)] text-accent",
  partial: "bg-[var(--warn-soft)] text-[var(--warn)]",
  completed: "bg-[var(--ok-soft)] text-[var(--ok)]",
  failed: "bg-[var(--danger-soft)] text-[var(--danger)]",
  rate_limited: "bg-[var(--warn-soft)] text-[var(--warn)]",
  provider_unavailable: "bg-[var(--danger-soft)] text-[var(--danger)]",
  cancelled: "bg-fog text-ink-muted",
  interrupted: "bg-[var(--warn-soft)] text-[var(--warn)]",
};

export function RunStatus({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center rounded-lg px-2.5 py-1 text-xs font-semibold ${tone[status]}`}
    >
      {fa.status[status] ?? status}
    </span>
  );
}
