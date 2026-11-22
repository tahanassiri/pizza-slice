import type { Source } from "@/types";

const fetched = "2026-11-22T10:00:00.000Z";

export const mockSources = {
  trade: {
    url: "https://example.com/trade-stats-demo",
    title: "آمار تجارت نمونه (آزمایشی)",
    publisher: "Demo Trade Desk",
    fetched_at: fetched,
    provider: "mock",
    reliability_note: "داده آزمایشی — قابل استناد برای تصمیم واقعی نیست",
  } satisfies Source,
  directory: {
    url: "https://example.com/buyer-directory-demo",
    title: "فهرست خریداران نمونه",
    publisher: "Demo Directory",
    fetched_at: fetched,
    provider: "mock",
    reliability_note: "داده آزمایشی",
  } satisfies Source,
  news: {
    url: "https://example.com/market-news-demo",
    title: "خبر بازار نمونه",
    publisher: "Demo News",
    published_at: "2026-08-01",
    fetched_at: fetched,
    provider: "mock",
    reliability_note: "داده آزمایشی و احتمالاً قدیمی",
  } satisfies Source,
};
