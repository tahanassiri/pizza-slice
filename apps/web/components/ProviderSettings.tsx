"use client";

import { useMemo, useState } from "react";
import { fa } from "@/lib/i18n/fa";
import { resolveSource } from "@/lib/api/client";
import { getAdminToken } from "@/lib/api/live-adapter";
import type { AdminSettingsView, LlmModelOption, RouterProvider } from "@/types";

const DOCUMENTED_ROUTERS: RouterProvider[] = [
  {
    id: "openrouter",
    label_fa: "اوپن‌روتر",
    base_url: "https://openrouter.ai/api/v1",
    has_key_configured: false,
    capability: "unchecked",
    active: false,
  },
  {
    id: "omnirouter",
    label_fa: "اومنی‌روتر",
    base_url: "https://omnirouter-api.cc/v1",
    has_key_configured: false,
    capability: "unchecked",
    active: false,
  },
];

function methodLabel(value: string): string {
  const labels: Record<string, string> = {
    json_schema: "طرح JSON",
    json_object: "شیء JSON",
    function: "فراخوانی تابع",
    prompt: "سازگاری با پرامپت",
  };
  return labels[value] ?? value;
}

function failureLabel(value: string): string {
  const labels: Record<string, string> = {
    malformed: "JSON نامعتبر",
    empty: "پاسخ خالی",
    truncated: "پاسخ ناقص",
    unsupported: "پشتیبانی نشد",
    temporary: "خطای موقت",
    auth: "احراز هویت",
    provider_error: "خطای سرویس",
    schema: "طرح نخواند",
    ok: "سالم",
  };
  return labels[value] ?? value;
}

function capabilityLabel(value: string): string {
  const labels: Record<string, string> = {
    capable: "مجاز برای پژوهش",
    failed: "ناموفق",
    unchecked: "بررسی نشده",
    partial: "ناقص — رد دائمی نیست",
    unsupported: "خروجی ساختاریافته پشتیبانی نشد",
    temporary: "خطای موقت — مدل رد نشد",
  };
  return labels[value] ?? value;
}

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
  const [routerId, setRouterId] = useState(settings.routers?.find((item) => item.active)?.id ?? "openrouter");
  const [routerModel, setRouterModel] = useState("");
  const [routerKey, setRouterKey] = useState("");
  const [routerModels, setRouterModels] = useState<string[]>([]);
  const [routerMessage, setRouterMessage] = useState("");
  const routers = settings.routers?.length ? settings.routers : DOCUMENTED_ROUTERS;
  const activeRouter = routers.find((item) => item.id === routerId) ?? routers[0];
  const [keyDraft, setKeyDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [safety, setSafety] = useState(
    settings.safety ?? {
      max_consecutive_invalid: 3,
      max_repeated_actions: 3,
      max_runtime_seconds: 1800,
      max_run_tokens: 200000,
    }
  );
  const [selectedModel, setSelectedModel] = useState(settings.selected_model);
  const [models, setModels] = useState<LlmModelOption[]>(settings.llm_models ?? []);
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

  async function saveSafety() {
    setBusy(true);
    try {
      if (isMock) {
        setMessage("سقف عملیاتی نمایشی ذخیره شد.");
        return;
      }
      const base = liveApiBase();
      const res = await fetch(`${base}/api/admin/safety`, {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify(safety),
      });
      if (!res.ok) throw new Error("fail");
      setMessage("سقف عملیاتی ذخیره شد. مدل انتخاب‌شده عوض نشد.");
    } catch {
      setMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
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
      const body = (await res.json()) as {
        message_fa?: string;
        connection_status?: string;
        billing_status?: string;
      };
      setModelCheckMessage(
        [
          body.connection_status,
          body.billing_status === "Billing problem" ? body.billing_status : "",
          body.message_fa,
        ]
          .filter(Boolean)
          .join(" — ") ||
          "نتیجه بررسی کلید مشخص نشد."
      );
    } catch {
      setModelCheckMessage(fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function saveRouterKey() {
    setRouterMessage("");
    if (isMock) {
      setRouterMessage("در حالت نمایشی کلید روتر ذخیره نمی‌شود و تماسی انجام نمی‌شود.");
      setRouterKey("");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${liveApiBase()}/api/admin/routers/${routerId}/key`, {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify({ api_key: routerKey.trim() || null }),
      });
      const body = (await res.json()) as { message_fa?: string; has_key_configured?: boolean };
      if (!res.ok) throw new Error(body.message_fa || "fail");
      setRouterKey("");
      setRouterMessage(
        body.has_key_configured
          ? "کلید روتر ذخیره شد. عوض کردن مدل کلید جدید نمی‌خواهد."
          : "کلید روتر پاک شد."
      );
    } catch (err) {
      setRouterMessage(err instanceof Error && err.message !== "fail" ? err.message : fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function activateRouterModel(modelId: string) {
    const model = modelId.trim();
    if (!model) return;
    setRouterModel(model);
    if (isMock) {
      setRouterMessage("در حالت نمایشی مدل روتر فعال نمی‌شود.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${liveApiBase()}/api/admin/routers/${routerId}/model`, {
        method: "PUT",
        headers: await authHeaders(),
        body: JSON.stringify({ model }),
      });
      const body = (await res.json()) as { message_fa?: string; selected_model?: string };
      if (!res.ok) throw new Error(body.message_fa || "fail");
      setRouterMessage(`مدل فعال روتر: ${body.selected_model ?? model}. کلید جداگانه خواسته نشد.`);
    } catch (err) {
      setRouterMessage(err instanceof Error && err.message !== "fail" ? err.message : fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function loadRouterModels() {
    if (isMock) {
      setRouterMessage("در حالت نمایشی فهرست زنده خوانده نمی‌شود.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${liveApiBase()}/api/admin/routers/${routerId}/models`, {
        headers: await authHeaders(),
      });
      const body = (await res.json()) as { ok?: boolean; models?: string[]; message_fa?: string };
      if (!res.ok) throw new Error(body.message_fa || "fail");
      setRouterModels(body.models ?? []);
      setRouterMessage(body.message_fa || "فهرست مدل خوانده شد.");
    } catch (err) {
      setRouterMessage(err instanceof Error && err.message !== "fail" ? err.message : fa.error.generic);
    } finally {
      setBusy(false);
    }
  }

  async function probeRouter(path: "test" | "capability") {
    const model = routerModel.trim();
    if (!model) {
      setRouterMessage("شناسه مدل را وارد کنید.");
      return;
    }
    if (isMock) {
      setRouterMessage("در حالت نمایشی آزمون زنده انجام نمی‌شود.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${liveApiBase()}/api/admin/routers/${routerId}/${path}`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({ model }),
      });
      const body = (await res.json()) as { message_fa?: string };
      if (!res.ok) throw new Error(body.message_fa || "fail");
      setRouterMessage(body.message_fa || "نتیجه آزمون مشخص نشد.");
    } catch (err) {
      setRouterMessage(err instanceof Error && err.message !== "fail" ? err.message : fa.error.generic);
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

      <section className="nova-panel min-w-0 space-y-2 overflow-hidden p-4 sm:p-5">
        <h2 className="font-semibold text-white">جست‌وجوی بدون کلید</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          کشف وب از منابع بدون هزینه انجام می‌شود. کلید Tavily، Exa، WITS یا Comtrade برای پژوهش لازم نیست و از اینجا ارسال نمی‌شود.
        </p>
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
              آزمون اتصال مدل
            </button>
          </div>
          <p role="status" className="break-words text-sm text-[var(--ink-muted)]">
            {modelCheckMessage}
          </p>
        </div>
      </section>

      <section className="nova-panel min-w-0 space-y-3 overflow-hidden p-4 sm:p-5">
        <h2 className="font-semibold text-white">روترهای سازگار با OpenAI</h2>
        <p className="text-sm text-[var(--ink-muted)]">
          کلید روی خود روتر می‌ماند. عوض کردن مدل کلید جدید نمی‌خواهد. پژوهش فقط بعد از آزمون تصمیم JSON فعال می‌شود و مدل دیگری جایگزین نمی‌شود.
        </p>
        <div className="flex flex-wrap gap-2">
          {routers.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={busy}
              onClick={() => {
                setRouterId(item.id);
                setRouterModels([]);
                setRouterMessage("");
              }}
              className={`rounded-xl border px-3 py-2 text-sm ${
                item.id === activeRouter.id
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] text-white"
                  : "border-[var(--line)] text-[var(--ink-soft)]"
              }`}
            >
              {item.label_fa}
              {item.active ? " · فعال" : ""}
            </button>
          ))}
        </div>
        <p className="break-all font-mono text-xs text-[var(--ink-muted)]" dir="ltr">
          {activeRouter.base_url}
        </p>
        <p className="text-xs text-[var(--ink-muted)]">
          ارائه‌دهنده: {activeRouter.label_fa}
          {activeRouter.selected_model ? ` · مدل: ${activeRouter.selected_model}` : " · مدلی انتخاب نشده"}
          {" · "}
          اتصال کلید: {activeRouter.has_key_configured ? "ذخیره شده" : "نیست"}
        </p>
        <p className="text-xs text-[var(--ink-muted)]">
          توانایی پژوهش: {capabilityLabel(activeRouter.capability)}
          {activeRouter.output_method ? ` · روش خروجی: ${methodLabel(activeRouter.output_method)}` : ""}
          {activeRouter.failure_category ? ` · دسته خطا: ${failureLabel(activeRouter.failure_category)}` : ""}
        </p>
        <p className="text-xs text-[var(--ink-muted)]">
          توکن آزمون: {activeRouter.tokens_used ?? 0}
          {" · "}
          هزینه برآوردی: {activeRouter.estimated_cost_usd ? `$${activeRouter.estimated_cost_usd}` : "در پاسخ روتر نیامد"}
        </p>
        <label className="nova-label" htmlFor="router-key">
          کلید روتر
        </label>
        <input
          id="router-key"
          className="nova-input"
          type="password"
          autoComplete="off"
          dir="ltr"
          value={routerKey}
          onChange={(event) => setRouterKey(event.target.value)}
        />
        <label className="nova-label" htmlFor="router-model">
          شناسه مدل
        </label>
        <input
          id="router-model"
          className="nova-input"
          dir="ltr"
          value={routerModel}
          onChange={(event) => setRouterModel(event.target.value)}
          placeholder="openai/gpt-4"
        />
        {routerModels.length ? (
          <label className="nova-label" htmlFor="router-model-list">
            فهرست زنده
          </label>
        ) : null}
        {routerModels.length ? (
          <select
            id="router-model-list"
            className="nova-input"
            dir="ltr"
            value={routerModel}
            onChange={(event) => setRouterModel(event.target.value)}
          >
            {routerModels.map((modelId) => (
              <option key={modelId} value={modelId}>
                {modelId}
              </option>
            ))}
          </select>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="nova-btn-primary !px-4 !py-2 text-xs" disabled={busy} onClick={() => void saveRouterKey()}>
            ذخیره کلید روتر
          </button>
          <button type="button" className="nova-btn-ghost !px-4 !py-2 text-xs" disabled={busy} onClick={() => void loadRouterModels()}>
            فهرست مدل‌ها
          </button>
          <button type="button" className="nova-btn-ghost !px-4 !py-2 text-xs" disabled={busy} onClick={() => void activateRouterModel(routerModel)}>
            فعال‌سازی همین مدل
          </button>
          <button type="button" className="nova-btn-ghost !px-4 !py-2 text-xs" disabled={busy} onClick={() => void probeRouter("test")}>
            آزمون اتصال
          </button>
          <button type="button" className="nova-btn-ghost !px-4 !py-2 text-xs" disabled={busy} onClick={() => void probeRouter("capability")}>
            آزمون تصمیم JSON
          </button>
        </div>
        <p role="status" className="break-words text-sm text-[var(--ink-muted)]">{routerMessage}</p>
      </section>

      <section className="nova-panel min-w-0 overflow-hidden p-4 sm:p-5">
        <h2 className="mb-2 font-semibold text-white">سقف عملیاتی پژوهش</h2>
        <p className="mb-3 text-sm text-[var(--ink-muted)]">
          این سقف‌ها عمق تحقیق را قطع نمی‌کنند. صفر یعنی آن مورد خاموش است. مدل انتخاب‌شده عوض نمی‌شود.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="nova-label">
            پاسخ نامعتبر پیاپی
            <input className="nova-input" type="number" min={0} value={safety.max_consecutive_invalid} onChange={(event) => setSafety({ ...safety, max_consecutive_invalid: Number(event.target.value) })} />
          </label>
          <label className="nova-label">
            تکرار همان اقدام
            <input className="nova-input" type="number" min={0} value={safety.max_repeated_actions} onChange={(event) => setSafety({ ...safety, max_repeated_actions: Number(event.target.value) })} />
          </label>
          <label className="nova-label">
            حداکثر زمان اجرا (ثانیه)
            <input className="nova-input" type="number" min={0} value={safety.max_runtime_seconds} onChange={(event) => setSafety({ ...safety, max_runtime_seconds: Number(event.target.value) })} />
          </label>
          <label className="nova-label">
            حداکثر توکن اجرا
            <input className="nova-input" type="number" min={0} value={safety.max_run_tokens} onChange={(event) => setSafety({ ...safety, max_run_tokens: Number(event.target.value) })} />
          </label>
        </div>
        <button type="button" className="nova-btn-ghost mt-3 !px-4 !py-2 text-xs" disabled={busy} onClick={() => void saveSafety()}>
          ذخیره سقف عملیاتی
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
