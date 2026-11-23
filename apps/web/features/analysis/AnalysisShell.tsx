"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fa } from "@/lib/i18n/fa";
import { getApiClient, resolveSource } from "@/lib/api/client";
import { useRunEvents } from "@/lib/api/use-run-events";
import type { AnalysisTab, Feasibility, RunEvent, RunSnapshot } from "@/types";
import { BuyerCard } from "@/components/BuyerCard";
import { CostEditor } from "@/components/CostEditor";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { MarketComparison } from "@/components/MarketComparison";
import { ReportView } from "@/components/ReportView";
import { ScenarioComparison } from "@/components/ScenarioComparison";
import { ActivityFeed } from "@/features/analysis/cockpit/ActivityFeed";
import { CockpitHeader } from "@/features/analysis/cockpit/CockpitHeader";
import { ConnectionBanner } from "@/features/analysis/cockpit/ConnectionBanner";
import { DestinationNav } from "@/features/analysis/cockpit/DestinationNav";
import { MarketSignalViz } from "@/features/analysis/cockpit/MarketSignalViz";
import { PhaseRail } from "@/features/analysis/cockpit/PhaseRail";
import { ProgressiveResults } from "@/features/analysis/cockpit/ProgressiveResults";
import { ResearchHero } from "@/features/analysis/cockpit/ResearchHero";

const TABS: AnalysisTab[] = ["timeline", "markets", "buyers", "feasibility", "report"];

function isTab(v: string | null): v is AnalysisTab {
  return !!v && (TABS as string[]).includes(v);
}

export function AnalysisShell({
  runId,
  initialTab,
}: {
  runId: string;
  initialTab?: AnalysisTab;
}) {
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
  const [connectionLost, setConnectionLost] = useState(
    () => searchParams.get("conn") === "lost"
  );

  function setTab(next: AnalysisTab) {
    setTabState(next);
    const base = `/analysis/${runId}`;
    const params = new URLSearchParams();
    if (next !== "timeline") params.set("tab", next);
    if (connectionLost) params.set("conn", "lost");
    const q = params.toString();
    router.replace(q ? `${base}?${q}` : base, { scroll: false });
  }

  const load = useCallback(
    async (opts?: { showSpinner?: boolean }) => {
      if (opts?.showSpinner) setLoading(true);
      setError(null);
      try {
        const data = await getApiClient().getRun(runId);
        setSnap(data);
        setFeasibility(data.feasibility ?? null);
        setConnectionLost(false);
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
    },
    [runId]
  );

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
            ? resolveSource() === "live"
              ? "اجرا یافت نشد. از صفحه خانه یک تحلیل جدید بسازید."
              : "این تحلیل در حافظه جلسه نیست. از صفحه خانه یک اجرای آزمایشی جدید بسازید."
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

  const onSseEvent = useCallback((event: RunEvent) => {
    setSnap((prev) => {
      if (!prev) return prev;
      if (prev.events.some((e) => e.event_id === event.event_id)) return prev;
      const events = [...prev.events, event];
      return {
        ...prev,
        last_event_id: event.event_id,
        events,
        run: {
          ...prev.run,
          phase: event.phase,
          status: event.status,
          error: event.error_code
            ? {
                code: event.error_code,
                message_fa: event.message_fa,
                retryable: event.error_code === "PROVIDER_UNAVAILABLE",
              }
            : prev.run.error,
        },
      };
    });
    // Refresh snapshot periodically when pipeline likely finished a stage
    if (
      event.phase === "report" ||
      event.status === "partial" ||
      event.status === "completed" ||
      event.status === "failed"
    ) {
      void getApiClient()
        .getRun(runId)
        .then((data) => {
          setSnap(data);
          setFeasibility(data.feasibility ?? null);
        })
        .catch(() => undefined);
    }
  }, [runId]);

  useRunEvents(runId, {
    enabled: resolveSource() === "live" && !loading && !!snap,
    lastEventId: snap?.last_event_id,
    onEvent: onSseEvent,
    onConnectionChange: (ok) => setConnectionLost(!ok),
  });

  async function selectCountry(code: string) {
    setBusySelect(true);
    setError(null);
    // Switch immediately so the page does not feel frozen on markets
    setSnap((prev) =>
      prev
        ? {
            ...prev,
            buyers: [],
            run: { ...prev.run, selected_country: code },
          }
        : prev
    );
    setTab("buyers");
    try {
      const next = await getApiClient().selectCountry(runId, code);
      setSnap(next);
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

  const readiness = useMemo(() => {
    if (!snap) return {} as Partial<Record<AnalysisTab, "ready" | "waiting" | "blocked">>;
    const { run, markets, buyers, report } = snap;
    const blocked =
      run.status === "provider_unavailable" || run.status === "rate_limited";
    return {
      timeline: "ready" as const,
      markets: blocked ? ("blocked" as const) : markets.length ? ("ready" as const) : ("waiting" as const),
      buyers: !run.selected_country
        ? ("waiting" as const)
        : buyers.length
          ? ("ready" as const)
          : ("waiting" as const),
      feasibility: snap.feasibility ? ("ready" as const) : ("waiting" as const),
      report: report ? ("ready" as const) : blocked ? ("blocked" as const) : ("waiting" as const),
    };
  }, [snap]);

  if (loading) {
    return (
      <div className="cockpit-shell mx-auto flex max-w-lg items-center justify-center py-10">
        <LoadingState
          label={fa.loading.pleaseWait}
          stages={[
            fa.loading.stages.prepare,
            fa.loading.stages.fetch,
            fa.loading.stages.analyze,
            fa.loading.stages.almost,
          ]}
        />
      </div>
    );
  }

  if (error && !snap) {
    return (
      <div className="cockpit-shell mx-auto max-w-lg">
        <ErrorState
          message={error}
          onRetry={() => void load({ showSpinner: true })}
        />
      </div>
    );
  }

  if (!snap) {
    return (
      <div className="cockpit-shell">
        <EmptyState />
      </div>
    );
  }

  const { run, events, markets, buyers, report } = snap;
  const blocked =
    run.status === "provider_unavailable" || run.status === "rate_limited";
  const latest = events[events.length - 1];

  return (
    <div className="cockpit-shell mx-auto w-full min-w-0 max-w-6xl">
      <CockpitHeader run={run} />

      {connectionLost ? (
        <ConnectionBanner
          onRetry={() => void load({ showSpinner: true })}
          onClear={() => setConnectionLost(false)}
        />
      ) : null}

      {tab === "timeline" ? (
        <div className="cockpit-timeline min-w-0 space-y-4">
          <ResearchHero run={run} latest={latest} />

          <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,240px)_minmax(0,1.2fr)_minmax(0,0.9fr)]">
            <PhaseRail events={events} runStatus={run.status} />
            <ActivityFeed events={events} />
            <div className="min-w-0 space-y-4">
              <ProgressiveResults
                markets={markets}
                status={run.status}
                onOpenMarkets={() => setTab("markets")}
              />
              <MarketSignalViz markets={markets} />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className="rounded-xl border border-[var(--cockpit-line)] px-3 py-1.5 text-[0.7rem] text-[var(--cockpit-faint)] hover:text-white"
              onClick={() => setConnectionLost(true)}
            >
              {fa.cockpit.simulateDisconnect}
            </button>
          </div>
        </div>
      ) : (
        <div className="study-surface min-w-0 space-y-4 overflow-x-clip p-3 sm:p-5">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[0.65rem] uppercase tracking-[0.14em] text-[#0cb6aa]">
                intelligence pane
              </p>
              <h2 className="text-lg font-semibold text-[var(--study-ink)]">
                {fa.analysis.tabs[tab]}
              </h2>
            </div>
            {run.is_mock ? (
              <span className="mock-banner rounded-lg px-2 py-1 text-xs font-medium">
                {fa.mockBadge}
              </span>
            ) : null}
          </div>

          {tab === "markets" ? (
            blocked ? (
              <EmptyState title={fa.markets.empty} hint={run.error?.message_fa} />
            ) : (
              <MarketComparison
                markets={markets}
                selectedCountry={run.selected_country}
                onSelect={selectCountry}
                selecting={busySelect}
              />
            )
          ) : null}

          {tab === "buyers" ? (
            !run.selected_country ? (
              <EmptyState
                title={fa.buyers.needCountry}
                action={
                  <button
                    type="button"
                    className="nova-btn-ghost"
                    onClick={() => setTab("markets")}
                  >
                    {fa.analysis.tabs.markets}
                  </button>
                }
              />
            ) : busySelect ? (
              <LoadingState
                label={fa.buyers.searching}
                hint={fa.buyers.searchingHint}
                stages={[
                  fa.loading.stages.buyers,
                  fa.loading.stages.buyersSources,
                  fa.loading.stages.buyersRank,
                ]}
              />
            ) : buyers.length === 0 ? (
              <EmptyState
                title={fa.buyers.empty}
                hint={run.error?.message_fa || fa.buyers.emptyHint}
              />
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-ink-muted">{fa.buyers.potentialNote}</p>
                <div className="grid gap-3 md:grid-cols-2">
                  {buyers.map((b) => (
                    <BuyerCard key={`${b.company_name}-${b.website ?? ""}`} buyer={b} />
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
                {feasibility.is_mock_sample ? (
                  <p className="mock-banner rounded-xl px-3 py-2 text-sm">
                    {fa.feasibility.sampleNote}
                  </p>
                ) : null}
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
                <button
                  type="button"
                  className="nova-btn-primary"
                  onClick={() => void recalc()}
                >
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
        </div>
      )}

      <DestinationNav active={tab} onSelect={setTab} readiness={readiness} />
    </div>
  );
}
