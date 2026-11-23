"use client";

import { useState } from "react";
import { fa } from "@/lib/i18n/fa";
import type { Report } from "@/types";
import { SourceBadge } from "./SourceBadge";
import { ConfidenceLabel } from "./ConfidenceLabel";

export function ReportView({ report }: { report: Report }) {
  const [clientName, setClientName] = useState(report.client_name ?? "");
  const [company, setCompany] = useState(report.company_name ?? "");

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-end justify-between gap-3">
        {report.is_mock ? (
          <div className="flex flex-wrap gap-2">
            <span className="mock-banner rounded-lg px-2.5 py-1 text-xs font-medium">
              {fa.mockPreviewBadge}
            </span>
            <span className="mock-banner rounded-lg px-2.5 py-1 text-xs font-medium">
              {fa.mockBadge}
            </span>
          </div>
        ) : (
          <div />
        )}
        <button type="button" className="nova-btn-primary" onClick={() => window.print()}>
          {fa.report.print}
        </button>
      </div>

      <article className="study-surface space-y-6 p-5 sm:p-8 print:border-0 print:shadow-none">
        <header className="border-b border-[var(--study-line)] pb-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-display text-2xl font-bold tracking-tight text-[var(--study-ink)]">
                {fa.brand}
              </p>
              <p className="text-xs uppercase tracking-[0.16em] text-[#0cb6aa]">
                {fa.brandSubtitle}
              </p>
              <h1 className="mt-3 text-xl font-semibold text-[var(--study-ink)]">
                {fa.report.title}
              </h1>
              <p className="mt-1 text-sm text-[var(--study-muted)]">
                {report.product} · {report.origin_country}
              </p>
            </div>
            {report.is_mock ? (
              <span className="mock-banner rounded-lg px-2 py-1 text-xs font-medium">
                {fa.mockBadge}
              </span>
            ) : null}
          </div>

          <div className="no-print mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[var(--study-ink)]" htmlFor="client">
                {fa.report.optionalClient}
              </label>
              <input
                id="client"
                className="nova-input !bg-white !text-[var(--study-ink)]"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[var(--study-ink)]" htmlFor="company">
                {fa.report.optionalCompany}
              </label>
              <input
                id="company"
                className="nova-input !bg-white !text-[var(--study-ink)]"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
          </div>
          {(clientName || company) && (
            <p className="mt-3 text-sm text-[var(--study-ink)]">
              {clientName}
              {clientName && company ? " — " : ""}
              {company}
            </p>
          )}
        </header>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#0cb6aa]">
            {fa.report.summary}
          </h2>
          <p className="text-sm leading-7 text-[var(--study-muted)]">{report.summary_fa}</p>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#0cb6aa]">
            {fa.markets.title}
          </h2>
          <ul className="space-y-2 text-sm">
            {report.markets.map((m) => (
              <li
                key={m.country_code}
                className="flex flex-wrap items-center gap-2 border-r-2 border-[#0cb6aa]/40 pr-2"
              >
                <span className="inline-flex items-baseline gap-2 font-medium text-[var(--study-ink)]">
                  <span dir="ltr">{m.rank}</span>
                  <span>{m.country_name_fa}</span>
                </span>
                <ConfidenceLabel level={m.confidence} />
                {report.selected_country === m.country_code ? (
                  <span className="text-xs text-[#0cb6aa]">({fa.analysis.selectedCountry})</span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#0cb6aa]">
            {fa.buyers.title}
          </h2>
          {report.buyers.length ? (
            <ul className="space-y-1 text-sm text-[var(--study-muted)]">
              {report.buyers.map((b) => (
                <li key={b.company_name}>
                  {b.company_name}
                  {b.business_type ? ` — ${b.business_type}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--study-muted)]">{fa.buyers.empty}</p>
          )}
        </section>

        {report.feasibility ? (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#0cb6aa]">
              {fa.feasibility.title}
            </h2>
            {report.feasibility.is_mock_sample ? (
              <p className="mb-2 text-xs text-[#9a6700]">{fa.feasibility.sampleNote}</p>
            ) : null}
            {report.feasibility.incoterm ? (
              <p className="mb-2 text-sm text-[var(--study-muted)]">
                {fa.feasibility.incoterm} <span dir="ltr">{report.feasibility.incoterm}</span>
              </p>
            ) : null}
            <ul className="space-y-1 text-sm text-[var(--study-muted)]">
              {report.feasibility.scenario_results.map((s) => (
                <li key={s.id}>
                  {s.label_fa}:{" "}
                  {s.margin === null
                    ? fa.feasibility.unknown
                    : `${s.margin.toLocaleString("fa-IR")} ${report.feasibility?.currency}`}
                </li>
              ))}
            </ul>
            {report.feasibility.missing_inputs.length ? (
              <p className="mt-2 text-xs text-[#9a6700]">
                {fa.feasibility.missing} ({report.feasibility.missing_inputs.join("، ")})
              </p>
            ) : null}
          </section>
        ) : null}

        <section className="grid gap-4 sm:grid-cols-2">
          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#9a6700]">
              {fa.report.risks}
            </h2>
            <ul className="space-y-1 text-sm text-[var(--study-muted)]">
              {report.risks_fa.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#0cb6aa]">
              {fa.report.assumptions}
            </h2>
            <ul className="space-y-1 text-sm text-[var(--study-muted)]">
              {report.assumptions_fa.map((a) => (
                <li key={a}>• {a}</li>
              ))}
            </ul>
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.08em] text-[#0cb6aa]">
            {fa.report.sources}
          </h2>
          <p className="mb-2 text-xs text-[var(--study-muted)]">
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
