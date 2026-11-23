/**
 * Single API client/adapter surface.
 * mock | live — never mix mock claims with live run data.
 */

import type {
  AdminSettingsView,
  CostUpdateInput,
  CreateRunInput,
  CreateRunResponse,
  Feasibility,
  FeasibilityAssumptions,
  FixtureId,
  RunSnapshot,
} from "@/types";
import { liveAdapter } from "./live-adapter";
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
    costUpdates?: CostUpdateInput[],
    assumptions?: FeasibilityAssumptions
  ): Promise<Feasibility>;
  getReport(id: string): Promise<NonNullable<RunSnapshot["report"]>>;
  getAdminSettings(): Promise<AdminSettingsView>;
  /** Mock-only helper for scenario switching in Phase A UI */
  listFixtures?(): FixtureId[];
}

export function resolveSource(): DataSource {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_DATA_SOURCE === "live") {
    return "live";
  }
  return "mock";
}

export function getApiClient(): NovaApiClient {
  const source = resolveSource();
  if (source === "live") return liveAdapter;
  return mockAdapter;
}

export const api = {
  get client() {
    return getApiClient();
  },
};
