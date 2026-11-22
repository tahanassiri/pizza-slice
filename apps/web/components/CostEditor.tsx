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
    <div className="nova-panel space-y-3 p-4">
      <h3 className="font-semibold">{fa.feasibility.editor}</h3>
      {items.map((item) => (
        <div key={item.id} className="grid gap-2 sm:grid-cols-[1fr_140px] sm:items-center">
          <label className="text-sm text-ink-soft" htmlFor={`cost-${item.id}`}>
            {item.label_fa}
            {item.required ? " *" : ""}
            <span className="mt-0.5 block text-xs text-ink-muted" dir="ltr">
              {item.currency}
              {item.unit ? ` / ${item.unit}` : ""}
            </span>
            {item.note_fa ? (
              <span className="mt-0.5 block text-xs text-ink-muted">{item.note_fa}</span>
            ) : null}
          </label>
          <input
            id={`cost-${item.id}`}
            className="nova-input"
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
  );
}
