import {
  FIXTURE_IDS,
  adminMockSettings,
  buildSnapshot,
  happyBuyers,
} from "@/fixtures";
import type {
  AdminSettingsView,
  CreateRunInput,
  CreateRunResponse,
  Feasibility,
  FixtureId,
  NovaApiClientLike,
  RunSnapshot,
} from "./mock-types";

const STORAGE_KEY = "nova_phase_a_runs";

/** Session-backed store so refresh/deep-link keeps Phase A fixtures. */
function readAll(): Record<string, RunSnapshot> {
  if (typeof window === "undefined") return {};
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, RunSnapshot>) : {};
  } catch {
    return {};
  }
}

function writeAll(data: Record<string, RunSnapshot>) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function saveSnap(id: string, snap: RunSnapshot) {
  const all = readAll();
  all[id] = snap;
  writeAll(all);
}

function uid(): string {
  return `run_${Math.random().toString(36).slice(2, 10)}`;
}

function delay(ms = 180): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function requireSnap(id: string): RunSnapshot {
  const snap = readAll()[id];
  if (!snap) {
    throw new Error(`RUN_NOT_FOUND:${id}`);
  }
  return snap;
}

function recomputeScenarios(feasibility: Feasibility): Feasibility {
  const { quantity: qty, target_sell_price_usd: sell, fx_rate_usd_irr: fx } = feasibility.input_assumptions;
  const missing = feasibility.cost_items
    .filter((c) => c.amount === null)
    .map((c) => c.label_fa);
  if (fx == null && feasibility.cost_items.some((c) => c.currency === "IRR" && c.amount)) {
    missing.push("نرخ تبدیل ریال به دلار");
  }

  if (qty == null || sell == null || missing.length) {
    return {
      ...feasibility,
      missing_inputs: [
        ...new Set([
          ...missing,
          ...(qty == null ? ["تعداد/وزن"] : []),
          ...(sell == null ? ["قیمت فروش هدف"] : []),
        ]),
      ],
      scenario_results: feasibility.scenario_results.map((s) => ({
        ...s,
        revenue: null,
        total_cost: null,
        margin: null,
        margin_pct: null,
        notes_fa: ["ورودی ناقص — محاسبه کامل ممکن نیست"],
      })),
    };
  }

  const unitCost = feasibility.cost_items.reduce((sum, c) => {
    const amount = c.amount ?? 0;
    return sum + (c.currency === "IRR" && fx ? amount / fx : amount);
  }, 0);
  const factors = { conservative: 0.88, base: 1, optimistic: 1.12 } as const;
  const costFactors = { conservative: 1.05, base: 1, optimistic: 0.95 } as const;

  return {
    ...feasibility,
    missing_inputs: [],
    scenario_results: feasibility.scenario_results.map((s) => {
      const revenue = Math.round(qty * sell * factors[s.id]);
      const total_cost = Math.round(qty * unitCost * costFactors[s.id]);
      const margin = revenue - total_cost;
      const margin_pct = revenue ? Math.round((margin / revenue) * 1000) / 10 : null;
      if (![revenue, total_cost, margin, margin_pct ?? 0].every(Number.isFinite)) {
        throw new Error("INVALID_FEASIBILITY_INPUT");
      }
      return {
        ...s,
        revenue,
        total_cost,
        margin,
        margin_pct,
        notes_fa: ["محاسبه آزمایشی محلی — غیرواقعی"],
      };
    }),
  };
}

export const mockAdapter: NovaApiClientLike = {
  source: "mock",

  listFixtures(): FixtureId[] {
    return [...FIXTURE_IDS];
  },

  async createRun(input: CreateRunInput): Promise<CreateRunResponse> {
    await delay();
    const fixture: FixtureId = input.fixture_id ?? "happy";
    const id = uid();
    const snap = buildSnapshot(
      id,
      input.product.trim(),
      input.origin_country.trim() || "ایران",
      fixture,
      input.hs_code?.trim() || undefined
    );
    saveSnap(id, snap);
    return { run_id: id };
  },

  async getRun(id: string): Promise<RunSnapshot> {
    await delay();
    return structuredClone(requireSnap(id));
  },

  async getMarkets(id: string) {
    await delay();
    return structuredClone(requireSnap(id).markets);
  },

  async selectCountry(id: string, countryCode: string): Promise<RunSnapshot> {
    await delay();
    const snap = requireSnap(id);
    snap.run.selected_country = countryCode;
    snap.run.updated_at = new Date().toISOString();
    if (snap.report) snap.report.selected_country = countryCode;
    // Rebuild from catalog so re-selecting a country does not permanently drop buyers
    if (snap.run.fixture_id === "happy" || snap.run.fixture_id === "incomplete_financial") {
      snap.buyers = happyBuyers().filter((b) => b.country === countryCode);
      if (snap.report) snap.report.buyers = snap.buyers;
    } else {
      snap.buyers = [];
      if (snap.report) snap.report.buyers = [];
    }
    saveSnap(id, snap);
    return structuredClone(snap);
  },

  async getBuyers(id: string) {
    await delay();
    return structuredClone(requireSnap(id).buyers);
  },

  async postFeasibility(id, costUpdates, assumptions) {
    await delay();
    const snap = requireSnap(id);
    if (!snap.feasibility) {
      throw new Error("FEASIBILITY_UNAVAILABLE");
    }
    let next = structuredClone(snap.feasibility);
    next.input_assumptions = { ...next.input_assumptions, ...assumptions };
    next.incoterm = next.input_assumptions.incoterm;
    next.cost_items = next.cost_items.map((c) => {
      const update = costUpdates?.find((x) => x.id === c.id);
      return {
        ...c,
        ...update,
        unit: next.input_assumptions.unit ?? c.unit,
        note_fa: update?.amount == null ? c.note_fa : undefined,
      };
    });
    next = recomputeScenarios(next);
    snap.feasibility = next;
    if (snap.report) snap.report.feasibility = next;
    saveSnap(id, snap);
    return structuredClone(next);
  },

  async getReport(id: string) {
    await delay();
    const snap = requireSnap(id);
    if (!snap.report) throw new Error("REPORT_UNAVAILABLE");
    return structuredClone(snap.report);
  },

  async getAdminSettings(): Promise<AdminSettingsView> {
    await delay();
    return structuredClone(adminMockSettings);
  },
};

/** Soft typing bridge so client.ts does not circular-import NovaApiClient. */
export type { NovaApiClientLike };
