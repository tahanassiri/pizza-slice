/** Persian UI labels — keep outside component logic for future i18n. */

export const fa = {
  brand: "NOVA",
  brandSubtitle: "هوش صادراتی",
  mockBadge: "داده آزمایشی",
  mockPreviewBadge: "پیش‌نمایش آزمایشی",
  mockNotice:
    "این نسخه فاز A است. همه داده‌ها آزمایشی‌اند و ادعای تحقیق واقعی ندارند.",

  nav: {
    home: "خانه",
    admin: "مدیریت",
    start: "شروع تحلیل",
  },

  home: {
    headline: "بازار صادراتی را با شواهد پیدا کنید",
    support:
      "محصول را وارد کنید؛ مسیر از کشف بازار تا گزارش نهایی را گام‌به‌گام ببینید.",
    cta: "شروع تحلیل صادرات",
    pathLabel: "مسیر فرمان صادرات",
    pathSteps: ["شناخت محصول", "کشف بازار", "خریداران", "امکان‌سنجی", "گزارش"],
  },

  productInput: {
    product: "نام محصول",
    productPlaceholder: "مثلاً پسته خام، زعفران، کاشی سرامیکی",
    origin: "کشور مبدأ",
    originDefault: "ایران",
    hsOptional: "کد HS (اختیاری)",
    hsPlaceholder: "مثلاً ۰۸۰۲",
    fixture: "سناریوی آزمایشی",
    submit: "شروع تحلیل صادرات",
    requiredProduct: "نام محصول را وارد کنید.",
    productTooShort: "نام محصول کوتاه است.",
  },

  fixtures: {
    happy: "مسیر موفق — ۳ بازار و خریداران",
    sparse: "شواهد کم / بدون خریدار",
    unavailable: "سرویس در دسترس نیست",
    quota: "سهمیه تمام شده",
    partial: "تایم‌لاین نیمه‌تمام",
    incomplete_financial: "فیلدهای مالی ناقص",
  } as Record<string, string>,

  analysis: {
    title: "تحلیل صادراتی",
    tabs: {
      timeline: "مرکز فرمان",
      markets: "بازارها",
      buyers: "خریداران",
      feasibility: "امکان‌سنجی",
      report: "گزارش",
    },
    selectCountry: "انتخاب این کشور",
    selectedCountry: "کشور منتخب",
    noCountryYet: "هنوز کشوری انتخاب نشده است.",
    hsGuess: "HS پیشنهادی",
    reconnect: "تلاش مجدد",
    backHome: "بازگشت به خانه",
  },

  cockpit: {
    researchLive: "تحقیق در جریان",
    researchDone: "تحقیق کامل شد",
    researchPartial: "نتیجه ناقص دریافت شد",
    researchBlocked: "تحقیق متوقف شد",
    researchQueued: "در صف اجرای تحقیق",
    currentBeat: "مرحله جاری",
    phaseRail: "مسیر تحقیق",
    activityFeed: "جریان شواهد",
    progressive: "نتایج تدریجی",
    signalMap: "نقشه سیگنال بازار",
    signalHint: "نمایش رابطهٔ اکتشاف — آمار واقعی نیست",
    destinations: "مقاصد بعدی",
    openDetails: "جزئیات مرحله",
    hideDetails: "بستن",
    connectionLost: "اتصال لحظه‌ای قطع شد",
    connectionLostHint:
      "پیش‌نمایش آزمایشی: ارتباط با جریان رویداد برقرار نیست. بدون رفرش دستی دوباره تلاش کنید.",
    noResults: "هنوز نتیجه‌ای برای نمایش نیست",
    noResultsHint: "با رسیدن رویدادهای بعدی، شواهد اینجا ظاهر می‌شوند.",
    waitingPhase: "در انتظار",
    activePhase: "در حال اجرا",
    donePhase: "انجام‌شده",
    errorPhase: "خطا",
    partialPhase: "ناقص",
    evidenceCount: "شواهد",
    marketsReady: "بازار آماده‌شده",
    simulateDisconnect: "شبیه‌سازی قطع اتصال",
    clearDisconnect: "بازگشت به حالت عادی",
    cockpitLabel: "میز فرمان هوشمند",
  },

  status: {
    idle: "آماده",
    queued: "در صف",
    running: "در حال اجرا",
    partial: "نتیجه ناقص",
    completed: "تکمیل شده",
    failed: "ناموفق",
    rate_limited: "محدودیت سهمیه",
    provider_unavailable: "سرویس در دسترس نیست",
    cancelled: "لغو شده",
  } as Record<string, string>,

  phase: {
    intake: "ورود درخواست",
    product_classify: "طبقه‌بندی محصول",
    search: "جست‌وجو",
    trade_stats: "آمار تجارت",
    market_compare: "مقایسه بازار",
    conclude: "جمع‌بندی",
    buyers: "خریداران",
    feasibility: "امکان‌سنجی",
    report: "گزارش",
  } as Record<string, string>,

  providerStatus: {
    idle: "آماده",
    ok: "سالم",
    error: "خطا",
    quota: "سهمیه",
    untested: "آزموده\u200cنشده",
  } as Record<string, string>,

  confidence: {
    high: "اطمینان بالا",
    medium: "اطمینان متوسط",
    low: "اطمینان پایین",
    unknown: "نامشخص",
  } as Record<string, string>,

  verification: {
    unverified: "تأییدنشده",
    source_backed: "مستند به منبع",
    needs_review: "نیازمند بررسی",
    rejected: "رد شده",
  } as Record<string, string>,

  markets: {
    title: "بازارهای پیشنهادی",
    empty: "بازاری برای نمایش نیست.",
    emptyHint: "شواهد کافی برای رتبه‌بندی کشور پیدا نشد.",
    compare: "مقایسه بازارها",
    opportunities: "فرصت‌ها",
    risks: "ریسک‌ها",
    unknowns: "نامشخص‌ها",
    evidence: "شواهد",
    sources: "منابع",
    rank: "رتبه",
  },

  buyers: {
    title: "خریداران بالقوه",
    empty: "خریداری یافت نشد.",
    emptyHint: "برای کشور منتخب شواهد کافی از خریدار بالقوه موجود نیست.",
    needCountry: "ابتدا یک کشور را از تب بازارها انتخاب کنید.",
    potentialNote: "این شرکت‌ها «بالقوه» هستند، نه مشتری تأییدشده.",
    website: "وب‌سایت",
    contact: "تماس",
    fit: "شواهد مرتبط بودن",
    maxNote: "حداکثر ۱۰ خریدار نمایش داده می‌شود.",
  },

  feasibility: {
    title: "امکان‌سنجی اقتصادی",
    sampleNote:
      "محاسبه نمایشی است و نتیجه واقعی یا تضمین سود نیست. فیلدهای نامشخص را تکمیل کنید.",
    editor: "ورودی هزینه‌ها و مفروضات",
    scenarios: "سناریوها",
    missing: "ورودی‌های ناقص",
    caveats: "هشدارها",
    unknown: "نامشخص / نیازمند تکمیل",
    conservative: "محافظه‌کارانه",
    base: "میانه",
    optimistic: "خوش‌بینانه",
    revenue: "درآمد",
    cost: "هزینه کل",
    margin: "حاشیه",
    recalc: "محاسبه آزمایشی",
  },

  report: {
    title: "گزارش نهایی",
    print: "چاپ / PDF",
    summary: "خلاصه فرصت",
    risks: "ریسک‌ها",
    assumptions: "مفروضات",
    sources: "منابع و تاریخ جمع‌آوری",
    optionalClient: "نام مخاطب (اختیاری)",
    optionalCompany: "نام شرکت (اختیاری)",
    collectedAt: "زمان جمع‌آوری",
  },

  admin: {
    loginTitle: "ورود مدیر",
    username: "نام کاربری",
    password: "رمز عبور",
    login: "ورود",
    loginNote: "ورود نمایشی فاز A — احراز هویت واقعی در فاز B.",
    settingsTitle: "تنظیمات سرویس‌ها",
    providers: "ارائه‌دهندگان",
    model: "انتخاب مدل LLM",
    modelKeyFor: "کلید API برای نسخه",
    keySaved: "ذخیره‌شده",
    saveModelKey: "ذخیره کلید این نسخه",
    apiKey: "کلید API",
    apiKeyPlaceholder: "کلید فقط سمت سرور رمزنگاری می‌شود",
    testConnection: "آزمون کلید مدل",
    testProvider: "آزمون ارائه‌دهنده",
    saveProviderKey: "ذخیره کلید",
    clearProviderKey: "پاک کردن کلید",
    researchProviders: "ارائه‌دهندگان تحقیق",
    researchProvidersHint:
      "کلید Tavily و Exa اختیاری است. UN Comtrade کلید اجباری ندارد و پیش‌فرض خاموش است.",
    tradeSources: "منابع آمار تجارت",
    tradeSourcesHint:
      "ترتیب بازیابی: WITS → تحقیق موجود → Comtrade اختیاری. عدد ساختگی تولید نمی‌شود.",
    enableProvider: "فعال‌سازی",
    disableProvider: "غیرفعال‌سازی",
    providerKeyPlaceholder: "کلید API را بچسبانید… (برای Comtrade اختیاری)",
    usage: "مصرف",
    errors: "تاریخچه خطا",
    enabled: "فعال",
    disabled: "غیرفعال",
    noRealKeys:
      "کلید واقعی در مرورگر ذخیره نمی‌شود و به سرویس زنده وصل نیست.",
  },

  empty: {
    title: "موردی برای نمایش نیست",
    retry: "تلاش مجدد",
  },

  error: {
    title: "خطا رخ داد",
    generic: "مشکلی پیش آمد. لطفاً دوباره تلاش کنید.",
    unavailable: "سرویس تحقیق فعلاً در دسترس نیست.",
    quota: "سهمیه رایگان تمام شده است. هیچ هزینه خودکاری ایجاد نمی‌شود.",
    retry: "تلاش مجدد",
  },

  loading: {
    title: "در حال بارگذاری…",
  },

  footer: {
    phase: "فرانت‌اند آزمایشی · Command Bridge",
    privacy: "خصوصی · بدون کلید در مرورگر",
  },
} as const;

export type FaDict = typeof fa;
