import { fa } from "@/lib/i18n/fa";
import type { Run, RunEvent, RunStatus } from "@/types";

function heroCopy(status: RunStatus): string {
  if (status === "queued") return fa.cockpit.researchQueued;
  if (status === "partial") return fa.cockpit.researchPartial;
  if (status === "completed") return fa.cockpit.researchDone;
  if (
    status === "failed" ||
    status === "rate_limited" ||
    status === "provider_unavailable"
  ) {
    return fa.cockpit.researchBlocked;
  }
  return fa.cockpit.researchLive;
}

function tone(status: RunStatus): string {
  if (status === "completed") return "from-[rgba(12,182,170,0.22)] to-transparent";
  if (status === "partial" || status === "rate_limited")
    return "from-[rgba(230,183,101,0.2)] to-transparent";
  if (
    status === "failed" ||
    status === "provider_unavailable"
  )
    return "from-[rgba(240,113,103,0.22)] to-transparent";
  return "from-[rgba(12,182,170,0.18)] to-transparent";
}

export function ResearchHero({
  run,
  latest,
}: {
  run: Run;
  latest?: RunEvent;
}) {
  const live = run.status === "running" || run.status === "queued";
  const blocked =
    run.status === "failed" ||
    run.status === "rate_limited" ||
    run.status === "provider_unavailable";

  return (
    <section
      className={`cockpit-panel relative overflow-hidden p-5 sm:p-7 ${live ? "cockpit-hero-scan" : ""}`}
    >
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-l ${tone(run.status)}`}
        aria-hidden
      />
      <div className="absolute inset-y-4 end-0 w-1 rounded-full bg-[var(--cockpit-gold)]/80" aria-hidden />

      <div className="relative z-[1] grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`cockpit-chip ${
                blocked
                  ? "border-[color-mix(in_srgb,var(--cockpit-danger)_50%,transparent)] bg-[var(--cockpit-danger-soft)] text-[var(--cockpit-danger)]"
                  : "cockpit-chip-live"
              }`}
            >
              {live ? <span className="h-1.5 w-1.5 rounded-full bg-current cockpit-node-live" /> : null}
              {heroCopy(run.status)}
            </span>
            {latest ? (
              <span className="text-[0.7rem] text-[var(--cockpit-faint)]">
                {fa.cockpit.currentBeat} · {fa.phase[latest.phase] ?? latest.phase}
              </span>
            ) : null}
          </div>

          <h2
            className={`text-2xl font-semibold leading-snug tracking-tight sm:text-4xl ${
              blocked ? "text-[var(--cockpit-danger)]" : "text-white"
            }`}
          >
            {latest?.message_fa ?? fa.cockpit.noResults}
          </h2>

          {run.error ? (
            <p className="text-sm text-[var(--cockpit-danger)]">{run.error.message_fa}</p>
          ) : (
            <p className="max-w-2xl text-sm leading-7 text-[var(--cockpit-muted)]">
              مسیر شناخت محصول تا پیشنهاد بازار به‌صورت مرحله‌ای به‌روز می‌شود. این پیش‌نمایش
              آزمایشی است و ادعای تحقیق زنده ندارد.
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-[var(--cockpit-line-strong)] bg-black/35 px-4 py-3 text-left shadow-[0_0_40px_rgba(12,182,170,0.08)]" dir="ltr">
          <p className="text-[0.65rem] uppercase tracking-[0.18em] text-[var(--cockpit-faint)]">
            run
          </p>
          <p className="font-mono text-sm text-[var(--cockpit-teal)]">{run.id}</p>
          <p className="mt-2 text-[0.65rem] uppercase tracking-[0.18em] text-[var(--cockpit-faint)]">
            fixture
          </p>
          <p className="text-xs text-[var(--cockpit-muted)]">{run.fixture_id}</p>
        </div>
      </div>
    </section>
  );
}
