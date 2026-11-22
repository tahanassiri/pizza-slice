import { fa } from "@/lib/i18n/fa";
import type { ScenarioResult } from "@/types";

function fmt(n: number | null): string {
  if (n === null || Number.isNaN(n)) return fa.feasibility.unknown;
  return n.toLocaleString("fa-IR");
}

export function ScenarioComparison({ scenarios }: { scenarios: ScenarioResult[] }) {
  return (
    <div className="nova-panel p-4">
      <h3 className="mb-3 font-semibold">{fa.feasibility.scenarios}</h3>
      <div className="grid gap-3 md:grid-cols-3">
        {scenarios.map((s) => (
          <div key={s.id} className="rounded-xl border border-line bg-white/70 p-3">
            <p className="mb-2 font-medium">{s.label_fa}</p>
            <dl className="space-y-1 text-sm text-ink-soft">
              <div className="flex justify-between gap-2">
                <dt>{fa.feasibility.revenue}</dt>
                <dd dir="ltr">{fmt(s.revenue)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>{fa.feasibility.cost}</dt>
                <dd dir="ltr">{fmt(s.total_cost)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>{fa.feasibility.margin}</dt>
                <dd dir="ltr">
                  {fmt(s.margin)}
                  {s.margin_pct !== null ? ` (${fmt(s.margin_pct)}%)` : ""}
                </dd>
              </div>
            </dl>
            {s.notes_fa.length ? (
              <ul className="mt-2 list-disc pr-4 text-xs text-ink-muted">
                {s.notes_fa.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
