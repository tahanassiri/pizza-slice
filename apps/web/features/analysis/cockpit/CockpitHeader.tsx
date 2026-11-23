import Link from "next/link";
import { fa } from "@/lib/i18n/fa";
import type { Run } from "@/types";
import { CockpitStatusPill } from "./CockpitStatusPill";

export function CockpitHeader({ run }: { run: Run }) {
  return (
    <header className="mb-5 flex flex-wrap items-start justify-between gap-4 border-b border-[var(--cockpit-line)] pb-5">
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/"
            className="font-display text-xl font-bold tracking-tight text-white sm:text-2xl"
          >
            {fa.brand}
          </Link>
          <span className="hidden text-sm text-[var(--cockpit-faint)] sm:inline">
            {fa.brandSubtitle}
          </span>
          {run.is_mock ? (
            <>
              <span className="cockpit-chip-mock cockpit-chip">{fa.mockPreviewBadge}</span>
              <span className="cockpit-chip-mock cockpit-chip">{fa.mockBadge}</span>
            </>
          ) : null}
        </div>
        <div>
          <p className="text-[0.65rem] font-medium uppercase tracking-[0.18em] text-[var(--cockpit-gold)]">
            {fa.cockpit.cockpitLabel}
          </p>
          <h1 className="mt-1 truncate text-2xl font-semibold text-white sm:text-3xl">
            {run.product}
          </h1>
          <p className="mt-1 text-sm text-[var(--cockpit-muted)]">
            {run.origin_country}
            {run.guessed_hs_code ? (
              <>
                {" · "}
                {fa.analysis.hsGuess}:{" "}
                <span dir="ltr" className="text-[var(--cockpit-teal)]">
                  {run.guessed_hs_code}
                </span>
              </>
            ) : null}
          </p>
        </div>
      </div>

      <div className="flex flex-col items-stretch gap-2 sm:items-end">
        <CockpitStatusPill status={run.status} />
        <Link
          href="/"
          className="rounded-xl border border-[var(--cockpit-line)] px-3 py-1.5 text-xs font-medium text-[var(--cockpit-muted)] transition hover:border-[var(--cockpit-teal)] hover:text-white"
        >
          {fa.analysis.backHome}
        </Link>
      </div>
    </header>
  );
}
