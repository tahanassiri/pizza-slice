import { fa } from "@/lib/i18n/fa";
import type { Market } from "@/types";
import { ConfidenceLabel } from "./ConfidenceLabel";
import { SourceBadge } from "./SourceBadge";

export function CountryDetail({
  market,
  selected,
}: {
  market: Market;
  selected?: boolean;
}) {
  return (
    <article
      className={`nova-panel p-5 ${selected ? "ring-2 ring-[var(--accent)]" : ""}`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">
          <span className="inline-flex items-baseline gap-2">
            <span dir="ltr">{market.rank}</span>
            <span>{market.country_name_fa}</span>
          </span>
        </h3>
        <ConfidenceLabel level={market.confidence} />
      </div>

      <Section title={fa.markets.evidence} items={market.evidence} />
      <Section title={fa.markets.opportunities} items={market.opportunities} />
      <Section title={fa.markets.risks} items={market.risks} />
      <Section title={fa.markets.unknowns} items={market.unknowns} />

      {market.sources.length ? (
        <div className="mt-3">
          <p className="mb-2 text-sm font-medium text-ink-soft">{fa.markets.sources}</p>
          <div className="flex flex-wrap gap-2">
            {market.sources.map((s) => (
              <SourceBadge key={s.url + s.title} source={s} />
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mb-3">
      <p className="mb-1 text-sm font-medium text-ink-soft">{title}</p>
      <ul className="list-disc space-y-1 pr-5 text-sm text-ink-muted">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
