import Link from "next/link";
import { fa } from "@/lib/i18n/fa";

export function AppHeader() {
  return (
    <header className="no-print border-b border-[var(--line)] bg-[#0b1426]/80 backdrop-blur-md">
      <div className="nova-container flex h-14 items-center justify-between">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="font-display text-xl font-extrabold tracking-tight text-white">
            {fa.brand}
          </span>
          <span className="nova-caption hidden text-sm text-[var(--ink-muted)] sm:inline">
            {fa.brandSubtitle}
          </span>
        </Link>
        <nav className="flex items-center gap-2 text-sm">
          <Link href="/" className="nova-btn-ghost !px-3 !py-1.5">
            {fa.nav.home}
          </Link>
          <Link href="/admin/login" className="nova-btn-ghost !px-3 !py-1.5">
            {fa.nav.admin}
          </Link>
        </nav>
      </div>
    </header>
  );
}
