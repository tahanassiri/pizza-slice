import type { Metadata } from "next";
import { Vazirmatn, Syne } from "next/font/google";
import { AppHeader } from "@/components/AppHeader";
import { fa } from "@/lib/i18n/fa";
import "./globals.css";

const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  variable: "--font-vazirmatn",
  display: "swap",
});

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
});

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
      <body className={`${vazirmatn.variable} ${syne.variable} font-sans antialiased`}>
        <AppHeader />
        <main className="nova-container py-6 sm:py-10">{children}</main>
        <footer className="no-print border-t border-line/60 py-6 text-center text-xs text-ink-muted">
          <p>
            {fa.footer.phase} · {fa.footer.privacy}
          </p>
        </footer>
      </body>
    </html>
  );
}
