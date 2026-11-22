"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ProviderSettings } from "@/components/ProviderSettings";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { getApiClient } from "@/lib/api/client";
import { fa } from "@/lib/i18n/fa";
import type { AdminSettingsView } from "@/types";

export default function AdminPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<AdminSettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const ok =
        typeof window !== "undefined" &&
        sessionStorage.getItem("nova_admin_demo") === "1";

      if (!ok) {
        router.replace("/admin/login");
        return;
      }

      try {
        const data = await getApiClient().getAdminSettings();
        if (!cancelled) setSettings(data);
      } catch {
        if (!cancelled) setError(fa.error.generic);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (error) return <ErrorState message={error} />;
  if (!settings) return <LoadingState />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{fa.admin.settingsTitle}</h1>
        <Link href="/" className="nova-btn-ghost !text-xs">
          {fa.nav.home}
        </Link>
      </div>
      <ProviderSettings settings={settings} />
    </div>
  );
}
