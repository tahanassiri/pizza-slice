"use client";

import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import { resolveSource } from "@/lib/api/client";
import { getAdminToken } from "@/lib/api/live-adapter";
import type { AdminSettingsView } from "@/types";

function liveApiBase(): string {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL !== undefined) {
    return String(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

export function ProviderSettings({ settings }: { settings: AdminSettingsView }) {
  const isMock = resolveSource() === "mock" || settings.is_mock_ui;
  const [message, setMessage] = useState(settings.connection_message_fa);
  const [keyDraft, setKeyDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const firstProvider = settings.providers[0]?.id ?? "tavily";

  async function testConnection() {
    setBusy(true);
    try {
      if (isMock) {
        setKeyDraft("");
        setMessage(
          "آزمون اتصال نمایشی انجام شد — هیچ درخواست واقعی ارسال نشد و کلید ذخیره نشد."
        );
        return;
      }
      const token = getAdminToken();
      const base = liveApiBase();
      if (keyDraft.trim()) {
        await fetch(`${base}/api/admin/providers/${firstProvider}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ api_key: keyDraft.trim() }),
        });
        setKeyDraft("");
      }
      const res = await fetch(`${base}/api/admin/test-connection`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ provider_id: firstProvider }),
      });
      const body = (await res.json()) as { message_fa?: string; ok?: boolean };
      setMessage(body.message_fa || "نتیجه آزمون دریافت شد.");
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {isMock ? (
        <div className="flex flex-wrap gap-2">
          <span className="cockpit-chip-mock cockpit-chip">{fa.mockPreviewBadge}</span>
          <span className="cockpit-chip-mock cockpit-chip">{fa.mockBadge}</span>
        </div>
      ) : null}
      <p className="text-sm text-[var(--mock)]">
        {isMock ? fa.admin.noRealKeys : "کلیدها رمزنگاری‌شده فقط سمت سرور ذخیره می‌شوند."}
      </p>

      <section className="nova-panel space-y-3 p-5">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="font-semibold text-white">{fa.admin.providers}</h2>
          <span className="text-[0.65rem] uppercase tracking-[0.14em] text-[var(--ink-muted)]">
            rack
          </span>
        </div>
        <ul className="space-y-2">
          {settings.providers.map((p) => (
            <li
              key={p.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-black/25 px-3 py-3"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`h-2 w-2 rounded-full ${
                    p.enabled ? "bg-[var(--accent)]" : "bg-[var(--ink-muted)]"
                  }`}
                />
                <div>
                  <p className="font-medium text-white">{p.name}</p>
                  <p className="text-xs text-[var(--ink-muted)]">{p.usage_note_fa}</p>
                  {p.daily_limit != null ? (
                    <p className="text-xs text-[var(--ink-muted)]">
                      {fa.admin.usage}:{" "}
                      <span dir="ltr">
                        {p.used_today ?? 0}/{p.daily_limit}
                      </span>
                    </p>
                  ) : null}
                </div>
              </div>
              <span className="text-xs font-semibold text-[var(--ink-soft)]">
                {p.enabled ? fa.admin.enabled : fa.admin.disabled}
                {" · "}
                {fa.providerStatus[p.status] ?? p.status}
                {p.has_key_configured ? " · key✓" : ""}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="nova-panel space-y-3 p-5">
        <h2 className="font-semibold text-white">{fa.admin.model}</h2>
        <p className="font-mono text-sm text-[var(--accent)]" dir="ltr">
          {settings.selected_model}
        </p>
        <div>
          <label className="nova-label" htmlFor="api-key">
            {fa.admin.apiKey}
          </label>
          <input
            id="api-key"
            className="nova-input"
            type="password"
            autoComplete="off"
            placeholder={fa.admin.apiKeyPlaceholder}
            value={keyDraft}
            onChange={(e) => setKeyDraft(e.target.value)}
          />
        </div>
        <button
          type="button"
          className="nova-btn-ghost"
          disabled={busy}
          onClick={() => void testConnection()}
        >
          {fa.admin.testConnection}
        </button>
        <p className="text-sm text-[var(--ink-muted)]">{message}</p>
      </section>

      <section className="nova-panel p-5">
        <h2 className="mb-3 font-semibold text-white">{fa.admin.errors}</h2>
        <ul className="space-y-2 text-sm text-[var(--ink-muted)]">
          {settings.error_history.map((e) => (
            <li
              key={e.at + e.message_fa}
              className="flex flex-wrap gap-2 border-r border-[var(--line)] pr-2"
            >
              <time dir="ltr" className="text-xs opacity-70">
                {new Date(e.at).toLocaleString("fa-IR")}
              </time>
              <span>{e.message_fa}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
