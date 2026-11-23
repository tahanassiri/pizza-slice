"""Resolve live-capable providers from DB settings. Never log secrets."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models.entities import ProviderSetting
from app.providers.free_wiki import FreeWikiSearchProvider
from app.providers.keyed import KeyedTavilySearch, build_llm
from app.providers.llm_catalog import models_by_id
from app.providers.stubs import StubLLMProvider, StubSearchProvider, StubTradeProvider
from app.services import admin_service
from app.services.admin_service import ensure_providers
from app.trade_data.adapter import TradeDataProviderAdapter
from app.trade_data.comtrade_optional import ComtradePublicProvider
from app.trade_data.research import ResearchTradeProvider
from app.trade_data.service import TradeDataService
from app.trade_data.wits import WitsTradeProvider


@dataclass
class ProviderBundle:
    search: object
    trade: object
    llm: object
    mode: str
    notes_fa: list[str]
    trade_service: TradeDataService | None = None


def _provider_row(db: Session, provider_id: str) -> ProviderSetting | None:
    return db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == provider_id))


def _key_for(db: Session, provider_id: str) -> str | None:
    row = _provider_row(db, provider_id)
    if not row or not row.enabled or not row.encrypted_api_key:
        return None
    plain = decrypt_secret(row.encrypted_api_key)
    return plain or None


def _comtrade_public_enabled(db: Session) -> bool:
    """Public preview is opt-in via enabled flag — key is never mandatory."""
    row = _provider_row(db, "comtrade")
    if not row:
        return False
    return bool(row.enabled)


def resolve_providers(db: Session) -> ProviderBundle:
    ensure_providers(db)
    settings = get_settings()
    mode = (settings.provider_mode or "auto").lower()
    notes: list[str] = []

    if mode == "stub":
        return ProviderBundle(
            search=StubSearchProvider(),
            trade=StubTradeProvider(),
            llm=StubLLMProvider(),
            mode="stub",
            notes_fa=["حالت stub اجباری — بدون تماس خارجی"],
            trade_service=None,
        )

    wiki = FreeWikiSearchProvider()
    notes.append("زمینه محصول: Wikipedia رایگان")

    tavily_key = _key_for(db, "tavily")
    search: object
    if tavily_key:
        search = KeyedTavilySearch(tavily_key)
        notes.append("جست‌وجوی تکمیلی: Tavily (کلید پیکربندی‌شده)")
    else:
        search = wiki
        notes.append("Tavily بدون کلید — تحقیق با Wikipedia/مسیر رایگان")

    comtrade_on = _comtrade_public_enabled(db)
    trade_service = TradeDataService(
        wits=WitsTradeProvider(),
        research=ResearchTradeProvider(search_provider=search),
        comtrade_public=ComtradePublicProvider(enabled=comtrade_on),
    )
    trade = TradeDataProviderAdapter(trade_service)
    notes.append("آمار بازار: TradeDataService (WITS → تحقیق → Comtrade اختیاری)")
    if comtrade_on:
        notes.append("Comtrade public preview: فعال (اختیاری)")
    else:
        notes.append("Comtrade: غیرفعال — کلید الزامی نیست")

    model = admin_service.get_selected_model(db)
    meta = models_by_id().get(model)
    model_key = admin_service.get_model_api_key(db, model)
    if meta and model_key:
        llm: object = build_llm(meta.provider, model_key, model)
        notes.append(f"LLM فعال: {model} ({meta.provider}) — کلید نسخهٔ مدل")
    else:
        llm = StubLLMProvider()
        if not meta:
            notes.append(f"مدل «{model}» در فهرست نیست — LLM stub")
        else:
            notes.append(f"کلید نسخه «{model}» نیست — HS فقط از ورودی کاربر یا unknown")

    return ProviderBundle(
        search=search,
        trade=trade,
        llm=llm,
        mode=mode,
        notes_fa=notes,
        trade_service=trade_service,
    )
