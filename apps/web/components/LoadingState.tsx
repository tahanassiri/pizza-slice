"use client";

import { useEffect, useState } from "react";
import { resolveSource } from "@/lib/api/client";
import { fa } from "@/lib/i18n/fa";

const DEFAULT_STAGES = [
  fa.loading.stages.prepare,
  fa.loading.stages.fetch,
  fa.loading.stages.analyze,
  fa.loading.stages.almost,
];

export function LoadingState({
  label = fa.loading.pleaseWait,
  hint,
  stages = DEFAULT_STAGES,
  pulse = true,
}: {
  label?: string;
  hint?: string;
  stages?: readonly string[];
  /** When false, show a single static stage (still animated chrome). */
  pulse?: boolean;
}) {
  const [idx, setIdx] = useState(0);
  const [tick, setTick] = useState(0);
  const simulated = resolveSource() === "mock";
  const detail = hint ?? (simulated ? fa.loading.hint : undefined);

  useEffect(() => {
    if (!simulated || !pulse || stages.length <= 1) return;
    const id = window.setInterval(() => {
      setIdx((i) => (i + 1) % stages.length);
      setTick((t) => t + 1);
    }, 2200);
    return () => window.clearInterval(id);
  }, [pulse, simulated, stages]);

  const stage = stages[idx] ?? label;
  const progress = stages.length
    ? ((idx % stages.length) + 1) / stages.length
    : 0.35;

  return (
    <div
      className="nova-panel relative overflow-hidden flex flex-col gap-4 p-5 text-center sm:p-6 sm:text-right"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse at 30% 0%, rgba(12,182,170,0.18), transparent 55%), radial-gradient(ellipse at 80% 100%, rgba(230,183,101,0.12), transparent 50%)",
        }}
      />
      <div className="relative flex flex-col items-center gap-3 sm:flex-row sm:items-start">
        <span className="relative flex h-11 w-11 shrink-0 items-center justify-center" aria-hidden>
          <span className="absolute inset-0 rounded-full border border-[var(--accent)]/25 animate-ping opacity-40" />
          <span className="absolute inset-1 rounded-full border-2 border-[var(--accent)]/20 border-t-[var(--accent)] animate-spin" />
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] shadow-[0_0_12px_rgba(12,182,170,0.7)]" />
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-semibold text-white">{label}</p>
          {simulated ? <p
            key={`${idx}-${tick}`}
            className="animate-fade-up text-xs font-medium text-[var(--accent)]"
          >
            {stage}
          </p> : null}
          {detail ? (
            <p className="text-xs leading-5 text-[var(--ink-muted)]">{detail}</p>
          ) : null}
        </div>
      </div>

      {simulated ? <div className="relative space-y-2" aria-hidden>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-700 ease-out"
            style={{ width: `${Math.max(18, progress * 100)}%` }}
          />
        </div>
        <div className="flex justify-center gap-1.5 sm:justify-start">
          {stages.map((_, i) => (
            <span
              key={i}
              className={`h-1.5 w-1.5 rounded-full transition ${
                i === idx ? "bg-[var(--accent)] scale-125" : "bg-white/20"
              }`}
            />
          ))}
        </div>
      </div> : null}
    </div>
  );
}
