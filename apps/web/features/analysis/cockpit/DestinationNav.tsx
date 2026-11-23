import { fa } from "@/lib/i18n/fa";
import type { AnalysisTab } from "@/types";

const ITEMS: AnalysisTab[] = [
  "timeline",
  "markets",
  "buyers",
  "feasibility",
  "report",
];

export function DestinationNav({
  active,
  onSelect,
  readiness,
}: {
  active: AnalysisTab;
  onSelect: (tab: AnalysisTab) => void;
  readiness: Partial<Record<AnalysisTab, "ready" | "waiting" | "blocked">>;
}) {
  return (
    <nav
      className="no-print fixed inset-x-0 bottom-0 z-50 border-t border-[var(--cockpit-line)] bg-[#0b1426]/95 backdrop-blur-md lg:static lg:z-auto lg:mt-4 lg:rounded-2xl lg:border lg:bg-[var(--cockpit-panel)]"
      aria-label={fa.cockpit.destinations}
    >
      <div className="mx-auto grid w-full max-w-6xl grid-cols-5 gap-0.5 px-1 py-1.5 sm:gap-2 sm:px-2 sm:py-2">
        {ITEMS.map((id) => {
          const state = readiness[id] ?? "waiting";
          const isActive = active === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              className={`min-w-0 rounded-xl px-0.5 py-2 text-center transition sm:px-2 ${
                isActive
                  ? "bg-[var(--cockpit-teal)] text-[#041016] shadow-[0_0_24px_rgba(12,182,170,0.35)]"
                  : "text-[var(--cockpit-muted)] hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              <span className="block truncate text-[0.58rem] font-semibold leading-tight sm:text-sm">
                {fa.analysis.tabs[id]}
              </span>
              <span
                className={`mt-0.5 block truncate text-[0.5rem] sm:text-[0.6rem] ${
                  isActive ? "text-[#041016]/80" : "text-[var(--cockpit-faint)]"
                }`}
              >
                {state === "ready"
                  ? "آماده"
                  : state === "blocked"
                    ? "مسدود"
                    : "در انتظار"}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
