"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { MockBanner } from "@/components/MockBanner";
import { fa } from "@/lib/i18n/fa";

export default function AdminLoginPage() {
  const router = useRouter();
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("");

  return (
    <div className="mx-auto max-w-md space-y-4">
      <MockBanner />
      <form
        className="nova-panel space-y-4 p-6"
        onSubmit={(e) => {
          e.preventDefault();
          // Phase A: cosmetic gate only — no real auth
          if (typeof window !== "undefined") {
            sessionStorage.setItem("nova_admin_demo", "1");
          }
          router.push("/admin");
        }}
      >
        <h1 className="text-xl font-semibold">{fa.admin.loginTitle}</h1>
        <p className="text-sm text-ink-muted">{fa.admin.loginNote}</p>
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
        <button type="submit" className="nova-btn-primary w-full">
          {fa.admin.login}
        </button>
      </form>
    </div>
  );
}
