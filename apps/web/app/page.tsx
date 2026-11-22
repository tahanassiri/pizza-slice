import { ProductInput } from "@/components/ProductInput";
import { MockBanner } from "@/components/MockBanner";
import { fa } from "@/lib/i18n/fa";

export default function HomePage() {
  return (
    <div className="relative">
      <section className="relative min-h-[calc(100vh-8rem)] overflow-hidden pb-10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-8 h-[70vh] overflow-hidden rounded-3xl"
        >
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_30%,rgba(15,110,106,0.28),transparent_55%),linear-gradient(120deg,#0c1b2a_0%,#1a3348_45%,#0f6e6a_100%)]" />
          <div className="absolute inset-0 opacity-40 mix-blend-overlay [background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22160%22 height=%22160%22 viewBox=%220 0 160 160%22%3E%3Cpath fill=%22none%22 stroke=%22%23ffffff%22 stroke-opacity=%220.12%22 d=%22M0 80h160M80 0v160%22/%3E%3C/svg%3E')]" />
          <div className="absolute -left-10 bottom-10 h-40 w-40 rounded-full bg-white/10 blur-2xl animate-pulse-soft" />
          <div className="absolute right-10 top-16 h-28 w-28 rounded-full bg-[var(--accent)]/30 blur-xl" />
        </div>

        <div className="relative z-10 grid gap-10 px-1 pt-6 sm:px-2 lg:grid-cols-[1.1fr_0.9fr] lg:items-end lg:px-4 lg:pt-16">
          <div className="animate-fade-up space-y-5 px-1 text-white lg:pb-8">
            <p className="font-display text-5xl font-bold tracking-tight sm:text-6xl md:text-7xl">
              {fa.brand}
            </p>
            <p className="text-lg text-white/80 sm:text-xl">{fa.brandSubtitle}</p>
            <h1 className="max-w-xl text-2xl font-semibold leading-snug text-white/95 sm:text-3xl">
              {fa.home.headline}
            </h1>
            <p className="max-w-lg text-sm leading-7 text-white/75 sm:text-base">
              {fa.home.support}
            </p>
          </div>

          <div className="animate-fade-up space-y-3" style={{ animationDelay: "80ms" }}>
            <MockBanner className="bg-[var(--mock-soft)]/95" />
            <ProductInput />
          </div>
        </div>
      </section>
    </div>
  );
}
