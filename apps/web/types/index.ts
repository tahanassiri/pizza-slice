/** Typed contracts for NOVA Export Intelligence — Phase A (mock-ready for live). */

export type RunStatus =
  | "idle"
  | "queued"
  | "running"
  | "partial"
  | "completed"
  | "failed"
  | "rate_limited"
  | "provider_unavailable"
  | "cancelled";

export type AnalysisPhase =
  | "intake"
  | "product_classify"
  | "search"
  | "trade_stats"
  | "market_compare"
  | "conclude"
  | "buyers"
  | "feasibility"
  | "report";

export type ConfidenceLevel = "high" | "medium" | "low" | "unknown";

export type VerificationStatus =
  | "unverified"
  | "source_backed"
  | "needs_review"
  | "rejected";

export type FixtureId =
  | "happy"
  | "sparse"
  | "unavailable"
  | "quota"
  | "partial"
  | "incomplete_financial";

export interface Source {
  url: string;
  title: string;
  publisher: string;
  published_at?: string;
  fetched_at: string;
  provider: string;
  reliability_note: string;
}

export interface MarketMetric {
  key: string;
  label_fa: string;
  value: string;
  unit?: string;
  estimated?: boolean;
}

export interface Market {
  country_code: string;
  country_name_fa: string;
  rank: number;
  evidence: string[];
  opportunities: string[];
  risks: string[];
  metrics: MarketMetric[];
  confidence: ConfidenceLevel;
  unknowns: string[];
  sources: Source[];
}

export interface BuyerContact {
  email?: string;
  phone?: string;
  note_fa?: string;
}

export interface Buyer {
  company_name: string;
  website?: string;
  country: string;
  business_type?: string;
  fit_evidence: string[];
  contact?: BuyerContact;
  verification_status: VerificationStatus;
  sources: Source[];
}

export interface CostItem {
  id: string;
  label_fa: string;
  amount: number | null;
  currency: string;
  unit?: string;
  required: boolean;
  note_fa?: string;
  status?: "verified" | "estimated" | "user_input" | "missing" | null;
  source_url?: string | null;
  as_of?: string | null;
}

export interface ScenarioResult {
  id: "conservative" | "base" | "optimistic";
  label_fa: string;
  revenue: number | null;
  total_cost: number | null;
  margin: number | null;
  margin_pct: number | null;
  notes_fa: string[];
}

export interface FeasibilityAssumptions {
  quantity?: number | null;
  target_sell_price_usd?: number | null;
  fx_rate_usd_irr?: number | null;
  unit?: string | null;
  incoterm?: string | null;
}

export type CostUpdateInput = Pick<CostItem, "id" | "amount"> & { currency?: string };

export interface Feasibility {
  break_even_price?: number | null;
  break_even_qty?: number | null;
  sensitivity?: Record<string, number | null> | null;
  input_assumptions: FeasibilityAssumptions;
  cost_items: CostItem[];
  currency: string;
  incoterm?: string | null;
  scenario_results: ScenarioResult[];
  missing_inputs: string[];
  caveats: string[];
  is_mock_sample: boolean;
}

export interface RunEvent {
  event_id: string;
  run_id: string;
  phase: AnalysisPhase;
  status: RunStatus;
  message_fa: string;
  timestamp: string;
  payload?: Record<string, unknown>;
  source_refs?: Source[];
  error_code?: string;
}

export interface RunError {
  code: string;
  message_fa: string;
  retryable: boolean;
}

export interface Run {
  id: string;
  product: string;
  origin_country: string;
  guessed_hs_code?: string;
  hs_confidence?: ConfidenceLevel;
  phase: AnalysisPhase;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  selected_country?: string;
  error?: RunError;
  is_mock: boolean;
  fixture_id?: FixtureId | null;
}

export interface Report {
  run_id: string;
  product: string;
  origin_country: string;
  summary_fa: string;
  markets: Market[];
  selected_country?: string;
  buyers: Buyer[];
  feasibility?: Feasibility;
  risks_fa: string[];
  assumptions_fa: string[];
  sources: Source[];
  collected_at: string;
  is_mock: boolean;
  client_name?: string;
  company_name?: string;
}

export interface CreateRunInput {
  product: string;
  origin_country: string;
  hs_code?: string;
  fixture_id?: FixtureId;
}

export interface CreateRunResponse {
  run_id: string;
}

export interface RunSnapshot {
  run: Run;
  last_event_id?: string;
  events: RunEvent[];
  markets: Market[];
  buyers: Buyer[];
  buyer_search?: {
    id: string;
    country_code: string;
    status: "queued" | "running" | "completed" | "partial" | "failed";
    updated_at: string;
    error?: RunError;
  } | null;
  feasibility?: Feasibility;
  report?: Report;
}

export interface ProviderConfig {
  id: string;
  name: string;
  enabled: boolean;
  model?: string;
  has_key_configured: boolean;
  status: "idle" | "ok" | "error" | "quota" | "untested";
  usage_note_fa: string;
  daily_limit?: number;
  used_today?: number;
}

export interface LlmModelOption {
  id: string;
  label: string;
  provider: string;
  group: string;
  group_label_fa: string;
  is_flash?: boolean;
  has_key_configured: boolean;
}

export interface LlmModelGroup {
  id: string;
  label_fa: string;
  models: {
    id: string;
    label: string;
    provider: string;
    is_flash?: boolean;
  }[];
}

export interface TradeSourceStatus {
  id: string;
  name: string;
  status: "active" | "inactive" | "failed" | "limited" | string;
  optional?: boolean;
  last_checked?: string;
  note_fa?: string;
}

export interface AdminSettingsView {
  providers: ProviderConfig[];
  selected_model: string;
  llm_models?: LlmModelOption[];
  llm_groups?: LlmModelGroup[];
  trade_sources?: TradeSourceStatus[];
  connection_message_fa: string;
  error_history: { at: string; message_fa: string }[];
  is_mock_ui: boolean;
}

export type AnalysisTab = "timeline" | "markets" | "buyers" | "feasibility" | "report";
