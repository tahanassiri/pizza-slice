"""Resolve live-capable providers from DB settings. Never log secrets."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models.entities import AppMeta, ProviderSetting
from app.providers.free_wiki import FreeWikiSearchProvider
from app.providers.free_worldbank import FreeWorldBankTradeProvider
from app.providers.keyed import KeyedGeminiLLM, KeyedTavilySearch
from app.providers.stubs import StubLLMProvider, StubSearchProvider, StubTradeProvider
from app.services.admin_service import ensure_providers


@dataclass
class ProviderBundle:
    search: object
    trade: object
    llm: object
    mode: str
    notes_fa: list[str]


def _provider_row(db: Session, provider_id: str) -> ProviderSetting | None:
    return db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == provider_id))


def _key_for(db: Session, provider_id: str) -> str | None:
    row = _provider_row(db, provider_id)
    if not row or not row.enabled or not row.encrypted_api_key:
        return None
    plain = decrypt_secret(row.encrypted_api_key)
    return plain or None


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
        )

    # Free path always available in auto/live
    trade = FreeWorldBankTradeProvider()
    wiki = FreeWikiSearchProvider()
    notes.append("آمار بازار: World Bank رایگان")
    notes.append("زمینه محصول: Wikipedia رایگان")

    tavily_key = _key_for(db, "tavily")
    search: object
    if tavily_key:
        search = KeyedTavilySearch(tavily_key)
        notes.append("جست‌وجوی تکمیلی: Tavily (کلید پیکربندی‌شده)")
    else:
        search = wiki
        notes.append("Tavily بدون کلید — فقط مسیر رایگان/stub صادقانه")

    gemini_key = _key_for(db, "gemini")
    selected = db.get(AppMeta, "selected_model")
    model = selected.value if selected else "gemini-2.0-flash"
    if gemini_key:
        llm: object = KeyedGeminiLLM(gemini_key, model=model)
        notes.append("طبقه‌بندی HS: Gemini (کلید پیکربندی‌شده)")
    else:
        llm = StubLLMProvider()
        notes.append("Gemini بدون کلید — HS فقط از ورودی کاربر یا unknown")

    return ProviderBundle(search=search, trade=trade, llm=llm, mode=mode, notes_fa=notes)
