"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fa } from "@/lib/i18n/fa";
import { getApiClient } from "@/lib/api/client";
import type { AnalysisTab, Feasibility, RunSnapshot } from "@/types";
import { AnalysisTimeline } from "@/components/AnalysisTimeline";
import { BuyerCard } from "@/components/BuyerCard";
import { CostEditor } from "@/components/CostEditor";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { MarketComparison } from "@/components/MarketComparison";
import { MockBanner } from "@/components/MockBanner";
import { ReportView } from "@/components/ReportView";
import { RunStatus } from "@/components/RunStatus";
import { ScenarioComparison } from "@/components/ScenarioComparison";

const TABS: AnalysisTab[] = ["timeline", "markets", "buyers", "feasibility", "report"];

function isTab(v: string | null): v is AnalysisTab {
  return !!v && (TABS as string[]).includes(v);
}

export function AnalysisShell({ runId, initialTab }: { runId: string; initialTab?: AnalysisTab }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabFromQuery = searchParams.get("tab");
  const [tab, setTabState] = useState<AnalysisTab>(
    initialTab ?? (isTab(tabFromQuery) ? tabFromQuery : "timeline")
  );
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [feasibility, setFeasibility] = useState<Feasibility | null>(null);
  const [busySelect, setBusySelect] = useState(false);

  function setTab(next: AnalysisTab) {
    setTabState(next);
    const base = `/analysis/${runId}`;
    const href = next === "timeline" ? base : `${base}?tab=${next}`;
    router.replace(href, { scroll: false });
  }

  const load = useCallback(async (opts?: { showSpinner?: boolean }) => {
    if (opts?.showSpinner) {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await getApiClient().getRun(runId);
      setSnap(data);
      setFeasibility(data.feasibility ?? null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      setError(
        msg.startsWith("RUN_NOT_FOUND")
          ? "این تحلیل در حافظه جلسه نیست. از صفحه خانه یک اجرای آزمایشی جدید بسازید."
          : fa.error.generic
      );
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getApiClient().getRun(runId);
        if (cancelled) return;
        setSnap(data);
        setFeasibility(data.feasibility ?? null);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "";
        setError(
          msg.startsWith("RUN_NOT_FOUND")
            ? "این تحلیل در حافظه جلسه نیست. از صفحه خانه یک اجرای آزمایشی جدید بسازید."
            : fa.error.generic
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  async function selectCountry(code: string) {
    setBusySelect(true);
    try {
      const next = await getApiClient().selectCountry(runId, code);
      setSnap(next);
      setTab("buyers");
    } catch {
      setError(fa.error.generic);
    } finally {
      setBusySelect(false);
    }
  }

  async function recalc() {
    if (!feasibility) return;
    try {
      const next = await getApiClient().postFeasibility(
        runId,
        feasibility.cost_items.map((c) => ({ id: c.id, amount: c.amount }))
      );
      setFeasibility(next);
    } catch {
      setError(fa.error.generic);
    }
  }

  if (loading) return <LoadingState />;
  if (error && !snap)
    return (
      <ErrorState
        message={error}
        onRetry={() => void load({ showSpinner: true })}
      />
    );
  if (!snap) return <EmptyState />;

  const { run, events, markets, buyers, report } = snap;
  const blocked =
    run.status === "provider_unavailable" || run.status === "rate_limited";

  return (
    <div className="space-y-4">
      <MockBanner />

      <div className="nova-panel p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-ink-muted">{fa.analysis.title}</p>
            <h1 className="text-xl font-semibold text-ink sm:text-2xl">{run.product}</h1>
            <p className="mt-1 text-sm text-ink-muted">
              {run.origin_country}
              {run.guessed_hs_code ? (
                <>
                  {" · "}
                  {fa.analysis.hsGuess}:{" "}
                  <span dir="ltr">{run.guessed_hs_code}</span>
                </>
              ) : null}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <RunStatus status={run.status} />
            <span className="text-xs text-ink-muted">fixture: {run.fixture_id}</span>
          </div>
        </div>

        {run.error ? (
          <div className="mt-4">
            <ErrorState
              message={
                run.error.code === "QUOTA_EXHAUSTED"
                  ? fa.error.quota
                  : run.error.code === "PROVIDER_UNAVAILABLE"
                    ? fa.error.unavailable
                    : run.error.message_fa
              }
              onRetry={run.error.retryable ? load : undefined}
            />
          </div>
        ) : null}
      </div>

      <div className="no-print flex gap-1 overflow-x-auto rounded-xl border border-line bg-white/70 p-1">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${
              tab === t ? "bg-accent text-white" : "text-ink-soft hover:bg-fog"
            }`}
            onClick={() => setTab(t)}
          >
            {fa.analysis.tabs[t]}
          </button>
        ))}
      </div>

      {tab === "timeline" ? <AnalysisTimeline events={events} /> : null}

      {tab === "markets" ? (
        blocked ? (
          <EmptyState title={fa.markets.empty} hint={run.error?.message_fa} />
        ) : (
          <div className={busySelect ? "opacity-60" : ""}>
            <MarketComparison
              markets={markets}
              selectedCountry={run.selected_country}
              onSelect={selectCountry}
            />
          </div>
        )
      ) : null}

      {tab === "buyers" ? (
        !run.selected_country ? (
          <EmptyState
            title={fa.buyers.needCountry}
            action={
              <button type="button" className="nova-btn-ghost" onClick={() => setTab("markets")}>
                {fa.analysis.tabs.markets}
              </button>
            }
          />
        ) : buyers.length === 0 ? (
          <EmptyState title={fa.buyers.empty} hint={fa.buyers.emptyHint} />
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-ink-muted">{fa.buyers.potentialNote}</p>
            <div className="grid gap-3 md:grid-cols-2">
              {buyers.map((b) => (
                <BuyerCard key={b.company_name} buyer={b} />
              ))}
            </div>
          </div>
        )
      ) : null}

      {tab === "feasibility" ? (
        !feasibility ? (
          <EmptyState
            title={fa.feasibility.title}
            hint={
              blocked
                ? run.error?.message_fa
                : "برای این سناریو داده امکان‌سنجی تعریف نشده است."
            }
          />
        ) : (
          <div className="space-y-4">
            <p className="mock-banner rounded-xl px-3 py-2 text-sm">
              {fa.feasibility.sampleNote}
            </p>
            <CostEditor
              items={feasibility.cost_items}
              onChange={(id, amount) => {
                setFeasibility({
                  ...feasibility,
                  cost_items: feasibility.cost_items.map((c) =>
                    c.id === id ? { ...c, amount } : c
                  ),
                });
              }}
            />
            <button type="button" className="nova-btn-primary" onClick={() => void recalc()}>
              {fa.feasibility.recalc}
            </button>
            {feasibility.missing_inputs.length ? (
              <div className="nova-panel p-4">
                <p className="mb-2 font-medium">{fa.feasibility.missing}</p>
                <ul className="list-disc pr-5 text-sm text-ink-muted">
                  {feasibility.missing_inputs.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <ScenarioComparison scenarios={feasibility.scenario_results} />
            {feasibility.caveats.length ? (
              <ul className="list-disc pr-5 text-xs text-ink-muted">
                {feasibility.caveats.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            ) : null}
          </div>
        )
      ) : null}

      {tab === "report" ? (
        report ? (
          <ReportView report={report} />
        ) : (
          <EmptyState
            title={fa.report.title}
            hint={blocked ? run.error?.message_fa : "گزارش هنوز آماده نیست."}
          />
        )
      ) : null}

      <div className="no-print">
        <Link href="/" className="nova-btn-ghost !text-xs">
          {fa.analysis.backHome}
        </Link>
      </div>
    </div>
  );
}
