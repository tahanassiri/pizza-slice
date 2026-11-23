"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fa } from "@/lib/i18n/fa";
import { getApiClient, resolveSource } from "@/lib/api/client";
import { useRunEvents } from "@/lib/api/use-run-events";
import type { AnalysisTab, Feasibility, RunSnapshot } from "@/types";
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

type AnalysisShellProps = {
  runId: string;
  initialTab?: AnalysisTab;
};

export function AnalysisShell(props: AnalysisShellProps) {
  return <AnalysisRun key={props.runId} {...props} />;
}

function AnalysisRun({ runId, initialTab }: AnalysisShellProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const live = resolveSource() === "live";
  const tabFromQuery = searchParams.get("tab");
  const [tab, setTabState] = useState<AnalysisTab>(
    initialTab ?? (isTab(tabFromQuery) ? tabFromQuery : "timeline")
  );
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [feasibility, setFeasibility] = useState<Feasibility | null>(null);
  const [lastCalculation, setLastCalculation] = useState<{ runId: string; data: Feasibility } | null>(null);
  const [busyRecalc, setBusyRecalc] = useState(false);
  const [busySelect, setBusySelect] = useState(false);
  const [connectionLost, setConnectionLost] = useState(
    () => searchParams.get("conn") === "lost"
  );
  const latestSnapshot = useRef<RunSnapshot | null>(null);
  const refreshSnapshot = useRef<(() => void) | null>(null);

  function setTab(next: AnalysisTab) {
    setTabState(next);
    const base = `/analysis/${runId}`;
    const params = new URLSearchParams();
    if (next !== "timeline") params.set("tab", next);
    if (connectionLost) params.set("conn", "lost");
    const q = params.toString();
    router.replace(q ? `${base}?${q}` : base, { scroll: false });
  }

  const acceptSnapshot = useCallback((data: RunSnapshot) => {
    if (data.run.id !== runId || data.events.some((event) => event.run_id !== runId)) return false;
    const current = latestSnapshot.current;
    if (
      current &&
      (data.events.length < current.events.length ||
        (current.last_event_id &&
          data.events[current.events.length - 1]?.event_id !== current.last_event_id) ||
        (data.events.length === current.events.length && data.run.updated_at < current.run.updated_at) ||
        (data.buyer_search && current.buyer_search &&
          data.buyer_search.updated_at < current.buyer_search.updated_at))
    ) {
      return false;
    }
    latestSnapshot.current = data;
    setSnap(data);
    return true;
  }, [runId]);

  const load = useCallback((opts?: { showSpinner?: boolean }) => {
    if (opts?.showSpinner) {
      if (!latestSnapshot.current) setLoading(true);
      setError(null);
    }
    refreshSnapshot.current?.();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    let queued = false;
    let attempts = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    async function fetchSnapshot() {
      if (cancelled) return;
      if (inFlight) {
        queued = true;
        return;
      }
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = null;
      inFlight = true;
      queued = false;
      try {
        const data = await getApiClient().getRun(runId);
        if (cancelled) return;
        const initial = !latestSnapshot.current;
        if (acceptSnapshot(data) && initial) {
          setFeasibility(data.feasibility ?? null);
          setError(null);
        } else if (initial) {
          throw new Error("UNEXPECTED_RUN");
        }
        if (!live && !initial) setConnectionLost(false);
        attempts = 0;
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "";
        const notFound = msg.startsWith("RUN_NOT_FOUND");
        if (!latestSnapshot.current) {
          setError(
            notFound
              ? live
                ? "اجرا یافت نشد. از صفحه خانه یک تحلیل جدید بسازید."
                : "این تحلیل در حافظه جلسه نیست. از صفحه خانه یک اجرای آزمایشی جدید بسازید."
              : fa.error.generic
          );
        }
        if (live && !notFound) {
          const delay = Math.min(8000, 500 * 2 ** attempts);
          attempts += 1;
          retryTimer = setTimeout(fetchSnapshot, delay);
        }
      } finally {
        inFlight = false;
        if (!cancelled) {
          setLoading(false);
          if (queued && !retryTimer) void fetchSnapshot();
        }
      }
    }

    refreshSnapshot.current = () => void fetchSnapshot();
    void fetchSnapshot();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      refreshSnapshot.current = null;
    };
  }, [acceptSnapshot, live, runId]);

  useRunEvents(runId, {
    enabled: live && !!snap,
    lastEventId: snap?.last_event_id,
    onEvent: () => load(),
    onConnectionChange: (ok) => {
      setConnectionLost(!ok);
      if (ok) load();
    },
  });

  const buyerStatus = snap?.buyer_search?.status;
  const buyerPending = buyerStatus === "queued" || buyerStatus === "running";
  useEffect(() => {
    if (!buyerPending) return;
    const timer = window.setInterval(() => void load(), 1000);
    return () => window.clearInterval(timer);
  }, [buyerPending, load]);

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
      if (!acceptSnapshot(next)) void load();
    } catch (cause) {
      setError(cause instanceof Error && cause.message === "RATE_LIMITED"
        ? fa.error.requestLimit
        : fa.error.generic);
    } finally {
      setBusySelect(false);
    }
  }

  async function recalc() {
    if (!feasibility || busyRecalc) return;
    const assumptions = feasibility.input_assumptions;
    const amounts = [assumptions.quantity, assumptions.target_sell_price_usd, assumptions.fx_rate_usd_irr,
      ...feasibility.cost_items.map((c) => c.amount)];
    if (amounts.some((n) => n != null && (!Number.isFinite(Number(n)) || Number(n) < 0)) || assumptions.fx_rate_usd_irr === 0) {
      setError(fa.feasibility.invalidInput);
      return;
    }
    setBusyRecalc(true);
    setError(null);
    try {
      const next = await getApiClient().postFeasibility(
        runId,
        feasibility.cost_items.map(({ id, amount, currency }) => ({ id, amount, currency })),
        { ...assumptions, unit: assumptions.unit?.trim() || null },
      );
      if (latestSnapshot.current?.run.id === runId) {
        setFeasibility(next);
        setLastCalculation({ runId, data: next });
      }
    } catch (exc) {
      if (latestSnapshot.current?.run.id === runId) {
        const message = exc instanceof Error ? exc.message : "";
        setError(message === "INVALID_FEASIBILITY_INPUT" ? fa.feasibility.invalidInput
          : message === "FEASIBILITY_CONFLICT" ? fa.feasibility.conflict : fa.error.generic);
      }
    } finally {
      setBusyRecalc(false);
    }
  }

  const readiness = useMemo(() => {
    if (!snap) return {} as Partial<Record<AnalysisTab, "ready" | "waiting" | "blocked">>;
    const { run, markets, buyers, report } = snap;
    const blocked =
      run.status === "provider_unavailable" || run.status === "rate_limited" || run.status === "failed";
    return {
      timeline: "ready" as const,
      markets: markets.length ? ("ready" as const) : blocked ? ("blocked" as const) : ("waiting" as const),
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
    run.status === "provider_unavailable" || run.status === "rate_limited" || run.status === "failed";
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

          {!live ? <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className="rounded-xl border border-[var(--cockpit-line)] px-3 py-1.5 text-[0.7rem] text-[var(--cockpit-faint)] hover:text-white"
              onClick={() => setConnectionLost(true)}
            >
              {fa.cockpit.simulateDisconnect}
            </button>
          </div> : null}
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
            blocked && !markets.length ? (
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
            ) : busySelect || buyerPending ? (
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
                hint={snap.buyer_search?.error?.message_fa || run.error?.message_fa || fa.buyers.emptyHint}
                action={snap.buyer_search?.error?.retryable ? (
                  <button type="button" className="nova-btn-ghost"
                    onClick={() => void selectCountry(snap.buyer_search!.country_code)}>
                    {fa.error.retry}
                  </button>
                ) : undefined}
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
                <form
                  aria-busy={busyRecalc}
                  onSubmit={(event) => {
                    event.preventDefault();
                    void recalc();
                  }}
                >
                  <fieldset disabled={busyRecalc} className="min-w-0 space-y-4">
                    <CostEditor
                      items={feasibility.cost_items}
                      assumptions={feasibility.input_assumptions}
                      onChange={(id, update) => {
                        setFeasibility((current) => current && ({
                          ...current,
                          cost_items: current.cost_items.map((c) => c.id === id ? { ...c, ...update } : c),
                        }));
                      }}
                      onAssumptionChange={(key, value) => {
                        setFeasibility((current) => current && ({
                          ...current,
                          input_assumptions: { ...current.input_assumptions, [key]: value },
                        }));
                      }}
                    />
                    <button type="submit" className="nova-btn-primary">
                      {busyRecalc ? fa.feasibility.calculating : fa.feasibility.recalc}
                    </button>
                  </fieldset>
                </form>
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
                <ScenarioComparison scenarios={feasibility.scenario_results} currency={feasibility.currency} />
              </div>
            )
          ) : null}

          {tab === "report" ? (
            report ? (
              <ReportView report={lastCalculation?.runId === runId
                ? { ...report, feasibility: lastCalculation.data }
                : report} />
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
