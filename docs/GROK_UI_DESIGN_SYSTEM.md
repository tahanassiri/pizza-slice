# NOVA Grok UI Design System — Analysis Cockpit

**Scope:** `/analysis/[id]` only (employer visual checkpoint)  
**Graphify:** MCP not connected — design decisions from code audit, not Graphify.

## Audit (why the current UI feels generic)

| Issue | Where |
|-------|--------|
| Flat vertical stack of identical `nova-panel` cards — no focal composition | `features/analysis/AnalysisShell.tsx` |
| Generic pill tab strip; research stages are not a cockpit | same + tab buttons |
| Timeline is a list of same-weight cards, no phase rail or live focus | `components/AnalysisTimeline.tsx` |
| Light paper/teal theme shared with landing — no “ops room” identity | `app/globals.css` tokens |
| Mock strip is a yellow banner, not woven into the command surface | `components/MockBanner.tsx` |
| No evidence density, no progressive reveal, no purposeful viz | missing entirely |
| Status chips are soft pastel pills without operational hierarchy | `components/RunStatus.tsx` |

Root cause: **layout + hierarchy**, not missing a color. It reads as a form wizard, not an intelligence desk.

## Two layout ideas

### A — Command Bridge (selected)
Dark full-bleed cockpit. Top identity bar. Hero focus for the active research beat. **Right phase rail** (RTL: rail on the visual start side). Center activity/evidence feed. Left/side progressive results + light market-signal viz. Destination nav for markets/buyers/feasibility/report.

**Why:** Matches “executive trust + wow”, dark dashboard vs light report surfaces, distinctive in ≤5s, maps cleanly to future SSE events.

### B — Signal Desk (rejected for this checkpoint)
Light executive canvas, top horizontal stepper, large center card, bottom split feed/results.

**Why not now:** Closer to the current light stack; weaker first-impression differentiation after employer rejection of “simple/soulless.”

## Tokens (cockpit-scoped under `.cockpit`)

| Token | Value | Role |
|-------|-------|------|
| `--cockpit-bg` | `#0B1426` | Midnight navy field |
| `--cockpit-ink` | `#13233D` | Raised panels |
| `--cockpit-line` | `rgba(230,240,255,0.10)` | Hairlines |
| `--cockpit-text` | `#F6F8FB` | Primary text |
| `--cockpit-muted` | `rgba(246,248,251,0.62)` | Secondary |
| `--cockpit-teal` | `#0CB6AA` | Live / insight |
| `--cockpit-gold` | `#E6B765` | Opportunity accent |
| `--cockpit-danger` | `#F07167` | Failures |
| `--cockpit-warn` | `#E6B765` | Partial / quota |

Study/report panes that open from destination nav may use light surfaces inside the dark shell for readability — without restyling those feature components broadly.

## Typography
- Body/UI: Vazirmatn (existing)
- Display/brand Latin: Syne (existing)
- Numbers, HS, URLs: `dir="ltr"` inline
- Hierarchy: Hero stage title ≫ product name ≫ feed items ≫ meta

## Spacing & grid
- Desktop `1440×900`: 12-col mental grid; rail ~240px; hero + feed dominate
- Mobile `390×844`: stacked — hero → compact phase chips → feed → results → sticky destination nav
- Breathing room: 16 / 24 / 40; avoid card farms

## Motion
- Phase active: soft pulse on teal node (`prefers-reduced-motion: reduce` → static)
- Feed items: short fade/slide-in on mount
- No fake % progress; no endless spinner as the main story

## Components (cockpit)
`CockpitHeader`, `ResearchHero`, `PhaseRail`, `ActivityFeed`, `ProgressiveResults`, `MarketSignalViz`, `DestinationNav`, `ConnectionBanner` — composed by `AnalysisShell`.

## States to render
`queued` · `running` · `partial` · `completed` · `failed` · `rate_limited` · `provider_unavailable` · `connection_lost` · `no_results`

Mock labels **«پیش‌نمایش آزمایشی / داده آزمایشی»** remain permanent.
