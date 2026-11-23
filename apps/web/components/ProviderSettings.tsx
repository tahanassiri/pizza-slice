"use client";

import { useMemo, useState } from "react";
import { fa } from "@/lib/i18n/fa";
import { resolveSource } from "@/lib/api/client";
import { getAdminToken } from "@/lib/api/live-adapter";
import type { AdminSettingsView, LlmModelOption } from "@/types";

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
  const [selectedModel, setSelectedModel] = useState(settings.selected_model);
  const [models, setModels] = useState<LlmModelOption[]>(settings.llm_models ?? []);
  const firstProvider = settings.providers[0]?.id ?? "tavily";

  const groups = useMemo(() => {
    if (settings.llm_groups?.length) return settings.llm_groups;
    const map = new Map<string, { id: string; label_fa: string; models: LlmModelOption[] }>();
    for (const m of models) {
      const g = map.get(m.group) ?? {
        id: m.group,
        label_fa: m.group_label_fa,
        models: [],
      };
      g.models.push(m);
      map.set(m.group, g);
    }
    return Array.from(map.values());
  }, [settings.llm_groups, models]);

  const activeMeta = models.find((m) => m.id === selectedModel);

  async function authHeaders(): Promise<HeadersInit> {
    const token = getAdminToken();
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }

  async function selectModel(modelId: string) {
    setSelectedModel(modelId);
    setKeyDraft("");
    if (isMock) {
      setMessage(`مدل نمایشی انتخاب شد: ${modelId}`);
      return;
    }
    setBusy(true);
    try {
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/model`, {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify({ model: modelId }),
      });
      if (!res.ok) throw new Error("fail");
      setMessage(`مدل فعال: ${modelId}`);
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function saveModelKey() {
    setBusy(true);
    try {
      if (isMock) {
        setKeyDraft("");
        setModels((prev) =>
          prev.map((m) =>
            m.id === selectedModel ? { ...m, has_key_configured: true } : m
          )
        );
        setMessage(`کلید نمایشی برای ${selectedModel} ذخیره شد (بدون تماس واقعی).`);
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/model/key`, {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify({
          model: selectedModel,
          api_key: keyDraft.trim() || null,
        }),
      });
      if (!res.ok) throw new Error("fail");
      const body = (await res.json()) as { has_key_configured?: boolean };
      setKeyDraft("");
      setModels((prev) =>
        prev.map((m) =>
          m.id === selectedModel
            ? { ...m, has_key_configured: Boolean(body.has_key_configured) }
            : m
        )
      );
      setMessage(
        body.has_key_configured
          ? `کلید نسخه «${selectedModel}» ذخیره شد.`
          : `کلید نسخه «${selectedModel}» پاک شد.`
      );
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    try {
      if (isMock) {
        setMessage("آزمون اتصال نمایشی — بدون درخواست واقعی.");
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/test-connection`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({ provider_id: `model:${selectedModel}` }),
      });
      const body = (await res.json()) as { message_fa?: string };
      setMessage(body.message_fa || "نتیجه آزمون دریافت شد.");
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function testProviderKey() {
    setBusy(true);
    try {
      if (isMock) {
        setMessage("آزمون ارائه‌دهنده نمایشی انجام شد.");
        return;
      }
      const token = getAdminToken();
      const base = liveApiBase();
      if (keyDraft.trim() && !selectedModel) {
        await fetch(`${base}/api/admin/providers/${firstProvider}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ api_key: keyDraft.trim() }),
        });
      }
      const res = await fetch(`${base}/api/admin/test-connection`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({ provider_id: firstProvider }),
      });
      const body = (await res.json()) as { message_fa?: string };
      setMessage(body.message_fa || "نتیجه آزمون دریافت شد.");
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-w-0 space-y-4">
      {isMock ? (
        <div className="flex flex-wrap gap-2">
          <span className="cockpit-chip-mock cockpit-chip">{fa.mockPreviewBadge}</span>
          <span className="cockpit-chip-mock cockpit-chip">{fa.mockBadge}</span>
        </div>
      ) : null}
      <p className="text-sm text-[var(--mock)]">
        {isMock ? fa.admin.noRealKeys : "کلید هر نسخه مدل جداگانه رمزنگاری می‌شود؛ فقط سمت سرور."}
      </p>

      <section className="nova-panel min-w-0 space-y-3 overflow-hidden p-4 sm:p-5">
        <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-white">{fa.admin.model}</h2>
          <span className="max-w-full truncate text-[0.65rem] uppercase tracking-[0.14em] text-[var(--ink-muted)]" dir="ltr">
            {selectedModel}
          </span>
        </div>

        <div className="max-h-[22rem] space-y-4 overflow-y-auto overflow-x-hidden pe-1">
          {groups.map((group) => (
            <div key={group.id} className="min-w-0 space-y-2">
              <p className="text-xs font-semibold text-[var(--accent)]">{group.label_fa}</p>
              <div className="grid min-w-0 gap-1.5">
                {group.models.map((m) => {
                  const configured =
                    models.find((x) => x.id === m.id)?.has_key_configured ?? false;
                  const active = selectedModel === m.id;
                  return (
                    <button
                      key={`${group.id}-${m.id}`}
                      type="button"
                      disabled={busy}
                      onClick={() => void selectModel(m.id)}
                      className={`flex min-w-0 items-center justify-between gap-2 rounded-xl border px-3 py-2 text-start transition ${
                        active
                          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                          : "border-[var(--line)] bg-black/20 hover:border-[var(--accent)]/50"
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-white">
                          {m.label}
                        </span>
                        <span className="block truncate font-mono text-[0.65rem] text-[var(--ink-muted)]" dir="ltr">
                          {m.id}
                        </span>
                      </span>
                      <span className="shrink-0 text-[0.65rem] text-[var(--ink-soft)]">
                        {configured ? "key✓" : "—"}
                        {m.is_flash ? " · flash" : ""}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-[var(--line)] pt-3">
          <p className="mb-2 text-xs text-[var(--ink-muted)]">
            {fa.admin.modelKeyFor}:{" "}
            <span className="font-mono text-[var(--accent)]" dir="ltr">
              {selectedModel}
            </span>
            {activeMeta?.has_key_configured ? (
              <span className="ms-2 text-[var(--ok)]">({fa.admin.keySaved})</span>
            ) : null}
          </p>
          <label className="nova-label" htmlFor="model-api-key">
            {fa.admin.apiKey}
          </label>
          <input
            id="model-api-key"
            className="nova-input"
            type="password"
            autoComplete="off"
            placeholder={fa.admin.apiKeyPlaceholder}
            value={keyDraft}
            onChange={(e) => setKeyDraft(e.target.value)}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="nova-btn-primary !px-4 !py-2 text-xs"
              disabled={busy}
              onClick={() => void saveModelKey()}
            >
              {fa.admin.saveModelKey}
            </button>
            <button
              type="button"
              className="nova-btn-ghost !px-4 !py-2 text-xs"
              disabled={busy}
              onClick={() => void testConnection()}
            >
              {fa.admin.testConnection}
            </button>
          </div>
        </div>
        <p className="break-words text-sm text-[var(--ink-muted)]">{message}</p>
      </section>

      <section className="nova-panel min-w-0 space-y-3 overflow-hidden p-4 sm:p-5">
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
              className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-black/25 px-3 py-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className={`h-2 w-2 shrink-0 rounded-full ${
                    p.enabled ? "bg-[var(--accent)]" : "bg-[var(--ink-muted)]"
                  }`}
                />
                <div className="min-w-0">
                  <p className="font-medium text-white">{p.name}</p>
                  <p className="break-words text-xs text-[var(--ink-muted)]">{p.usage_note_fa}</p>
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
        <button
          type="button"
          className="nova-btn-ghost"
          disabled={busy}
          onClick={() => void testProviderKey()}
        >
          {fa.admin.testProvider}
        </button>
      </section>

      <section className="nova-panel min-w-0 overflow-hidden p-4 sm:p-5">
        <h2 className="mb-3 font-semibold text-white">{fa.admin.errors}</h2>
        <ul className="space-y-2 text-sm text-[var(--ink-muted)]">
          {settings.error_history.map((e) => (
            <li
              key={e.at + e.message_fa}
              className="flex min-w-0 flex-wrap gap-2 border-r border-[var(--line)] pr-2"
            >
              <time dir="ltr" className="text-xs opacity-70">
                {new Date(e.at).toLocaleString("fa-IR")}
              </time>
              <span className="break-words">{e.message_fa}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
