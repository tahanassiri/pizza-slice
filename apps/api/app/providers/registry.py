"""Resolve providers — LLM + free web. No mandatory Tavily/Exa/WITS/Comtrade."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.providers.free_wiki import FreeWikiSearchProvider
from app.providers.keyed import build_llm
from app.providers.llm_catalog import models_by_id
from app.providers.stubs import StubLLMProvider, StubSearchProvider, StubTradeProvider
from app.services import admin_service
from app.services.admin_service import ensure_providers


@dataclass
class ProviderBundle:
    search: object
    trade: object
    llm: object
    mode: str
    notes_fa: list[str]
    trade_service: object | None = None


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

    # Free wiki remains available for legacy buyer search helpers; agent loop uses free_web tools.
    search: object = FreeWikiSearchProvider()
    notes.append("جست‌وجوی ایجنت: وب رایگان (Wikipedia/DuckDuckGo) — بدون کلید اجباری")
    notes.append("یکپارچگی اجباری Tavily/Exa/WITS/Comtrade حذف شده است")

    model = admin_service.get_selected_model(db)
    meta = models_by_id().get(model)
    model_key = admin_service.get_model_api_key(db, model)
    if meta and model_key:
        llm: object = build_llm(meta.provider, model_key, model)
        notes.append(f"LLM تصمیم‌یار تحقیق: {model} ({meta.provider}) — Saved key ≠ Verified")
    else:
        llm = StubLLMProvider()
        if not meta:
            notes.append(f"مدل «{model}» در فهرست نیست — راهبرد اکتشافی بدون مدل")
        else:
            notes.append(
                f"کلید نسخه «{model}» نیست — ایجنت با راهبرد اکتشافی (بدون تصمیم مدل) ادامه می‌دهد"
            )

    return ProviderBundle(
        search=search,
        trade=StubTradeProvider(),  # not used by agent loop
        llm=llm,
        mode=mode,
        notes_fa=notes,
        trade_service=None,
    )
