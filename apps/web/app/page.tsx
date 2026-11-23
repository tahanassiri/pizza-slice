import { ProductInput } from "@/components/ProductInput";
import { fa } from "@/lib/i18n/fa";
import { resolveSource } from "@/lib/api/client";

export default function HomePage() {
  const isMock = resolveSource() === "mock";
  return (
    <div className="relative -mx-4 max-w-[100vw] sm:-mx-6 -my-6 sm:-my-10 min-h-[calc(100vh-3.5rem)] overflow-x-hidden px-4 sm:px-6">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
      >
        <div className="absolute -left-20 top-10 h-72 w-72 rounded-full bg-[var(--accent)]/15 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-[var(--mock)]/10 blur-3xl" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-l from-transparent via-[var(--accent)]/40 to-transparent" />
      </div>

      <section className="relative z-10 mx-auto grid max-w-6xl gap-10 pb-16 pt-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center lg:gap-14 lg:pt-16">
        <div className="animate-fade-up space-y-6">
          {isMock ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="cockpit-chip-mock cockpit-chip">{fa.mockPreviewBadge}</span>
              <span className="cockpit-chip-mock cockpit-chip">{fa.mockBadge}</span>
            </div>
          ) : null}

          <p className="font-display text-4xl font-black tracking-tight text-white sm:text-6xl md:text-7xl">
            {fa.brand}
          </p>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-[var(--mock)]">
            {fa.brandSubtitle}
          </p>
          <h1 className="max-w-xl text-2xl font-bold leading-snug text-white sm:text-3xl">
            {fa.home.headline}
          </h1>
          <p className="nova-caption max-w-lg text-sm leading-7 text-[var(--ink-muted)] sm:text-base">
            {fa.home.support}
          </p>

          <div>
            <p className="nova-caption mb-2 text-xs text-[var(--ink-muted)]">{fa.home.pathLabel}</p>
            <ol className="flex flex-wrap gap-2">
              {fa.home.pathSteps.map((step, i) => (
                <li
                  key={step}
                  className="rounded-full border border-[var(--line)] bg-black/20 px-3 py-1 text-xs text-[var(--ink-soft)]"
                >
                  <span className="me-1.5 text-[var(--accent)]" dir="ltr">
                    {i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "90ms" }}>
          <ProductInput />
        </div>
      </section>
    </div>
  );
}
