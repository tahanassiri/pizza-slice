import type {
  Buyer,
  Feasibility,
  FixtureId,
  Market,
  RunEvent,
  RunSnapshot,
  RunStatus,
  AnalysisPhase,
} from "@/types";
import { mockSources } from "./sources";

export const FIXTURE_IDS: FixtureId[] = [
  "happy",
  "sparse",
  "unavailable",
  "quota",
  "partial",
  "incomplete_financial",
];

const now = () => new Date().toISOString();

function baseMarkets(): Market[] {
  return [
    {
      country_code: "DE",
      country_name_fa: "آلمان",
      rank: 1,
      evidence: [
        "تقاضای پایدار برای پسته خام در کانال‌های عمده‌فروشی (نمونه)",
        "حضور واردکنندگان تخصصی آجیل در هامبورگ (نمونه)",
      ],
      opportunities: ["کانال B2B مشخص", "پرداخت نسبتاً شفاف"],
      risks: ["رقابت ترکیه", "نیاز به گواهی‌های غذایی"],
      metrics: [
        { key: "demand", label_fa: "تقاضای برآوردی", value: "متوسط رو به بالا", estimated: true },
        { key: "access", label_fa: "دسترسی", value: "نیازمند مستندات", estimated: true },
      ],
      confidence: "medium",
      unknowns: ["تعرفه دقیق برای HS مبهم"],
      sources: [mockSources.trade, mockSources.news],
    },
    {
      country_code: "AE",
      country_name_fa: "امارات",
      rank: 2,
      evidence: ["نقش هاب توزیع منطقه‌ای (نمونه)", "تجارت مجدد به کشورهای همسایه (نمونه)"],
      opportunities: ["نزدیکی لجستیکی", "سرعت ترخیص نسبی"],
      risks: ["حاشیه رقابتی پایین", "وابستگی به توزیع‌کننده"],
      metrics: [
        { key: "demand", label_fa: "تقاضای برآوردی", value: "متوسط", estimated: true },
        { key: "access", label_fa: "دسترسی", value: "نسبتاً آسان", estimated: true },
      ],
      confidence: "medium",
      unknowns: ["حجم واقعی مصرف داخلی در برابر ترانزیت"],
      sources: [mockSources.trade],
    },
    {
      country_code: "IN",
      country_name_fa: "هند",
      rank: 3,
      evidence: ["رشد مصرف آجیل در بخش شهری (نمونه)"],
      opportunities: ["بازار بزرگ", "تنوع کانال خرده‌فروشی"],
      risks: ["پیچیدگی مقررات", "رقابت قیمتی"],
      metrics: [
        { key: "demand", label_fa: "تقاضای برآوردی", value: "بالا اما پراکنده", estimated: true },
        { key: "access", label_fa: "دسترسی", value: "پیچیده", estimated: true },
      ],
      confidence: "low",
      unknowns: ["شرکای معتبر محلی", "هزینه واقعی انبارداری"],
      sources: [mockSources.news],
    },
  ];
}

function sparseMarkets(): Market[] {
  return [
    {
      country_code: "IQ",
      country_name_fa: "عراق",
      rank: 1,
      evidence: ["اشاره محدود در فهرست‌های تجاری قدیمی (نمونه)"],
      opportunities: ["نزدیکی جغرافیایی"],
      risks: ["شواهد ضعیف", "عدم قطعیت پرداخت"],
      metrics: [
        { key: "demand", label_fa: "تقاضای برآوردی", value: "نامشخص", estimated: true },
      ],
      confidence: "low",
      unknowns: ["حجم واردات", "کانال توزیع قابل اتکا", "تعرفه و مجوزها"],
      sources: [mockSources.news],
    },
  ];
}

export function happyBuyers(): Buyer[] {
  return [
    {
      company_name: "NordNut Import GmbH",
      website: "https://example.com/nordnut",
      country: "DE",
      business_type: "واردکننده عمده آجیل",
      fit_evidence: ["فهرست محصولات شامل پسته (نمونه)", "حضور در نمایشگاه غذایی (نمونه)"],
      contact: { email: "demo@example.com", note_fa: "ایمیل نمایشی — واقعی نیست" },
      verification_status: "source_backed",
      sources: [mockSources.directory],
    },
    {
      company_name: "Hamburg Dry Goods AG",
      website: "https://example.com/hdg",
      country: "DE",
      business_type: "توزیع‌کننده B2B",
      fit_evidence: ["دسته خشکبار در کاتالوگ (نمونه)"],
      verification_status: "needs_review",
      sources: [mockSources.directory],
    },
    {
      company_name: "Rhein Foods Trading",
      country: "DE",
      business_type: "بازرگانی مواد غذایی",
      fit_evidence: ["اشاره در فهرست واردکنندگان (نمونه)"],
      verification_status: "unverified",
      sources: [mockSources.directory],
    },
  ];
}

function buildFeasibility(incomplete: boolean): Feasibility {
  return {
    input_assumptions: {
      unit: "کیلوگرم",
      quantity: incomplete ? null : 1000,
      fx_rate_usd_irr: incomplete ? null : 420000,
      target_sell_price_usd: incomplete ? null : 12.5,
      incoterm: "FOB",
    },
    cost_items: [
      {
        id: "purchase",
        label_fa: "قیمت خرید / تولید",
        amount: incomplete ? null : 8.2,
        currency: "USD",
        unit: "کیلوگرم",
        required: true,
        note_fa: incomplete ? "نامشخص / نیازمند تکمیل" : undefined,
      },
      {
        id: "packaging",
        label_fa: "بسته‌بندی",
        amount: incomplete ? null : 0.4,
        currency: "USD",
        unit: "کیلوگرم",
        required: true,
      },
      {
        id: "inland",
        label_fa: "حمل داخلی",
        amount: 0.3,
        currency: "USD",
        unit: "کیلوگرم",
        required: false,
      },
      {
        id: "intl_freight",
        label_fa: "حمل بین‌المللی",
        amount: incomplete ? null : 0.9,
        currency: "USD",
        unit: "کیلوگرم",
        required: true,
      },
      {
        id: "insurance",
        label_fa: "بیمه",
        amount: 0.1,
        currency: "USD",
        unit: "کیلوگرم",
        required: false,
      },
      {
        id: "duty",
        label_fa: "تعرفه",
        amount: incomplete ? null : 0.5,
        currency: "USD",
        unit: "کیلوگرم",
        required: true,
        note_fa: incomplete ? "نامشخص / نیازمند تکمیل" : "برآورد آزمایشی",
      },
      {
        id: "fees",
        label_fa: "کارمزدها",
        amount: 0.2,
        currency: "USD",
        unit: "کیلوگرم",
        required: false,
      },
    ],
    currency: "USD",
    incoterm: "FOB",
    scenario_results: incomplete
      ? [
          {
            id: "conservative",
            label_fa: "محافظه‌کارانه",
            revenue: null,
            total_cost: null,
            margin: null,
            margin_pct: null,
            notes_fa: ["ورودی ناقص — محاسبه کامل ممکن نیست"],
          },
          {
            id: "base",
            label_fa: "میانه",
            revenue: null,
            total_cost: null,
            margin: null,
            margin_pct: null,
            notes_fa: ["ورودی ناقص — محاسبه کامل ممکن نیست"],
          },
          {
            id: "optimistic",
            label_fa: "خوش‌بینانه",
            revenue: null,
            total_cost: null,
            margin: null,
            margin_pct: null,
            notes_fa: ["ورودی ناقص — محاسبه کامل ممکن نیست"],
          },
        ]
      : [
          {
            id: "conservative",
            label_fa: "محافظه‌کارانه",
            revenue: 11000,
            total_cost: 10600,
            margin: 400,
            margin_pct: 3.6,
            notes_fa: ["نمونه آزمایشی"],
          },
          {
            id: "base",
            label_fa: "میانه",
            revenue: 12500,
            total_cost: 10600,
            margin: 1900,
            margin_pct: 15.2,
            notes_fa: ["نمونه آزمایشی"],
          },
          {
            id: "optimistic",
            label_fa: "خوش‌بینانه",
            revenue: 14000,
            total_cost: 10200,
            margin: 3800,
            margin_pct: 27.1,
            notes_fa: ["نمونه آزمایشی — تضمین سود نیست"],
          },
        ],
    missing_inputs: incomplete
      ? ["قیمت خرید", "حمل بین‌المللی", "تعرفه", "قیمت فروش هدف", "نرخ ارز"]
      : [],
    caveats: [
      "این محاسبه نمونه فاز A است و مبنای تصمیم واقعی نیست.",
      "اعداد از fixture آزمایشی آمده‌اند.",
    ],
    is_mock_sample: true,
  };
}

function timelineEvents(
  runId: string,
  mode: "full" | "partial" | "fail_quota" | "fail_unavailable"
): RunEvent[] {
  const t0 = Date.now();
  const mk = (
    i: number,
    phase: AnalysisPhase,
    status: RunStatus,
    message_fa: string,
    error_code?: string
  ): RunEvent => ({
    event_id: `evt_${runId}_${i}`,
    run_id: runId,
    phase,
    status,
    message_fa,
    timestamp: new Date(t0 + i * 1200).toISOString(),
    error_code,
    source_refs: status === "running" || status === "completed" ? [mockSources.trade] : undefined,
  });

  if (mode === "fail_unavailable") {
    return [
      mk(1, "intake", "completed", "صف شروع تحلیل انجام شد (آزمایشی)"),
      mk(2, "product_classify", "completed", "فهم اولیه محصول (آزمایشی)"),
      mk(
        3,
        "search",
        "provider_unavailable",
        "سرویس جست‌وجو در دسترس نیست (آزمایشی)",
        "PROVIDER_UNAVAILABLE"
      ),
    ];
  }

  if (mode === "fail_quota") {
    return [
      mk(1, "intake", "completed", "صف شروع تحلیل انجام شد (آزمایشی)"),
      mk(2, "product_classify", "completed", "فهم اولیه محصول (آزمایشی)"),
      mk(3, "search", "completed", "جست‌وجوی منابع آغاز شد (آزمایشی)"),
      mk(
        4,
        "trade_stats",
        "rate_limited",
        "سهمیه رایگان تمام شده است (آزمایشی)",
        "QUOTA_EXHAUSTED"
      ),
    ];
  }

  if (mode === "partial") {
    return [
      mk(1, "intake", "completed", "در صف قرار گرفت"),
      mk(2, "product_classify", "completed", "طبقه‌بندی محصول و HS احتمالی"),
      mk(3, "search", "completed", "جست‌وجوی منابع بازار"),
      mk(4, "trade_stats", "completed", "بررسی آمار تجارت (نمونه)"),
      mk(5, "market_compare", "partial", "مقایسه ناقص — برخی منابع پاسخ ندادند"),
    ];
  }

  return [
    mk(1, "intake", "completed", "در صف قرار گرفت"),
    mk(2, "product_classify", "completed", "طبقه‌بندی محصول و HS احتمالی"),
    mk(3, "search", "completed", "جست‌وجوی منابع بازار"),
    mk(4, "trade_stats", "completed", "بررسی آمار تجارت (نمونه)"),
    mk(5, "market_compare", "completed", "مقایسه بازارهای کاندید"),
    mk(6, "conclude", "completed", "رتبه‌بندی بازارها آماده شد"),
  ];
}

export function buildSnapshot(
  runId: string,
  product: string,
  origin: string,
  fixture: FixtureId,
  hs?: string
): RunSnapshot {
  const created = now();
  const events =
    fixture === "unavailable"
      ? timelineEvents(runId, "fail_unavailable")
      : fixture === "quota"
        ? timelineEvents(runId, "fail_quota")
        : fixture === "partial"
          ? timelineEvents(runId, "partial")
          : timelineEvents(runId, "full");

  const last = events[events.length - 1]!;
  const markets =
    fixture === "sparse"
      ? sparseMarkets()
      : fixture === "unavailable" || fixture === "quota"
        ? []
        : fixture === "partial"
          ? baseMarkets().slice(0, 2)
          : baseMarkets();

  const buyers =
    fixture === "happy" || fixture === "incomplete_financial"
      ? happyBuyers()
      : [];

  const feasibility =
    fixture === "incomplete_financial"
      ? buildFeasibility(true)
      : fixture === "happy" || fixture === "partial"
        ? buildFeasibility(false)
        : undefined;

  const status = last.status;
  const phase = last.phase;

  const failedEarly = fixture === "unavailable" || fixture === "quota";
  const run = {
    id: runId,
    product,
    origin_country: origin,
    guessed_hs_code: failedEarly
      ? undefined
      : hs || (fixture === "sparse" ? undefined : "0802.51"),
    hs_confidence: failedEarly
      ? undefined
      : hs
        ? ("medium" as const)
        : fixture === "sparse"
          ? ("unknown" as const)
          : ("low" as const),
    phase,
    status,
    created_at: created,
    updated_at: last.timestamp,
    selected_country: fixture === "happy" || fixture === "incomplete_financial" ? "DE" : undefined,
    error:
      status === "provider_unavailable"
        ? {
            code: "PROVIDER_UNAVAILABLE",
            message_fa: "سرویس تحقیق فعلاً در دسترس نیست.",
            retryable: true,
          }
        : status === "rate_limited"
          ? {
              code: "QUOTA_EXHAUSTED",
              message_fa: "سهمیه رایگان تمام شده است.",
              retryable: false,
            }
          : undefined,
    is_mock: true as const,
    fixture_id: fixture,
  };

  const report =
    status === "completed" || status === "partial"
      ? {
          run_id: runId,
          product,
          origin_country: origin,
          summary_fa:
            fixture === "sparse"
              ? "شواهد محدود است؛ پیشنهاد بازار با اطمینان پایین ارائه شده (آزمایشی)."
              : "سه بازار کاندید با شواهد آزمایشی رتبه‌بندی شدند. این خلاصه نمونه فاز A است.",
          markets,
          selected_country: run.selected_country,
          buyers,
          feasibility,
          risks_fa: ["رقابت قیمتی", "عدم قطعیت تعرفه", "وابستگی به کیفیت منبع"],
          assumptions_fa: [
            "مبدأ ایران",
            "اعداد مالی نمونه و غیرواقعی‌اند",
            "خریداران بالقوه هستند نه تأییدشده",
          ],
          sources: [mockSources.trade, mockSources.directory, mockSources.news],
          collected_at: created,
          is_mock: true as const,
        }
      : undefined;

  return {
    run,
    last_event_id: last.event_id,
    events,
    markets,
    buyers,
    feasibility,
    report,
  };
}

export const adminMockSettings = {
  providers: [
    {
      id: "tavily",
      name: "Tavily",
      enabled: false,
      has_key_configured: false,
      status: "untested" as const,
      usage_note_fa: "در فاز A متصل نیست",
      daily_limit: 50,
      used_today: 0,
    },
    {
      id: "exa",
      name: "Exa",
      enabled: false,
      has_key_configured: false,
      status: "untested" as const,
      usage_note_fa: "در فاز A متصل نیست",
      daily_limit: 50,
      used_today: 0,
    },
    {
      id: "comtrade",
      name: "UN Comtrade",
      enabled: false,
      has_key_configured: false,
      status: "untested" as const,
      usage_note_fa: "در فاز A متصل نیست",
    },
    {
      id: "gemini",
      name: "Gemini",
      enabled: false,
      model: "gemini-3.8-flash",
      has_key_configured: false,
      status: "untested" as const,
      usage_note_fa: "کلید در مرورگر ذخیره نمی‌شود",
    },
  ],
  selected_model: "gemini-3.8-flash",
  llm_models: [
    {
      id: "gemini-3.8-flash",
      label: "Gemini 3.8 Flash",
      provider: "google",
      group: "google",
      group_label_fa: "گوگل (Gemini)",
      is_flash: true,
      has_key_configured: false,
    },
    {
      id: "gemini-3.1-pro-preview",
      label: "Gemini 3.1 Pro Preview",
      provider: "google",
      group: "google",
      group_label_fa: "گوگل (Gemini)",
      has_key_configured: false,
    },
    {
      id: "gpt-6.2-astra",
      label: "GPT-6.2 Astra",
      provider: "openai",
      group: "openai",
      group_label_fa: "اوپن‌ای‌آی (GPT)",
      has_key_configured: false,
    },
    {
      id: "deepseek-flash",
      label: "DeepSeek Flash (V4.1 Flash)",
      provider: "deepseek",
      group: "deepseek",
      group_label_fa: "دیپ‌سیک (DeepSeek)",
      is_flash: true,
      has_key_configured: false,
    },
  ],
  llm_groups: [
    {
      id: "google",
      label_fa: "گوگل (Gemini)",
      models: [
        { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash", provider: "google", is_flash: true },
        { id: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview", provider: "google" },
      ],
    },
    {
      id: "openai",
      label_fa: "اوپن‌ای‌آی (GPT)",
      models: [{ id: "gpt-6.2-astra", label: "GPT-6.2 Astra", provider: "openai" }],
    },
    {
      id: "deepseek",
      label_fa: "دیپ‌سیک (DeepSeek)",
      models: [
        {
          id: "deepseek-flash",
          label: "DeepSeek Flash (V4.1 Flash)",
          provider: "deepseek",
          is_flash: true,
        },
      ],
    },
    {
      id: "flash",
      label_fa: "مدل‌های Flash",
      models: [
        { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash", provider: "google", is_flash: true },
        {
          id: "deepseek-flash",
          label: "DeepSeek Flash (V4.1 Flash)",
          provider: "deepseek",
          is_flash: true,
        },
      ],
    },
  ],
  connection_message_fa: "آزمون اتصال نمایشی — بدون درخواست واقعی",
  error_history: [
    {
      at: "2026-11-22T09:00:00.000Z",
      message_fa: "نمونه: کلید پیکربندی نشده (آزمایشی)",
    },
  ],
  is_mock_ui: true as const,
};
