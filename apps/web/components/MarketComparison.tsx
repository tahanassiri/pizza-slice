"use client";

import { fa } from "@/lib/i18n/fa";
import type { Market } from "@/types";
import { ConfidenceLabel } from "./ConfidenceLabel";
import { EmptyState } from "./EmptyState";
import { CountryDetail } from "./CountryDetail";
import { SourceBadge } from "./SourceBadge";

export function MarketComparison({
  markets,
  selectedCountry,
  onSelect,
}: {
  markets: Market[];
  selectedCountry?: string;
  onSelect: (code: string) => void;
}) {
  if (!markets.length) {
    return <EmptyState title={fa.markets.empty} hint={fa.markets.emptyHint} />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#0cb6aa]">
            {fa.markets.compare}
          </p>
          <h3 className="text-lg font-semibold text-[var(--study-ink)]">{fa.markets.title}</h3>
        </div>
        <span className="mock-banner rounded-lg px-2 py-1 text-xs font-medium">
          {fa.mockBadge}
        </span>
      </div>

      {/* Rank strip — not a dense data table */}
      <div className="grid gap-3 md:grid-cols-3">
        {markets.map((m) => {
          const selected = selectedCountry === m.country_code;
          return (
            <button
              key={`strip-${m.country_code}`}
              type="button"
              data-selected={selected}
              className="dossier-row p-4 text-right"
              onClick={() => onSelect(m.country_code)}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <span
                  className="font-display text-2xl font-bold text-[#0cb6aa]"
                  dir="ltr"
                >
                  {m.rank}
                </span>
                <ConfidenceLabel level={m.confidence} />
              </div>
              <p className="text-base font-semibold text-[var(--study-ink)]">
                {m.country_name_fa}
              </p>
              <p className="mt-1 text-xs text-[var(--study-muted)]" dir="ltr">
                {m.country_code}
              </p>
              <p className="mt-3 line-clamp-2 text-xs leading-5 text-[var(--study-muted)]">
                {m.evidence[0] ?? m.opportunities[0] ?? "—"}
              </p>
              <p className="mt-3 text-xs font-semibold text-[#0cb6aa]">
                {selected ? fa.analysis.selectedCountry : fa.analysis.selectCountry}
              </p>
            </button>
          );
        })}
      </div>

      <div className="space-y-4">
        {markets.map((m) => (
          <CountryDetail
            key={`detail-${m.country_code}`}
            market={m}
            selected={selectedCountry === m.country_code}
            onSelect={() => onSelect(m.country_code)}
          />
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {markets.flatMap((m) =>
          m.sources.slice(0, 1).map((s) => (
            <SourceBadge key={`${m.country_code}-${s.url}`} source={s} />
          ))
        )}
      </div>
    </div>
  );
}
