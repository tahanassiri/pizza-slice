"use client";

import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import type { Market } from "@/types";
import { ConfidenceLabel } from "./ConfidenceLabel";
import { EmptyState } from "./EmptyState";
import { CountryDetail } from "./CountryDetail";
import { SourceBadge } from "./SourceBadge";

function recommendationOf(m: Market): string {
  return m.metrics.find((x) => x.key === "recommendation")?.value ?? "recommended";
}

function MarketRow({
  m,
  selectedCountry,
  onSelect,
  selecting,
  openWhy,
  setOpenWhy,
}: {
  m: Market;
  selectedCountry?: string;
  onSelect: (code: string) => void;
  selecting?: boolean;
  openWhy: string | null;
  setOpenWhy: (code: string | null) => void;
}) {
  const selected = selectedCountry === m.country_code;
  const whyOpen = openWhy === m.country_code;
  const quality = m.metrics.find((x) => x.key === "data_quality")?.value;
  const share = m.metrics.find((x) => x.key === "pool_share");
  const year = m.metrics.find((x) => x.key === "reference_year")?.value;
  const scope = m.metrics.find((x) => x.key === "data_scope")?.value;
  const risky = recommendationOf(m) === "risky";

  return (
    <li key={m.country_code} className="bg-transparent">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 sm:gap-3">
        <span
          className={`font-display w-7 shrink-0 text-lg font-bold ${
            risky ? "text-[#b45309]" : "text-[#0cb6aa]"
          }`}
          dir="ltr"
        >
          {risky ? "!" : m.rank}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-[var(--study-ink)]">
            {m.country_name_fa}
            <span className="ms-2 text-[0.7rem] font-normal text-[var(--study-muted)]" dir="ltr">
              {m.country_code}
            </span>
          </p>
          <p className="truncate text-[0.7rem] text-[var(--study-muted)]">
            {share
              ? `${fa.markets.share}: ${share.value}${share.unit ?? ""}`
              : m.evidence[0]?.slice(0, 72) ?? "—"}
            {year ? ` · ${year}` : ""}
            {quality ? ` · ${quality}` : ""}
            {scope ? ` · ${scope}` : ""}
          </p>
          {scope === "sector" || scope === "total" ? (
            <p className="mt-0.5 text-[0.65rem] text-[#9a6700]">{fa.markets.sectorWarning}</p>
          ) : null}
        </div>
        <ConfidenceLabel level={m.confidence} />
        <button
          type="button"
          className="rounded-lg border border-[var(--study-line)] px-2.5 py-1 text-[0.7rem] font-semibold text-[var(--study-ink)] hover:border-[#0cb6aa]/50"
          onClick={() => setOpenWhy(whyOpen ? null : m.country_code)}
          aria-expanded={whyOpen}
        >
          {whyOpen ? fa.markets.showLess : fa.markets.showMore}
        </button>
        <button
          type="button"
          disabled={selecting}
          className={
            selected
              ? "nova-btn-primary !py-1.5 !text-xs"
              : "rounded-xl border border-[var(--study-line)] px-3 py-1.5 text-xs font-semibold text-[var(--study-ink)] disabled:opacity-50"
          }
          onClick={() => onSelect(m.country_code)}
        >
          {selected ? fa.analysis.selectedCountry : fa.analysis.selectCountry}
        </button>
      </div>
      {whyOpen ? (
        <div className="animate-fade-up border-t border-[var(--study-line)] bg-[var(--study-bg)]/80 px-3 py-3">
          <p className="mb-2 text-xs font-semibold text-[var(--study-ink)]">{fa.markets.whyTitle}</p>
          <CountryDetail
            market={m}
            selected={selected}
            compact
            onSelect={() => onSelect(m.country_code)}
          />
        </div>
      ) : null}
    </li>
  );
}

export function MarketComparison({
  markets,
  selectedCountry,
  onSelect,
  selecting,
}: {
  markets: Market[];
  selectedCountry?: string;
  onSelect: (code: string) => void;
  selecting?: boolean;
}) {
  const [openWhy, setOpenWhy] = useState<string | null>(null);

  if (!markets.length) {
    return <EmptyState title={fa.markets.empty} hint={fa.markets.emptyHint} />;
  }

  const recommended = markets.filter((m) => recommendationOf(m) !== "risky");
  const risky = markets.filter((m) => recommendationOf(m) === "risky");
  const primary = recommended.length ? recommended : markets;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#0cb6aa]">
            {fa.markets.compare}
          </p>
          <h3 className="text-lg font-semibold text-[var(--study-ink)]">{fa.markets.title}</h3>
          <p className="mt-1 text-xs text-[var(--study-muted)]">{fa.markets.compactHint}</p>
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold text-[var(--study-ink)]">
          {fa.markets.recommendedTitle}
        </p>
        <ul className="divide-y divide-[var(--study-line)] overflow-hidden rounded-xl border border-[var(--study-line)] bg-white/40">
          {primary.map((m) => (
            <MarketRow
              key={m.country_code}
              m={m}
              selectedCountry={selectedCountry}
              onSelect={onSelect}
              selecting={selecting}
              openWhy={openWhy}
              setOpenWhy={setOpenWhy}
            />
          ))}
        </ul>
      </div>

      {risky.length ? (
        <div>
          <p className="mb-1 text-xs font-semibold text-[#9a6700]">{fa.markets.riskyTitle}</p>
          <p className="mb-2 text-[0.7rem] text-[var(--study-muted)]">{fa.markets.riskyHint}</p>
          <ul className="divide-y divide-[var(--study-line)] overflow-hidden rounded-xl border border-[#e6b765]/40 bg-[#fff8eb]/60">
            {risky.map((m) => (
              <MarketRow
                key={m.country_code}
                m={m}
                selectedCountry={selectedCountry}
                onSelect={onSelect}
                selecting={selecting}
                openWhy={openWhy}
                setOpenWhy={setOpenWhy}
              />
            ))}
          </ul>
        </div>
      ) : null}

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
