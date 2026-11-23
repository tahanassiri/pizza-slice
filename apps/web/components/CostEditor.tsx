"use client";

import { fa } from "@/lib/i18n/fa";
import type { CostItem } from "@/types";

export function CostEditor({
  items,
  onChange,
}: {
  items: CostItem[];
  onChange: (id: string, amount: number | null) => void;
}) {
  return (
    <div className="dossier-row p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <p className="text-[0.65rem] uppercase tracking-[0.14em] text-[#0cb6aa]">
            inputs
          </p>
          <h3 className="font-semibold text-[var(--study-ink)]">{fa.feasibility.editor}</h3>
        </div>
      </div>

      <div className="divide-y divide-[var(--study-line)]">
        {items.map((item) => (
          <div
            key={item.id}
            className="grid gap-2 py-3 sm:grid-cols-[1fr_148px] sm:items-center"
          >
            <label className="text-sm text-[var(--study-ink)]" htmlFor={`cost-${item.id}`}>
              {item.label_fa}
              {item.required ? (
                <span className="text-[#0cb6aa]"> *</span>
              ) : null}
              <span className="mt-0.5 block text-xs text-[var(--study-muted)]" dir="ltr">
                {item.currency}
                {item.unit ? ` / ${item.unit}` : ""}
              </span>
              {item.note_fa ? (
                <span className="mt-0.5 block text-xs text-[#9a6700]">{item.note_fa}</span>
              ) : null}
            </label>
            <input
              id={`cost-${item.id}`}
              className="nova-input !bg-white !text-[var(--study-ink)]"
              type="number"
              step="0.01"
              dir="ltr"
              value={item.amount ?? ""}
              placeholder={fa.feasibility.unknown}
              onChange={(e) => {
                const raw = e.target.value;
                onChange(item.id, raw === "" ? null : Number(raw));
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
