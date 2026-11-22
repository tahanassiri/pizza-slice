"use client";

import { fa } from "@/lib/i18n/fa";
import type { RunEvent } from "@/types";
import { RunStatus } from "./RunStatus";
import { SourceBadge } from "./SourceBadge";
export function AnalysisTimeline({ events }: { events: RunEvent[] }) {
  if (!events.length) {
    return (
      <p className="text-sm text-ink-muted">{fa.empty.title}</p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="mock-banner inline-flex rounded-lg px-2.5 py-1 text-xs font-medium">
        {fa.mockPreviewBadge}
      </p>
      <ol className="space-y-3">
        {events.map((ev, idx) => (
          <li
            key={ev.event_id}
            className="nova-panel animate-fade-up p-4"
            style={{ animationDelay: `${idx * 40}ms` }}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-ink">{ev.message_fa}</p>
              <RunStatus status={ev.status} />
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-ink-muted">
              <span>{fa.phase[ev.phase] ?? ev.phase}</span>
              <time dateTime={ev.timestamp} dir="ltr">
                {new Date(ev.timestamp).toLocaleString("fa-IR")}
              </time>
              {ev.error_code ? (
                <span className="text-[var(--danger)]" dir="ltr">
                  {ev.error_code}
                </span>
              ) : null}
            </div>
            {ev.source_refs?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {ev.source_refs.map((s) => (
                  <SourceBadge key={`${ev.event_id}-${s.url}`} source={s} />
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
