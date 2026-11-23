import Link from "next/link";
import { fa } from "@/lib/i18n/fa";

export function AppHeader() {
  return (
    <header className="no-print border-b border-[var(--line)] bg-[#0b1426]/80 backdrop-blur-md">
      <div className="nova-container flex h-14 min-w-0 items-center justify-between gap-2">
        <Link href="/" className="flex min-w-0 items-baseline gap-2">
          <span className="font-display shrink-0 text-lg font-extrabold tracking-tight text-white sm:text-xl">
            {fa.brand}
          </span>
          <span className="nova-caption hidden truncate text-sm text-[var(--ink-muted)] sm:inline">
            {fa.brandSubtitle}
          </span>
        </Link>
        <nav className="flex shrink-0 items-center gap-1 text-sm sm:gap-2">
          <Link href="/" className="nova-btn-ghost !px-2.5 !py-1.5 sm:!px-3">
            {fa.nav.home}
          </Link>
          <Link href="/admin/login" className="nova-btn-ghost !px-2.5 !py-1.5 sm:!px-3">
            {fa.nav.admin}
          </Link>
        </nav>
      </div>
    </header>
  );
}
