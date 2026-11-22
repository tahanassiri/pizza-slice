import type {
  AdminSettingsView,
  CreateRunInput,
  CreateRunResponse,
  Feasibility,
  FixtureId,
  RunSnapshot,
} from "@/types";

export type {
  AdminSettingsView,
  CreateRunInput,
  CreateRunResponse,
  Feasibility,
  FixtureId,
  RunSnapshot,
};

export interface NovaApiClientLike {
  readonly source: "mock" | "live";
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
  listFixtures?(): FixtureId[];
}
