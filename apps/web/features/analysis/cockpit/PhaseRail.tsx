"use client";

import { useMemo, useState } from "react";
import { fa } from "@/lib/i18n/fa";
import type { AnalysisPhase, RunEvent, RunStatus } from "@/types";

const RESEARCH_PHASES: AnalysisPhase[] = [
  "intake",
  "product_classify",
  "search",
  "trade_stats",
  "market_compare",
  "conclude",
];

type PhaseState = "waiting" | "active" | "done" | "error" | "partial";

function derive(events: RunEvent[], phase: AnalysisPhase): PhaseState {
  const related = events.filter((e) => e.phase === phase);
  if (!related.length) return "waiting";
  const last = related[related.length - 1]!;
  if (
    last.status === "failed" ||
    last.status === "provider_unavailable" ||
    last.status === "rate_limited"
  ) {
    return "error";
  }
  if (last.status === "partial") return "partial";
  if (last.status === "running" || last.status === "queued") return "active";
  if (last.status === "completed") return "done";
  return "waiting";
}

const stateLabel: Record<PhaseState, string> = {
  waiting: fa.cockpit.waitingPhase,
  active: fa.cockpit.activePhase,
  done: fa.cockpit.donePhase,
  error: fa.cockpit.errorPhase,
  partial: fa.cockpit.partialPhase,
};

const nodeClass: Record<PhaseState, string> = {
  waiting: "border-[var(--cockpit-line)] bg-transparent text-[var(--cockpit-faint)]",
  active:
    "border-[var(--cockpit-teal)] bg-[var(--cockpit-teal)] text-[#041016] cockpit-node-live",
  done: "border-[var(--cockpit-teal)] bg-[var(--cockpit-teal-soft)] text-[var(--cockpit-teal)]",
  error: "border-[var(--cockpit-danger)] bg-[var(--cockpit-danger-soft)] text-[var(--cockpit-danger)]",
  partial: "border-[var(--cockpit-gold)] bg-[var(--cockpit-gold-soft)] text-[var(--cockpit-gold)]",
};

function nodeGlyph(state: PhaseState, idx: number) {
  if (state === "done") return "✓";
  if (state === "error") return "!";
  if (state === "partial") return "~";
  return String(idx + 1);
}

export function PhaseRail({
  events,
  runStatus,
}: {
  events: RunEvent[];
  runStatus: RunStatus;
}) {
  const [open, setOpen] = useState<AnalysisPhase | null>(null);
  const items = useMemo(
    () =>
      RESEARCH_PHASES.map((phase) => {
        const state = derive(events, phase);
        const detail = [...events].reverse().find((e) => e.phase === phase);
        return { phase, state, detail };
      }),
    [events]
  );

  return (
    <aside className="cockpit-panel p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white">{fa.cockpit.phaseRail}</h3>
        <span className="text-[0.65rem] text-[var(--cockpit-faint)]">
          {fa.status[runStatus]}
        </span>
      </div>

      <ol className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
        {items.map((item, idx) => (
          <li key={item.phase} className="min-w-[9.5rem] lg:min-w-0">
            <button
              type="button"
              className="w-full rounded-xl border border-transparent p-2 text-right transition hover:border-[var(--cockpit-line)] hover:bg-white/[0.03]"
              onClick={() => setOpen(open === item.phase ? null : item.phase)}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${nodeClass[item.state]}`}
                >
                  {nodeGlyph(item.state, idx)}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">
                    {fa.phase[item.phase]}
                  </p>
                  <p className="text-[0.65rem] text-[var(--cockpit-muted)]">
                    {stateLabel[item.state]}
                  </p>
                </div>
              </div>
            </button>
            {open === item.phase ? (
              <div className="mt-1 rounded-xl border border-[var(--cockpit-line)] bg-black/20 px-3 py-2 text-xs text-[var(--cockpit-muted)]">
                <p className="mb-1 font-medium text-white">
                  {item.detail ? fa.cockpit.openDetails : fa.cockpit.waitingPhase}
                </p>
                <p>{item.detail?.message_fa ?? "رویدادی برای این مرحله ثبت نشده."}</p>
                {item.detail ? (
                  <time className="mt-1 block text-[var(--cockpit-faint)]" dir="ltr">
                    {new Date(item.detail.timestamp).toLocaleString("fa-IR")}
                  </time>
                ) : null}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </aside>
  );
}
