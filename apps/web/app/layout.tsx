import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { fa } from "@/lib/i18n/fa";
import { dastkhat, dastkhatMono } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: `${fa.brand} — ${fa.brandSubtitle}`,
  description: fa.home.support,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl">
      <body
        className={`${dastkhat.variable} ${dastkhatMono.variable} font-sans font-normal antialiased`}
      >
        <AppHeader />
        <main className="nova-container py-6 sm:py-10">{children}</main>
        <footer className="no-print border-t border-[var(--line)] py-6 text-center text-xs font-light text-[var(--ink-muted)]">
          <p>
            {fa.footer.phase} · {fa.footer.privacy}
          </p>
        </footer>
      </body>
    </html>
  );
}
