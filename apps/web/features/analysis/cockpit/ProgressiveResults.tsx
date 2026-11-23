import { fa } from "@/lib/i18n/fa";
import type { ConfidenceLevel, Market, RunStatus } from "@/types";
import { LoadingState } from "@/components/LoadingState";

function CockpitConfidence({ level }: { level: ConfidenceLevel }) {
  const tone =
    level === "high"
      ? "text-[var(--cockpit-ok)]"
      : level === "medium"
        ? "text-[var(--cockpit-gold)]"
        : level === "low"
          ? "text-[var(--cockpit-danger)]"
          : "text-[var(--cockpit-faint)]";
  return <span className={`text-[0.7rem] font-semibold ${tone}`}>{fa.confidence[level]}</span>;
}

export function ProgressiveResults({
  markets,
  status,
  onOpenMarkets,
}: {
  markets: Market[];
  status: RunStatus;
  onOpenMarkets: () => void;
}) {
  const blocked =
    status === "provider_unavailable" || status === "rate_limited" || status === "failed";

  return (
    <section className="cockpit-panel min-w-0 overflow-hidden p-3 sm:p-4">
      <div className="mb-3 flex min-w-0 items-center justify-between gap-2">
        <h3 className="truncate text-sm font-semibold text-white">{fa.cockpit.progressive}</h3>
        <span className="shrink-0 text-[0.7rem] text-[var(--cockpit-muted)]">
          {fa.cockpit.marketsReady}: {markets.length}
        </span>
      </div>

      {blocked && !markets.length ? (
        <p className="text-sm text-[var(--cockpit-danger)]">
          {status === "rate_limited" ? fa.error.quota : fa.error.unavailable}
        </p>
      ) : null}

      {!markets.length && !blocked ? (
        status === "running" || status === "queued" ? (
          <LoadingState
            label={fa.cockpit.noResults}
            hint={fa.cockpit.noResultsHint}
            stages={[
              fa.loading.stages.prepare,
              fa.loading.stages.fetch,
              fa.loading.stages.analyze,
              fa.loading.stages.almost,
            ]}
          />
        ) : (
          <div className="rounded-xl border border-dashed border-[var(--cockpit-line)] px-3 py-6 text-center">
            <p className="text-sm font-medium text-white">{fa.cockpit.noResults}</p>
            <p className="mt-1 text-xs text-[var(--cockpit-muted)]">{fa.cockpit.noResultsHint}</p>
          </div>
        )
      ) : null}

      {markets.length ? (
        <ul className="space-y-2">
          {markets.map((m) => (
            <li
              key={m.country_code}
              className="rounded-xl border border-[var(--cockpit-line)] bg-black/20 px-3 py-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium text-white">
                  <span dir="ltr" className="me-2 text-[var(--cockpit-gold)]">
                    {m.rank}
                  </span>
                  {m.country_name_fa}
                </p>
                <CockpitConfidence level={m.confidence} />
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-[var(--cockpit-muted)]">
                {m.evidence[0] ?? m.opportunities[0] ?? "—"}
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      {markets.length ? (
        <button
          type="button"
          onClick={onOpenMarkets}
          className="mt-3 w-full rounded-xl border border-[var(--cockpit-teal)] bg-[var(--cockpit-teal-soft)] px-3 py-2 text-sm font-semibold text-[var(--cockpit-teal)] transition hover:bg-[var(--cockpit-teal)] hover:text-[#041016]"
        >
          {fa.analysis.tabs.markets}
        </button>
      ) : null}
    </section>
  );
}
