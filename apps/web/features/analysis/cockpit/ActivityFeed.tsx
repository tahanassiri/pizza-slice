"use client";

import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import type { RunEvent } from "@/types";
import { CockpitStatusPill } from "./CockpitStatusPill";
import { SourceBadge } from "@/components/SourceBadge";

export function ActivityFeed({ events }: { events: RunEvent[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!events.length) {
    return (
      <section className="cockpit-panel p-4">
        <h3 className="mb-2 text-sm font-semibold">{fa.cockpit.activityFeed}</h3>
        <p className="text-sm text-[var(--cockpit-muted)]">{fa.cockpit.noResultsHint}</p>
      </section>
    );
  }

  const ordered = [...events].reverse();

  return (
    <section className="cockpit-panel flex min-h-0 flex-col p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white">{fa.cockpit.activityFeed}</h3>
        <span className="cockpit-chip-mock cockpit-chip">{fa.mockPreviewBadge}</span>
      </div>
      <ol className="max-h-[28rem] space-y-2 overflow-y-auto pe-1">
        {ordered.map((ev, idx) => {
          const open = expanded === ev.event_id;
          return (
            <li
              key={ev.event_id}
              className="animate-fade-up rounded-xl border border-[var(--cockpit-line)] bg-black/15 p-3"
              style={{ animationDelay: `${Math.min(idx, 8) * 35}ms` }}
            >
              <button
                type="button"
                className="flex w-full items-start justify-between gap-3 text-right"
                onClick={() => setExpanded(open ? null : ev.event_id)}
              >
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-medium text-white">{ev.message_fa}</p>
                  <p className="text-[0.7rem] text-[var(--cockpit-faint)]">
                    {fa.phase[ev.phase] ?? ev.phase}
                    {" · "}
                    <time dir="ltr">{new Date(ev.timestamp).toLocaleString("fa-IR")}</time>
                  </p>
                </div>
                <CockpitStatusPill status={ev.status} />
              </button>
              {open ? (
                <div className="mt-3 space-y-2 border-t border-[var(--cockpit-line)] pt-3">
                  {ev.error_code ? (
                    <p className="text-xs text-[var(--cockpit-danger)]" dir="ltr">
                      {ev.error_code}
                    </p>
                  ) : null}
                  {ev.source_refs?.length ? (
                    <div className="flex flex-wrap gap-2">
                      {ev.source_refs.map((s) => (
                        <SourceBadge key={`${ev.event_id}-${s.url}`} source={s} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--cockpit-faint)]">منبعی در این رویداد نیست.</p>
                  )}
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
