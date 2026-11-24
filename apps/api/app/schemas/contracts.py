from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, FiniteFloat, ValidationError, model_validator

from app.core.errors import AppError

RunStatus = Literal[
    "idle",
    "queued",
    "running",
    "partial",
    "completed",
    "failed",
    "rate_limited",
    "provider_unavailable",
    "cancelled",
]

AnalysisPhase = Literal[
    "intake",
    "product_classify",
    "search",
    "trade_stats",
    "market_compare",
    "conclude",
    "buyers",
    "feasibility",
    "report",
]


class Source(BaseModel):
    url: str
    title: str
    publisher: str
    published_at: str | None = None
    fetched_at: str
    provider: str
    reliability_note: str


class MarketMetric(BaseModel):
    key: str
    label_fa: str
    value: str
    unit: str | None = None
    estimated: bool | None = None


class Market(BaseModel):
    country_code: str
    country_name_fa: str
    rank: int
    evidence: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    metrics: list[MarketMetric] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    unknowns: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class BuyerContact(BaseModel):
    email: str | None = None
    phone: str | None = None
    note_fa: str | None = None


class Buyer(BaseModel):
    company_name: str
    website: str | None = None
    country: str
    business_type: str | None = None
    fit_evidence: list[str] = Field(default_factory=list)
    contact: BuyerContact | None = None
    verification_status: Literal[
        "unverified", "source_backed", "needs_review", "rejected"
    ] = "unverified"
    sources: list[Source] = Field(default_factory=list)


class CostItem(BaseModel):
    id: str
    label_fa: str
    amount: float | None = None
    currency: str = "USD"
    unit: str | None = None
    required: bool = False
    note_fa: str | None = None
    # verified | estimated | user_input | missing
    status: Literal["verified", "estimated", "user_input", "missing"] | None = None
    source_url: str | None = None
    as_of: str | None = None


class ScenarioResult(BaseModel):
    id: Literal["conservative", "base", "optimistic"]
    label_fa: str
    revenue: float | None = None
    total_cost: float | None = None
    margin: float | None = None
    margin_pct: float | None = None
    notes_fa: list[str] = Field(default_factory=list)


class Feasibility(BaseModel):
    input_assumptions: dict[str, Any] = Field(default_factory=dict)
    cost_items: list[CostItem] = Field(default_factory=list)
    currency: str = "USD"
    incoterm: str | None = None
    scenario_results: list[ScenarioResult] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    is_mock_sample: bool = False
    break_even_price: float | None = None
    break_even_qty: float | None = None
    sensitivity: dict[str, Any] | None = None


class RunError(BaseModel):
    code: str
    message_fa: str
    retryable: bool = False


class RunOut(BaseModel):
    id: str
    product: str
    origin_country: str
    guessed_hs_code: str | None = None
    hs_confidence: str | None = None
    phase: str
    status: str
    created_at: str
    updated_at: str
    selected_country: str | None = None
    error: RunError | None = None
    is_mock: bool = False
    fixture_id: str | None = None


class RunEventOut(BaseModel):
    event_id: str
    run_id: str
    phase: str
    status: str
    message_fa: str
    timestamp: str
    payload: dict[str, Any] | None = None
    source_refs: list[Source] | None = None
    error_code: str | None = None


class Report(BaseModel):
    run_id: str
    product: str
    origin_country: str
    summary_fa: str
    markets: list[Market] = Field(default_factory=list)
    selected_country: str | None = None
    buyers: list[Buyer] = Field(default_factory=list)
    feasibility: Feasibility | None = None
    risks_fa: list[str] = Field(default_factory=list)
    assumptions_fa: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    collected_at: str
    is_mock: bool = False
    client_name: str | None = None
    company_name: str | None = None


class CreateRunIn(BaseModel):
    product: str = Field(max_length=512)
    origin_country: str = Field(default="ایران", max_length=128)
    hs_code: str | None = Field(default=None, max_length=32)


class CreateRunOut(BaseModel):
    run_id: str


class SelectCountryIn(BaseModel):
    country_code: str


class CostUpdate(BaseModel):
    id: str
    amount: FiniteFloat | None = Field(default=None, ge=0)
    currency: Literal["USD", "IRR"] | None = None


class FeasibilityAssumptions(BaseModel):
    quantity: FiniteFloat | None = Field(default=None, ge=0)
    target_sell_price_usd: FiniteFloat | None = Field(default=None, ge=0)
    fx_rate_usd_irr: FiniteFloat | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    incoterm: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")


class FeasibilityIn(BaseModel):
    cost_updates: list[CostUpdate] | None = None
    input_assumptions: FeasibilityAssumptions | None = None

    @model_validator(mode="wrap")
    @classmethod
    def validate_finance_input(cls, value, handler):
        try:
            return handler(value)
        except ValidationError as exc:
            # Validation errors may contain raw NaN/Infinity, which JSON cannot encode.
            first_error = exc.errors(include_input=False)[0]
            field = ".".join(map(str, first_error["loc"]))
            raise AppError("INVALID_FEASIBILITY_INPUT", f"ورودی امکان‌سنجی نامعتبر است ({field}).", 422) from None


class BuyerSearchState(BaseModel):
    id: str
    country_code: str
    status: Literal["queued", "running", "completed", "partial", "failed"]
    updated_at: str
    error: RunError | None = None


class RunSnapshot(BaseModel):
    run: RunOut
    last_event_id: str | None = None
    events: list[RunEventOut] = Field(default_factory=list)
    markets: list[Market] = Field(default_factory=list)
    buyers: list[Buyer] = Field(default_factory=list)
    buyer_search: BuyerSearchState | None = None
    feasibility: Feasibility | None = None
    report: Report | None = None


class AdminLoginIn(BaseModel):
    username: str
    password: str


class AdminLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProviderConfigOut(BaseModel):
    id: str
    name: str
    enabled: bool
    model: str | None = None
    has_key_configured: bool
    status: str
    usage_note_fa: str
    daily_limit: int | None = None
    used_today: int | None = None


class ProviderUpdateIn(BaseModel):
    enabled: bool | None = None
    model: str | None = None
    api_key: str | None = None  # plaintext only in request body; stored encrypted


class LlmModelOptionOut(BaseModel):
    id: str
    label: str
    provider: str
    group: str
    group_label_fa: str
    is_flash: bool = False
    has_key_configured: bool = False


class TradeSourceStatusOut(BaseModel):
    id: str
    name: str
    status: str  # active | inactive | failed | limited
    optional: bool = False
    last_checked: str | None = None
    note_fa: str | None = None


class RouterProviderOut(BaseModel):
    id: str
    label_fa: str
    base_url: str
    has_key_configured: bool = False
    selected_model: str | None = None
    capability: str = "unchecked"
    output_method: str = ""
    failure_category: str = ""
    tokens_used: int = 0
    estimated_cost_usd: float = 0
    active: bool = False


class SafetySettingsOut(BaseModel):
    max_consecutive_invalid: int = 3
    max_repeated_actions: int = 3
    max_runtime_seconds: int = 1800
    max_run_tokens: int = 200_000


class AdminSettingsOut(BaseModel):
    providers: list[ProviderConfigOut]
    selected_model: str
    selected_provider: str = "google"
    llm_models: list[LlmModelOptionOut] = []
    llm_groups: list[dict] = []
    routers: list[RouterProviderOut] = []
    safety: SafetySettingsOut = SafetySettingsOut()
    trade_sources: list[TradeSourceStatusOut] = []
    connection_message_fa: str
    error_history: list[dict[str, str]]
    is_mock_ui: bool = False


class ModelSelectIn(BaseModel):
    model: str
    provider: str | None = None


class RouterKeyIn(BaseModel):
    api_key: str | None = None


class ModelKeyIn(BaseModel):
    model: str
    api_key: str | None = None  # empty/null clears this version's key only


class TestConnectionIn(BaseModel):
    provider_id: str


class TestConnectionOut(BaseModel):
    ok: bool
    message_fa: str
    checked: bool = False
    connection_status: str = "Failed"
    billing_status: str = "none"


class HealthOut(BaseModel):
    status: str
    service: str
