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
  const qty = Number(feasibility.input_assumptions.quantity ?? 0) || 0;
  const sell = Number(feasibility.input_assumptions.target_sell_price_usd ?? 0) || 0;
  const unitCost = feasibility.cost_items.reduce((sum, c) => sum + (c.amount ?? 0), 0);
  const missing = feasibility.cost_items
    .filter((c) => c.required && (c.amount === null || Number.isNaN(c.amount)))
    .map((c) => c.label_fa);

  if (!qty || !sell || missing.length) {
    return {
      ...feasibility,
      missing_inputs: [
        ...new Set([
          ...missing,
          ...(!qty ? ["تعداد/وزن"] : []),
          ...(!sell ? ["قیمت فروش هدف"] : []),
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

  const factors = { conservative: 0.88, base: 1, optimistic: 1.12 } as const;
  const costFactors = { conservative: 1.05, base: 1, optimistic: 0.95 } as const;

  return {
    ...feasibility,
    missing_inputs: [],
    scenario_results: feasibility.scenario_results.map((s) => {
      const revenue = Math.round(qty * sell * factors[s.id]);
      const total_cost = Math.round(qty * unitCost * costFactors[s.id]);
      const margin = revenue - total_cost;
      const margin_pct = Math.round((margin / revenue) * 1000) / 10;
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

  async postFeasibility(
    id: string,
    costUpdates?: { id: string; amount: number | null }[]
  ): Promise<Feasibility> {
    await delay();
    const snap = requireSnap(id);
    if (!snap.feasibility) {
      throw new Error("FEASIBILITY_UNAVAILABLE");
    }
    let next = structuredClone(snap.feasibility);
    if (costUpdates?.length) {
      next.cost_items = next.cost_items.map((c) => {
        const u = costUpdates.find((x) => x.id === c.id);
        return u ? { ...c, amount: u.amount } : c;
      });
    }
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
