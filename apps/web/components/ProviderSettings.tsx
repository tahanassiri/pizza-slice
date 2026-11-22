"use client";

import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import type { AdminSettingsView } from "@/types";
import { MockBanner } from "./MockBanner";

export function ProviderSettings({ settings }: { settings: AdminSettingsView }) {
  const [message, setMessage] = useState(settings.connection_message_fa);
  const [keyDraft, setKeyDraft] = useState("");

  return (
    <div className="space-y-4">
      <MockBanner />
      <p className="text-sm text-[var(--mock)]">{fa.admin.noRealKeys}</p>

      <section className="nova-panel space-y-4 p-5">
        <h2 className="font-semibold">{fa.admin.providers}</h2>
        <ul className="space-y-3">
          {settings.providers.map((p) => (
            <li
              key={p.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white/70 px-3 py-3"
            >
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-ink-muted">{p.usage_note_fa}</p>
                {p.daily_limit != null ? (
                  <p className="text-xs text-ink-muted">
                    {fa.admin.usage}: {p.used_today ?? 0}/{p.daily_limit}
                  </p>
                ) : null}
              </div>
              <span className="text-xs font-semibold text-ink-soft">
                {p.enabled ? fa.admin.enabled : fa.admin.disabled}
                {" · "}
                {fa.providerStatus[p.status] ?? p.status}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="nova-panel space-y-3 p-5">
        <h2 className="font-semibold">{fa.admin.model}</h2>
        <p className="text-sm text-ink-soft">{settings.selected_model}</p>
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
          onClick={() => {
            setKeyDraft("");
            setMessage(
              "آزمون اتصال نمایشی انجام شد — هیچ درخواست واقعی ارسال نشد و کلید ذخیره نشد."
            );
          }}
        >
          {fa.admin.testConnection}
        </button>
        <p className="text-sm text-ink-muted">{message}</p>
      </section>

      <section className="nova-panel p-5">
        <h2 className="mb-3 font-semibold">{fa.admin.errors}</h2>
        <ul className="space-y-2 text-sm text-ink-muted">
          {settings.error_history.map((e) => (
            <li key={e.at + e.message_fa} className="flex flex-wrap gap-2">
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
