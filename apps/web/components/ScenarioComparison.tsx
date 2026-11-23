import { fa } from "@/lib/i18n/fa";
import type { ScenarioResult } from "@/types";

function fmt(n: number | null): string {
  if (n === null || Number.isNaN(n)) return fa.feasibility.unknown;
  return n.toLocaleString("fa-IR");
}

const accent: Record<ScenarioResult["id"], string> = {
  conservative: "border-[#9a6700]/40",
  base: "border-[#0cb6aa]/50",
  optimistic: "border-[#027a48]/40",
};

export function ScenarioComparison({ scenarios }: { scenarios: ScenarioResult[] }) {
  return (
    <div>
      <div className="mb-3 flex items-end justify-between gap-2">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.14em] text-[#0cb6aa]">
            scenarios
          </p>
          <h3 className="font-semibold text-[var(--study-ink)]">{fa.feasibility.scenarios}</h3>
        </div>
        <p className="text-xs text-[#9a6700]">{fa.feasibility.sampleNote}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {scenarios.map((s) => (
          <div
            key={s.id}
            className={`rounded-2xl border bg-white p-4 ${accent[s.id]} ${
              s.id === "base" ? "shadow-[0_12px_30px_rgba(12,27,42,0.08)]" : ""
            }`}
          >
            <p className="mb-3 text-sm font-semibold text-[var(--study-ink)]">{s.label_fa}</p>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-2 text-[var(--study-muted)]">
                <dt>{fa.feasibility.revenue}</dt>
                <dd className="font-medium text-[var(--study-ink)]" dir="ltr">
                  {fmt(s.revenue)}
                </dd>
              </div>
              <div className="flex justify-between gap-2 text-[var(--study-muted)]">
                <dt>{fa.feasibility.cost}</dt>
                <dd className="font-medium text-[var(--study-ink)]" dir="ltr">
                  {fmt(s.total_cost)}
                </dd>
              </div>
              <div className="flex justify-between gap-2 border-t border-[var(--study-line)] pt-2">
                <dt className="font-medium text-[var(--study-ink)]">{fa.feasibility.margin}</dt>
                <dd className="font-semibold text-[#0cb6aa]" dir="ltr">
                  {fmt(s.margin)}
                  {s.margin_pct !== null ? ` (${fmt(s.margin_pct)}%)` : ""}
                </dd>
              </div>
            </dl>
            {s.notes_fa.length ? (
              <ul className="mt-3 space-y-1 text-xs text-[var(--study-muted)]">
                {s.notes_fa.map((n) => (
                  <li key={n}>• {n}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
