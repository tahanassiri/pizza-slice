"use client";

import { fa } from "@/lib/i18n/fa";
import type { CostItem, FeasibilityAssumptions } from "@/types";

const numberFields = [
  ["quantity", fa.feasibility.quantity],
  ["target_sell_price_usd", fa.feasibility.sellPrice],
  ["fx_rate_usd_irr", fa.feasibility.fxRate],
] as const;

export function CostEditor({
  items,
  assumptions,
  onChange,
  onAssumptionChange,
}: {
  items: CostItem[];
  assumptions: FeasibilityAssumptions;
  onChange: (id: string, update: Partial<Pick<CostItem, "amount" | "currency">>) => void;
  onAssumptionChange: (key: keyof FeasibilityAssumptions, value: string | number | null) => void;
}) {
  return (
    <div className="dossier-row p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-[var(--study-ink)]">{fa.feasibility.editor}</h3>
        </div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm text-[var(--study-ink)]">
          {fa.feasibility.unit}
          <input
            className="nova-input mt-1 !bg-white !text-[var(--study-ink)]"
            maxLength={40}
            value={assumptions.unit ?? ""}
            onChange={(e) => onAssumptionChange("unit", e.currentTarget.value || null)}
          />
        </label>
        {numberFields.map(([field, label]) => (
          <label key={field} className="text-sm text-[var(--study-ink)]">
            {label}
            <input
              className="nova-input mt-1 !bg-white !text-[var(--study-ink)]"
              type="number"
              min="0"
              step="any"
              dir="ltr"
              value={assumptions[field] ?? ""}
              placeholder={fa.feasibility.unknown}
              onChange={(e) => onAssumptionChange(field, e.currentTarget.value === "" ? null : e.currentTarget.valueAsNumber)}
            />
          </label>
        ))}
        <label className="text-sm text-[var(--study-ink)]">
          {fa.feasibility.incoterm}
          <input
            className="nova-input mt-1 !bg-white !text-[var(--study-ink)]"
            dir="ltr"
            maxLength={3}
            pattern="[A-Za-z]{3}"
            value={assumptions.incoterm ?? ""}
            onChange={(e) => onAssumptionChange("incoterm", e.currentTarget.value.toUpperCase() || null)}
          />
        </label>
      </div>

      <p className="mb-2 text-sm text-[var(--study-muted)]">{fa.feasibility.costHint}</p>
      <div className="divide-y divide-[var(--study-line)]">
        {items.map((item) => (
          <div
            key={item.id}
            className="grid gap-2 py-3 sm:grid-cols-[1fr_15rem] sm:items-center"
          >
            <label className="text-sm text-[var(--study-ink)]" htmlFor={`cost-${item.id}`}>
              {item.label_fa}
              {item.required ? (
                <span className="text-[#0cb6aa]"> *</span>
              ) : null}
              <span className="mt-0.5 block text-xs text-[var(--study-muted)]" dir="ltr">
                {assumptions.unit ?? item.unit}
              </span>
              {item.note_fa ? (
                <span className="mt-0.5 block text-xs text-[#9a6700]">{item.note_fa}</span>
              ) : null}
            </label>
            <div className="grid grid-cols-[minmax(0,1fr)_5.2rem] gap-2">
              <input
                id={`cost-${item.id}`}
                className="nova-input !bg-white !text-[var(--study-ink)]"
                type="number"
                min="0"
                step="any"
                dir="ltr"
                value={item.amount ?? ""}
                placeholder={fa.feasibility.unknown}
                onChange={(e) => onChange(item.id, { amount: e.currentTarget.value === "" ? null : e.currentTarget.valueAsNumber })}
              />
              <select
                aria-label={`${fa.feasibility.costCurrency} ${item.label_fa}`}
                className="nova-input !bg-white !text-[var(--study-ink)]"
                value={item.currency}
                onChange={(e) => onChange(item.id, { currency: e.currentTarget.value })}
              >
                <option value="USD">USD</option>
                <option value="IRR">IRR</option>
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
