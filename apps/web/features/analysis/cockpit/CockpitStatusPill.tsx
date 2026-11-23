import { fa } from "@/lib/i18n/fa";
import type { RunStatus } from "@/types";

const map: Record<RunStatus, { label: string; className: string }> = {
  idle: { label: fa.status.idle, className: "text-[var(--cockpit-muted)] border-[var(--cockpit-line)]" },
  queued: { label: fa.status.queued, className: "text-[var(--cockpit-teal)] border-[color-mix(in_srgb,var(--cockpit-teal)_45%,transparent)] bg-[var(--cockpit-teal-soft)]" },
  running: { label: fa.status.running, className: "text-[var(--cockpit-teal)] border-[color-mix(in_srgb,var(--cockpit-teal)_45%,transparent)] bg-[var(--cockpit-teal-soft)]" },
  partial: { label: fa.status.partial, className: "text-[var(--cockpit-gold)] border-[color-mix(in_srgb,var(--cockpit-gold)_45%,transparent)] bg-[var(--cockpit-gold-soft)]" },
  completed: { label: fa.status.completed, className: "text-[var(--cockpit-ok)] border-[color-mix(in_srgb,var(--cockpit-ok)_40%,transparent)] bg-[rgba(61,214,140,0.12)]" },
  failed: { label: fa.status.failed, className: "text-[var(--cockpit-danger)] border-[color-mix(in_srgb,var(--cockpit-danger)_45%,transparent)] bg-[var(--cockpit-danger-soft)]" },
  rate_limited: { label: fa.status.rate_limited, className: "text-[var(--cockpit-gold)] border-[color-mix(in_srgb,var(--cockpit-gold)_45%,transparent)] bg-[var(--cockpit-gold-soft)]" },
  provider_unavailable: { label: fa.status.provider_unavailable, className: "text-[var(--cockpit-danger)] border-[color-mix(in_srgb,var(--cockpit-danger)_45%,transparent)] bg-[var(--cockpit-danger-soft)]" },
  cancelled: { label: fa.status.cancelled, className: "text-[var(--cockpit-muted)] border-[var(--cockpit-line)]" },
  interrupted: { label: fa.status.interrupted, className: "text-[var(--cockpit-gold)] border-[color-mix(in_srgb,var(--cockpit-gold)_45%,transparent)] bg-[var(--cockpit-gold-soft)]" },
};

export function CockpitStatusPill({ status }: { status: RunStatus }) {
  const s = map[status];
  return (
    <span className={`cockpit-chip max-w-[9rem] shrink-0 truncate sm:max-w-none ${s.className}`}>
      {(status === "running" || status === "queued") && (
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current cockpit-node-live" />
      )}
      <span className="truncate">{s.label}</span>
    </span>
  );
}
