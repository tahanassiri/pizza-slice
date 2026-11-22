/**
 * Single API client/adapter surface.
 * Phase A: mock adapter only. Phase B+: swap implementation without rewriting pages.
 */

import type {
  AdminSettingsView,
  CreateRunInput,
  CreateRunResponse,
  Feasibility,
  FixtureId,
  RunSnapshot,
} from "@/types";
import { mockAdapter } from "./mock-adapter";

export type DataSource = "mock" | "live";

export interface NovaApiClient {
  readonly source: DataSource;
  createRun(input: CreateRunInput): Promise<CreateRunResponse>;
  getRun(id: string): Promise<RunSnapshot>;
  getMarkets(id: string): Promise<RunSnapshot["markets"]>;
  selectCountry(id: string, countryCode: string): Promise<RunSnapshot>;
  getBuyers(id: string): Promise<RunSnapshot["buyers"]>;
  postFeasibility(
    id: string,
    costUpdates?: { id: string; amount: number | null }[]
  ): Promise<Feasibility>;
  getReport(id: string): Promise<NonNullable<RunSnapshot["report"]>>;
  getAdminSettings(): Promise<AdminSettingsView>;
  /** Mock-only helper for scenario switching in Phase A UI */
  listFixtures?(): FixtureId[];
}

function resolveSource(): DataSource {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_DATA_SOURCE === "live") {
    // Live adapter lands in Phase B — fall back to mock until then.
    return "mock";
  }
  return "mock";
}

export function getApiClient(): NovaApiClient {
  const source = resolveSource();
  if (source === "mock") return mockAdapter;
  return mockAdapter;
}

export const api = {
  get client() {
    return getApiClient();
  },
};
