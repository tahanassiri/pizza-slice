"use client";

import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import type { Report } from "@/types";
import { MockBanner } from "./MockBanner";
import { SourceBadge } from "./SourceBadge";
import { ConfidenceLabel } from "./ConfidenceLabel";

export function ReportView({ report }: { report: Report }) {
  const [clientName, setClientName] = useState(report.client_name ?? "");
  const [company, setCompany] = useState(report.company_name ?? "");

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-end justify-between gap-3">
        <MockBanner />
        <button type="button" className="nova-btn-primary" onClick={() => window.print()}>
          {fa.report.print}
        </button>
      </div>

      <article className="nova-panel space-y-5 p-5 sm:p-8 print:border-0 print:shadow-none">
        <header className="border-b border-line pb-4">
          <p className="font-display text-2xl font-bold tracking-tight">{fa.brand}</p>
          <h1 className="mt-1 text-xl font-semibold">{fa.report.title}</h1>
          <p className="mt-2 text-sm text-ink-muted">
            {report.product} · {report.origin_country}
          </p>
          <div className="no-print mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label className="nova-label" htmlFor="client">
                {fa.report.optionalClient}
              </label>
              <input
                id="client"
                className="nova-input"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
              />
            </div>
            <div>
              <label className="nova-label" htmlFor="company">
                {fa.report.optionalCompany}
              </label>
              <input
                id="company"
                className="nova-input"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
          </div>
          {(clientName || company) && (
            <p className="mt-3 text-sm text-ink-soft">
              {clientName}
              {clientName && company ? " — " : ""}
              {company}
            </p>
          )}
        </header>

        <section>
          <h2 className="mb-2 font-semibold">{fa.report.summary}</h2>
          <p className="text-sm leading-7 text-ink-soft">{report.summary_fa}</p>
        </section>

        <section>
          <h2 className="mb-2 font-semibold">{fa.markets.title}</h2>
          <ul className="space-y-2 text-sm">
            {report.markets.map((m) => (
              <li key={m.country_code} className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-baseline gap-2 font-medium">
                  <span dir="ltr">{m.rank}</span>
                  <span>{m.country_name_fa}</span>
                </span>
                <ConfidenceLabel level={m.confidence} />
                {report.selected_country === m.country_code ? (
                  <span className="text-xs text-accent">({fa.analysis.selectedCountry})</span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="mb-2 font-semibold">{fa.buyers.title}</h2>
          {report.buyers.length ? (
            <ul className="list-disc space-y-1 pr-5 text-sm text-ink-soft">
              {report.buyers.map((b) => (
                <li key={b.company_name}>
                  {b.company_name}
                  {b.business_type ? ` — ${b.business_type}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-muted">{fa.buyers.empty}</p>
          )}
        </section>

        {report.feasibility ? (
          <section>
            <h2 className="mb-2 font-semibold">{fa.feasibility.title}</h2>
            <p className="mb-2 text-xs text-[var(--mock)]">{fa.feasibility.sampleNote}</p>
            <ul className="space-y-1 text-sm text-ink-soft">
              {report.feasibility.scenario_results.map((s) => (
                <li key={s.id}>
                  {s.label_fa}:{" "}
                  {s.margin === null
                    ? fa.feasibility.unknown
                    : `${s.margin.toLocaleString("fa-IR")} ${report.feasibility?.currency}`}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section>
          <h2 className="mb-2 font-semibold">{fa.report.risks}</h2>
          <ul className="list-disc space-y-1 pr-5 text-sm text-ink-muted">
            {report.risks_fa.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="mb-2 font-semibold">{fa.report.assumptions}</h2>
          <ul className="list-disc space-y-1 pr-5 text-sm text-ink-muted">
            {report.assumptions_fa.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="mb-2 font-semibold">{fa.report.sources}</h2>
          <p className="mb-2 text-xs text-ink-muted">
            {fa.report.collectedAt}:{" "}
            <time dir="ltr">{new Date(report.collected_at).toLocaleString("fa-IR")}</time>
          </p>
          <div className="flex flex-wrap gap-2">
            {report.sources.map((s) => (
              <SourceBadge key={s.url} source={s} />
            ))}
          </div>
        </section>
      </article>
    </div>
  );
}
