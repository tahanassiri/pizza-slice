"""Resolve providers — LLM + free web. No mandatory Tavily/Exa/WITS/Comtrade."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.providers.free_wiki import FreeWikiSearchProvider
from app.providers.keyed import build_llm
from app.providers.llm_catalog import models_by_id
from app.providers.model_clearance import is_research_cleared
from app.providers.openai_compat import OpenAICompatLLM, canonical_base, is_router
from app.providers.stubs import StubLLMProvider, StubSearchProvider, StubTradeProvider
from app.services.admin_service import read_model_verification
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


def _router_bundle(db: Session, search: object, mode: str, notes: list[str], provider_id: str, model: str) -> ProviderBundle:
    key = admin_service.get_router_api_key(db, provider_id)
    capability = admin_service.read_router_capability(db, provider_id, model)
    llm: object | None = None
    base = canonical_base(provider_id)
    if key and capability == "capable":
        llm = OpenAICompatLLM(key, model, provider_id=provider_id)
        llm.research_cleared = True
        notes.append(
            f"مدل «{model}» از {base} پژوهش را انجام می‌دهد. "
            "آزمون تصمیم JSON گذشت. تعویض خودکار مدل انجام نمی‌شود. بودجه سرور اعمال می‌شود."
        )
    elif key:
        notes.append(
            f"کلید {provider_id} ذخیره شده اما «{model}» هنوز تصمیم JSON قابل اجرا نداده است "
            f"(وضعیت توانایی: {capability}). پژوهش اجرا نمی‌شود. مدل دیگری جایگزین نشد."
        )
    else:
        notes.append(f"کلید {provider_id} نیست. پژوهش اجرا نمی‌شود و مدل دیگری جایگزین نشد.")
    return ProviderBundle(
        search=search,
        trade=StubTradeProvider(),
        llm=llm,
        mode=mode,
        notes_fa=notes,
        trade_service=None,
    )


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

    search: object = FreeWikiSearchProvider()
    notes.append("جست‌وجوی ابزار: وب رایگان بدون کلید — ویکی‌پدیا به‌تنهایی تصمیم بازار نیست")
    notes.append("یکپارچگی اجباری Tavily/Exa/WITS/Comtrade حذف شده است")

    model = admin_service.get_selected_model(db)
    selected_provider = admin_service.get_selected_provider(db)
    if is_router(selected_provider):
        return _router_bundle(db, search, mode, notes, selected_provider, model)

    meta = models_by_id().get(model)
    model_key = admin_service.get_model_api_key(db, model)
    verification = read_model_verification(db, model)
    llm: object | None = None
    if meta and model_key and is_research_cleared(model, verification):
        llm = build_llm(meta.provider, model_key, model)
        llm.research_cleared = True
        notes.append(
            f"مدل انتخاب‌شده ادمین «{model}» پژوهش را انجام می‌دهد. "
            "رایگان یا پولی بودن مانع نیست. بودجه سرور اعمال می‌شود."
        )
    elif model_key and meta:
        notes.append(
            f"کلید «{model}» ذخیره شده اما وضعیت اتصال «{verification}» است. "
            "پژوهش تا رفع همین خطا ارسال نمی‌شود. مدل دیگری جایگزین نشد."
        )
    elif not meta:
        notes.append(f"مدل «{model}» در فهرست محلی نیست و شناسه کاتالوگ معتبر فرض نمی‌شود")
    else:
        notes.append(f"کلید نسخه «{model}» نیست — پژوهش اجرا نمی‌شود و مسیر اکتشافی جایگزین نمی‌شود")

    return ProviderBundle(
        search=search,
        trade=StubTradeProvider(),  # not used by agent loop
        llm=llm,
        mode=mode,
        notes_fa=notes,
        trade_service=None,
    )
