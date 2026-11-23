import { fa } from "@/lib/i18n/fa";
import type { Market } from "@/types";
import { ConfidenceLabel } from "./ConfidenceLabel";
import { SourceBadge } from "./SourceBadge";

export function CountryDetail({
  market,
  selected,
  onSelect,
}: {
  market: Market;
  selected?: boolean;
  onSelect?: () => void;
}) {
  return (
    <article data-selected={!!selected} className="dossier-row p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.14em] text-[#0cb6aa]">
            dossier
          </p>
          <h3 className="mt-1 text-lg font-semibold text-[var(--study-ink)]">
            <span className="inline-flex items-baseline gap-2">
              <span dir="ltr" className="text-[#0cb6aa]">
                {market.rank}
              </span>
              <span>{market.country_name_fa}</span>
            </span>
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceLabel level={market.confidence} />
          {(() => {
            const q = market.metrics.find((m) => m.key === "data_quality")?.value;
            if (!q) return null;
            return (
              <span
                className="rounded-lg border border-[var(--study-line)] px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--study-muted)]"
                dir="ltr"
              >
                {q}
              </span>
            );
          })()}
          {onSelect ? (
            <button
              type="button"
              className={
                selected
                  ? "nova-btn-primary !py-1.5 !text-xs"
                  : "rounded-xl border border-[var(--study-line)] px-3 py-1.5 text-xs font-semibold text-[var(--study-ink)]"
              }
              onClick={onSelect}
            >
              {selected ? fa.analysis.selectedCountry : fa.analysis.selectCountry}
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title={fa.markets.evidence} items={market.evidence} />
        <Section title={fa.markets.opportunities} items={market.opportunities} />
        <Section title={fa.markets.risks} items={market.risks} accent="warn" />
        <Section title={fa.markets.unknowns} items={market.unknowns} accent="muted" />
      </div>

      {market.metrics.length ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--study-line)] pt-3">
          {market.metrics.map((metric) => (
            <span
              key={metric.key}
              className="rounded-lg bg-[var(--study-bg)] px-2.5 py-1 text-xs text-[var(--study-muted)]"
            >
              {metric.label_fa}: {metric.value}
              {metric.estimated ? " *" : ""}
            </span>
          ))}
        </div>
      ) : null}

      {market.sources.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {market.sources.map((s) => (
            <SourceBadge key={s.url + s.title} source={s} />
          ))}
        </div>
      ) : null}
    </article>
  );
}

function Section({
  title,
  items,
  accent,
}: {
  title: string;
  items: string[];
  accent?: "warn" | "muted";
}) {
  if (!items.length) return null;
  return (
    <div>
      <p
        className={`mb-1 text-xs font-semibold ${
          accent === "warn"
            ? "text-[#9a6700]"
            : accent === "muted"
              ? "text-[var(--study-muted)]"
              : "text-[var(--study-ink)]"
        }`}
      >
        {title}
      </p>
      <ul className="space-y-1.5 text-sm leading-6 text-[var(--study-muted)]">
        {items.map((item) => (
          <li key={item} className="border-r-2 border-[#0cb6aa]/35 pr-2">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
