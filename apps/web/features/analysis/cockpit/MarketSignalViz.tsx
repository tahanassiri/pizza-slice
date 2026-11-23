import { fa } from "@/lib/i18n/fa";
import type { Market } from "@/types";

/** Abstract discovery constellation — not invented trade statistics. */
export function MarketSignalViz({ markets }: { markets: Market[] }) {
  const nodes =
    markets.length > 0
      ? markets.slice(0, 3).map((m, i) => ({
          id: m.country_code,
          label: m.country_name_fa,
          x: [28, 72, 50][i] ?? 50,
          y: [38, 42, 72][i] ?? 50,
          glow: m.confidence === "high" ? 1 : m.confidence === "medium" ? 0.7 : 0.45,
        }))
      : [
          { id: "a", label: "…", x: 30, y: 40, glow: 0.25 },
          { id: "b", label: "…", x: 70, y: 45, glow: 0.2 },
          { id: "c", label: "…", x: 50, y: 70, glow: 0.15 },
        ];

  return (
    <section className="cockpit-panel min-w-0 overflow-hidden p-3 sm:p-4">
      <div className="mb-2 flex min-w-0 items-center justify-between gap-2">
        <h3 className="truncate text-sm font-semibold text-white">{fa.cockpit.signalMap}</h3>
      </div>
      <p className="mb-3 break-words text-[0.7rem] text-[var(--cockpit-faint)]">{fa.cockpit.signalHint}</p>

      <div className="relative aspect-[16/10] w-full min-w-0 max-w-full overflow-hidden rounded-xl border border-[var(--cockpit-line)] bg-[#0a1220]">
        <svg viewBox="0 0 100 100" className="h-full w-full" aria-hidden>
          <defs>
            <radialGradient id="signalGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0CB6AA" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#0CB6AA" stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx="50" cy="48" r="28" fill="url(#signalGlow)" />
          {/* origin hub */}
          <circle cx="50" cy="48" r="3.2" fill="#E6B765" />
          {nodes.map((n) => (
            <g key={n.id}>
              <line
                x1="50"
                y1="48"
                x2={n.x}
                y2={n.y}
                stroke="rgba(12,182,170,0.35)"
                strokeWidth="0.6"
                strokeDasharray="1.5 1.2"
              />
              <circle
                cx={n.x}
                cy={n.y}
                r={2.8 + n.glow}
                fill="rgba(12,182,170,0.2)"
                stroke="#0CB6AA"
                strokeWidth="0.7"
                opacity={0.4 + n.glow * 0.6}
              />
            </g>
          ))}
        </svg>
        <ul className="pointer-events-none absolute inset-x-2 bottom-2 flex flex-wrap gap-1">
          {markets.slice(0, 3).map((m) => (
            <li
              key={m.country_code}
              className="rounded-md bg-black/45 px-1.5 py-0.5 text-[0.65rem] text-[var(--cockpit-muted)] backdrop-blur"
            >
              {m.country_name_fa}
            </li>
          ))}
          {!markets.length ? (
            <li className="rounded-md bg-black/45 px-1.5 py-0.5 text-[0.65rem] text-[var(--cockpit-faint)]">
              در انتظار سیگنال
            </li>
          ) : null}
        </ul>
      </div>
    </section>
  );
}
