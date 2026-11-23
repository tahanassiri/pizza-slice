"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import { resolveSource } from "@/lib/api/client";
import { adminLogin } from "@/lib/api/live-adapter";

export default function AdminLoginPage() {
  const router = useRouter();
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isMock = resolveSource() === "mock";

  return (
    <div className="mx-auto max-w-md space-y-4">
      {isMock ? (
        <div className="flex flex-wrap gap-2">
          <span className="cockpit-chip-mock cockpit-chip">{fa.mockPreviewBadge}</span>
          <span className="cockpit-chip-mock cockpit-chip">{fa.mockBadge}</span>
        </div>
      ) : null}
      <form
        className="nova-panel relative overflow-hidden space-y-4 p-6"
        onSubmit={(e) => {
          e.preventDefault();
          void (async () => {
            setBusy(true);
            setError(null);
            try {
              if (isMock) {
                // Phase A: cosmetic gate only — no real auth / no key storage
                if (typeof window !== "undefined") {
                  sessionStorage.setItem("nova_admin_demo", "1");
                }
              } else {
                await adminLogin(user.trim(), pass);
                if (typeof window !== "undefined") {
                  sessionStorage.setItem("nova_admin_demo", "1");
                }
              }
              router.push("/admin");
            } catch {
              setError(fa.admin.loginNote);
            } finally {
              setBusy(false);
            }
          })();
        }}
      >
        <div className="absolute inset-y-5 end-0 w-1 rounded-full bg-[var(--accent)]/70" aria-hidden />
        <p className="text-[0.65rem] uppercase tracking-[0.16em] text-[var(--accent)]">
          control access
        </p>
        <h1 className="text-xl font-semibold text-white">{fa.admin.loginTitle}</h1>
        <p className="text-sm text-[var(--ink-muted)]">
          {isMock ? fa.admin.loginNote : "ورود مدیر — کلیدها فقط سمت سرور ذخیره می‌شوند."}
        </p>
        <div>
          <label className="nova-label" htmlFor="username">
            {fa.admin.username}
          </label>
          <input
            id="username"
            className="nova-input"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            autoComplete="username"
          />
        </div>
        <div>
          <label className="nova-label" htmlFor="password">
            {fa.admin.password}
          </label>
          <input
            id="password"
            className="nova-input"
            type="password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        {error ? (
          <p className="text-sm text-[var(--danger)]" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" className="nova-btn-primary w-full" disabled={busy}>
          {fa.admin.login}
        </button>
      </form>
    </div>
  );
}
