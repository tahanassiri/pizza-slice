"use client";

import { fa } from "@/lib/i18n/fa";
import type { Market } from "@/types";
import { ConfidenceLabel } from "./ConfidenceLabel";
import { EmptyState } from "./EmptyState";
import { CountryDetail } from "./CountryDetail";

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
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-right text-ink-muted">
              <th className="px-3 py-2 font-medium">{fa.markets.rank}</th>
              <th className="px-3 py-2 font-medium">کشور</th>
              <th className="px-3 py-2 font-medium">اطمینان</th>
              <th className="px-3 py-2 font-medium">شاخص‌ها</th>
              <th className="px-3 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => (
              <tr key={m.country_code} className="border-b border-line/70 align-top">
                <td className="px-3 py-3 font-semibold">{m.rank}</td>
                <td className="px-3 py-3">
                  <p className="font-medium">{m.country_name_fa}</p>
                  <p className="text-xs text-ink-muted" dir="ltr">
                    {m.country_code}
                  </p>
                </td>
                <td className="px-3 py-3">
                  <ConfidenceLabel level={m.confidence} />
                </td>
                <td className="px-3 py-3">
                  <ul className="space-y-1 text-ink-soft">
                    {m.metrics.map((metric) => (
                      <li key={metric.key}>
                        {metric.label_fa}: {metric.value}
                        {metric.estimated ? " *" : ""}
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-3 py-3">
                  <button
                    type="button"
                    className={
                      selectedCountry === m.country_code
                        ? "nova-btn-primary !py-1.5 !text-xs"
                        : "nova-btn-ghost !py-1.5 !text-xs"
                    }
                    onClick={() => onSelect(m.country_code)}
                  >
                    {selectedCountry === m.country_code
                      ? fa.analysis.selectedCountry
                      : fa.analysis.selectCountry}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 lg:grid-cols-1">
        {markets.map((m) => (
          <CountryDetail
            key={`detail-${m.country_code}`}
            market={m}
            selected={selectedCountry === m.country_code}
          />
        ))}
      </div>
    </div>
  );
}
