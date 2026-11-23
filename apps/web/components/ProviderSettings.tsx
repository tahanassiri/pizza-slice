"use client";

import { useMemo, useState } from "react";
import { fa } from "@/lib/i18n/fa";
import { resolveSource } from "@/lib/api/client";
import { getAdminToken } from "@/lib/api/live-adapter";
import type { AdminSettingsView, LlmModelOption, ProviderConfig } from "@/types";

/** Research providers that get dedicated API-key fields in admin. */
const RESEARCH_PROVIDER_IDS = ["tavily", "exa", "comtrade"] as const;

function liveApiBase(): string {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL !== undefined) {
    return String(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

export function ProviderSettings({ settings }: { settings: AdminSettingsView }) {
  const isMock = resolveSource() === "mock" || settings.is_mock_ui;
  const [message, setMessage] = useState(settings.connection_message_fa);
  const [modelCheckMessage, setModelCheckMessage] = useState("");
  const [keyDraft, setKeyDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedModel, setSelectedModel] = useState(settings.selected_model);
  const [models, setModels] = useState<LlmModelOption[]>(settings.llm_models ?? []);
  const [providers, setProviders] = useState<ProviderConfig[]>(settings.providers);
  const [providerKeyDrafts, setProviderKeyDrafts] = useState<Record<string, string>>({});

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

  const researchProviders = useMemo(
    () =>
      RESEARCH_PROVIDER_IDS.map(
        (id) =>
          providers.find((p) => p.id === id) ??
          ({
            id,
            name: id === "comtrade" ? "UN Comtrade" : id === "exa" ? "Exa" : "Tavily",
            enabled: false,
            has_key_configured: false,
            status: "untested",
            usage_note_fa: "",
          } satisfies ProviderConfig)
      ),
    [providers]
  );

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
    setModelCheckMessage("");
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
    setModelCheckMessage("");
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
        setModelCheckMessage("بررسی نمایشی کلید مدل");
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/test-connection`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({ provider_id: `model:${selectedModel}` }),
      });
      if (!res.ok) throw new Error("fail");
      const body = (await res.json()) as { message_fa?: string };
      setModelCheckMessage(body.message_fa || "نتیجه بررسی کلید مشخص نشد.");
    } catch {
      setModelCheckMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function toggleProvider(providerId: string, enabled: boolean) {
    setBusy(true);
    try {
      if (isMock) {
        setProviders((prev) =>
          prev.map((p) => (p.id === providerId ? { ...p, enabled } : p))
        );
        setMessage(
          enabled
            ? `ارائه‌دهنده نمایشی ${providerId} فعال شد.`
            : `ارائه‌دهنده نمایشی ${providerId} غیرفعال شد.`
        );
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/providers/${providerId}`, {
        method: "PATCH",
        headers: await authHeaders(),
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error("fail");
      const body = (await res.json()) as ProviderConfig;
      setProviders((prev) => {
        const others = prev.filter((p) => p.id !== providerId);
        return [...others, body].sort((a, b) => a.name.localeCompare(b.name));
      });
      setMessage(
        body.enabled
          ? `${body.name} فعال شد (کلید برای Comtrade اجباری نیست).`
          : `${body.name} غیرفعال شد.`
      );
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function saveProviderKey(providerId: string, clear = false) {
    setBusy(true);
    try {
      const draft = clear ? "" : (providerKeyDrafts[providerId] ?? "").trim();
      if (!clear && !draft) {
        setMessage("کلید خالی است — چیزی برای ذخیره نیست.");
        setBusy(false);
        return;
      }
      if (isMock) {
        setProviderKeyDrafts((prev) => ({ ...prev, [providerId]: "" }));
        setProviders((prev) =>
          prev.map((p) =>
            p.id === providerId
              ? {
                  ...p,
                  has_key_configured: !clear && Boolean(draft),
                  enabled: !clear && Boolean(draft),
                  status: "untested",
                }
              : p
          )
        );
        setMessage(
          clear
            ? `کلید نمایشی ${providerId} پاک شد.`
            : `کلید نمایشی ${providerId} ذخیره شد (بدون تماس واقعی).`
        );
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/providers/${providerId}`, {
        method: "PATCH",
        headers: await authHeaders(),
        body: JSON.stringify({
          api_key: draft,
          enabled: !clear && Boolean(draft),
        }),
      });
      if (!res.ok) throw new Error("fail");
      const body = (await res.json()) as ProviderConfig;
      setProviderKeyDrafts((prev) => ({ ...prev, [providerId]: "" }));
      setProviders((prev) => {
        const others = prev.filter((p) => p.id !== providerId);
        return [...others, body].sort((a, b) => a.name.localeCompare(b.name));
      });
      setMessage(
        body.has_key_configured
          ? `کلید ${body.name} ذخیره و فعال شد.`
          : `کلید ${body.name} پاک شد.`
      );
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function testProvider(providerId: string) {
    setBusy(true);
    try {
      if (isMock) {
        setMessage(`آزمون نمایشی ${providerId} انجام شد.`);
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/test-connection`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({ provider_id: providerId }),
      });
      if (!res.ok) throw new Error("fail");
      const body = (await res.json()) as { message_fa?: string };
      setMessage(body.message_fa || "نتیجه بررسی مشخص نشد.");
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
        {isMock ? fa.admin.noRealKeys : fa.admin.researchProvidersHint}
      </p>

      {settings.trade_sources?.length ? (
        <section className="nova-panel min-w-0 space-y-3 overflow-hidden p-4 sm:p-5">
          <div className="mb-1 flex items-center justify-between gap-2">
            <h2 className="font-semibold text-white">{fa.admin.tradeSources}</h2>
            <span className="text-[0.65rem] uppercase tracking-[0.14em] text-[var(--ink-muted)]">
              sources
            </span>
          </div>
          <p className="text-sm text-[var(--ink-muted)]">{fa.admin.tradeSourcesHint}</p>
          <ul className="space-y-2">
            {settings.trade_sources.map((s) => (
              <li
                key={s.id}
                className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--line)] bg-black/25 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="font-medium text-white">{s.name}</p>
                  <p className="text-xs text-[var(--ink-muted)]">{s.note_fa}</p>
                </div>
                <span className="text-xs font-semibold text-[var(--ink-soft)]" dir="ltr">
                  {s.status}
                  {s.optional ? " · optional" : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="nova-panel min-w-0 space-y-3 overflow-hidden p-4 sm:p-5">
        <div className="mb-1 flex items-center justify-between gap-2">
          <h2 className="font-semibold text-white">{fa.admin.researchProviders}</h2>
          <span className="text-[0.65rem] uppercase tracking-[0.14em] text-[var(--ink-muted)]">
            keys
          </span>
        </div>
        <ul className="space-y-4">
          {researchProviders.map((p) => (
            <li
              key={p.id}
              className="min-w-0 space-y-3 rounded-xl border border-[var(--line)] bg-black/25 px-3 py-3"
            >
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      p.enabled || (p.id !== "comtrade" && p.has_key_configured)
                        ? "bg-[var(--accent)]"
                        : "bg-[var(--ink-muted)]"
                    }`}
                  />
                  <div className="min-w-0">
                    <p className="font-medium text-white">{p.name}</p>
                    <p className="font-mono text-[0.65rem] text-[var(--ink-muted)]" dir="ltr">
                      {p.id}
                    </p>
                    {p.usage_note_fa ? (
                      <p className="mt-1 text-xs text-[var(--ink-muted)]">{p.usage_note_fa}</p>
                    ) : null}
                  </div>
                </div>
                <span className="text-xs font-semibold text-[var(--ink-soft)]">
                  {p.enabled ? fa.admin.enabled : fa.admin.disabled}
                  {" · "}
                  {fa.providerStatus[p.status] ?? p.status}
                  {p.has_key_configured ? (
                    <span className="text-[var(--ok)]"> · key✓ ({fa.admin.keySaved})</span>
                  ) : p.id === "comtrade" ? (
                    " · no key required"
                  ) : (
                    " · —"
                  )}
                </span>
              </div>
              <div>
                <label className="nova-label" htmlFor={`provider-key-${p.id}`}>
                  {fa.admin.apiKey} — {p.name}
                </label>
                <input
                  id={`provider-key-${p.id}`}
                  className="nova-input"
                  type="password"
                  autoComplete="off"
                  placeholder={fa.admin.providerKeyPlaceholder}
                  value={providerKeyDrafts[p.id] ?? ""}
                  onChange={(e) =>
                    setProviderKeyDrafts((prev) => ({
                      ...prev,
                      [p.id]: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {p.id === "comtrade" ? (
                  <button
                    type="button"
                    className="nova-btn-primary !px-4 !py-2 text-xs"
                    disabled={busy}
                    onClick={() => void toggleProvider(p.id, !p.enabled)}
                  >
                    {p.enabled ? fa.admin.disableProvider : fa.admin.enableProvider}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="nova-btn-primary !px-4 !py-2 text-xs"
                  disabled={busy}
                  onClick={() => void saveProviderKey(p.id)}
                >
                  {fa.admin.saveProviderKey}
                </button>
                <button
                  type="button"
                  className="nova-btn-ghost !px-4 !py-2 text-xs"
                  disabled={busy || !p.has_key_configured}
                  onClick={() => void saveProviderKey(p.id, true)}
                >
                  {fa.admin.clearProviderKey}
                </button>
                <button
                  type="button"
                  className="nova-btn-ghost !px-4 !py-2 text-xs"
                  disabled={busy}
                  onClick={() => void testProvider(p.id)}
                >
                  {p.id === "comtrade" ? "آزمون پیش‌نمایش عمومی" : "بررسی وجود کلید"}
                </button>
              </div>
            </li>
          ))}
        </ul>
        <p role="status" className="break-words text-sm text-[var(--ink-muted)]">{message}</p>
      </section>

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
              بررسی وجود کلید مدل
            </button>
          </div>
          <p role="status" className="break-words text-sm text-[var(--ink-muted)]">
            {modelCheckMessage}
          </p>
        </div>
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
