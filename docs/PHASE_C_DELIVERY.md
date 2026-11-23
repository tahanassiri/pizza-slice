# Phase C Delivery — Live-capable free path

**Status:** complete  
**Branch:** `design/grok-premium-cockpit`  
**Date:** 2026-11-23

## Path
1. Product intake (default origin ایران)
2. HS classify — user hint or Gemini if keyed; else `unknown` (no invented HS)
3. Market search — World Bank free imports ranking (max 3, confidence `low`) + Wikipedia context sources
4. Trade stats — same free WB indicators
5. Country select → buyer search — Tavily if keyed (still no fabricated verified buyers); else `NO_BUYERS`
6. Feasibility — deterministic server math
7. Report — printable HTML via existing ReportView (`window.print`)

## Honest unavailable
- Missing Tavily/Gemini/Comtrade keys → no paid call; status/messages stay insufficient/unavailable
- Wiki alone never ranks markets
- Buyers never invented from search snippets

## Evidence
- Live smoke (`PROVIDER_MODE=auto`): 3 markets CN/DE/IN for «پسته خام», `is_mock=false`, 11 stage events
- Pytest Phase C cases green (registry stub, mocked WB pipeline, wiki insufficient)

## Plug keys later
Admin Bearer login → `PATCH /api/admin/providers/{tavily|gemini|…}` with `api_key` + `enabled: true`. Keys Fernet-encrypted server-side only.
