import Link from "next/link";
import { fa } from "@/lib/i18n/fa";
import type { Run } from "@/types";
import { CockpitStatusPill } from "./CockpitStatusPill";

export function CockpitHeader({ run }: { run: Run }) {
  return (
    <header className="mb-4 flex min-w-0 flex-wrap items-start justify-between gap-3 border-b border-[var(--cockpit-line)] pb-4 sm:mb-5 sm:gap-4 sm:pb-5">
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Link
            href="/"
            className="font-display shrink-0 text-lg font-extrabold tracking-tight text-white sm:text-2xl"
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
        <div className="min-w-0">
          <p className="text-[0.65rem] font-medium uppercase tracking-[0.18em] text-[var(--cockpit-gold)]">
            {fa.cockpit.cockpitLabel}
          </p>
          <h1 className="mt-1 truncate text-xl font-semibold text-white sm:text-3xl">
            {run.product}
          </h1>
          <p className="mt-1 break-words text-sm text-[var(--cockpit-muted)]">
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

      <div className="flex w-full min-w-0 flex-row flex-wrap items-center justify-between gap-2 sm:w-auto sm:flex-col sm:items-end">
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
