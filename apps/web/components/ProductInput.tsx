"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fa } from "@/lib/i18n/fa";
import { getApiClient } from "@/lib/api/client";
import { FIXTURE_IDS } from "@/fixtures";
import type { FixtureId } from "@/types";

export function ProductInput() {
  const router = useRouter();
  const [product, setProduct] = useState("پسته خام");
  const [origin, setOrigin] = useState<string>(fa.productInput.originDefault);
  const [hs, setHs] = useState("");
  const [fixture, setFixture] = useState<FixtureId>("happy");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = product.trim();
    if (!trimmed) {
      setError(fa.productInput.requiredProduct);
      return;
    }
    if (trimmed.length < 2) {
      setError(fa.productInput.productTooShort);
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const api = getApiClient();
      const { run_id } = await api.createRun({
        product: trimmed,
        origin_country: origin.trim() || fa.productInput.originDefault,
        hs_code: hs.trim() || undefined,
        fixture_id: fixture,
      });
      router.push(`/analysis/${run_id}`);
    } catch {
      setError(fa.error.generic);
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="nova-panel relative overflow-hidden space-y-4 p-5 sm:p-6"
    >
      <div className="absolute inset-y-4 end-0 w-1 rounded-full bg-[var(--mock)]/70" aria-hidden />
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--mock)]">
          {fa.cockpit.cockpitLabel}
        </p>
        <span className="cockpit-chip-mock cockpit-chip text-[0.65rem]">{fa.mockBadge}</span>
      </div>

      <div>
        <label className="nova-label" htmlFor="product">
          {fa.productInput.product}
        </label>
        <input
          id="product"
          className="nova-input"
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          placeholder={fa.productInput.productPlaceholder}
          autoComplete="off"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="nova-label" htmlFor="origin">
            {fa.productInput.origin}
          </label>
          <input
            id="origin"
            className="nova-input"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          />
        </div>
        <div>
          <label className="nova-label" htmlFor="hs">
            {fa.productInput.hsOptional}
          </label>
          <input
            id="hs"
            className="nova-input"
            value={hs}
            onChange={(e) => setHs(e.target.value)}
            placeholder={fa.productInput.hsPlaceholder}
            dir="ltr"
          />
        </div>
      </div>

      <div>
        <label className="nova-label" htmlFor="fixture">
          {fa.productInput.fixture}
        </label>
        <select
          id="fixture"
          className="nova-input"
          value={fixture}
          onChange={(e) => setFixture(e.target.value as FixtureId)}
        >
          {FIXTURE_IDS.map((id) => (
            <option key={id} value={id}>
              {fa.fixtures[id]}
            </option>
          ))}
        </select>
      </div>

      {error ? (
        <p className="text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}

      <button type="submit" className="nova-btn-primary w-full" disabled={busy}>
        {busy ? fa.loading.title : fa.productInput.submit}
      </button>
      <p className="text-[0.7rem] leading-5 text-[var(--ink-muted)]">{fa.mockNotice}</p>
    </form>
  );
}
