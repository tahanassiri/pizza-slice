from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_secret
from app.models.entities import AppMeta, ProviderSetting
from app.providers.llm_catalog import all_models, catalog_grouped, models_by_id
from app.providers.model_clearance import billing_status_for, is_research_cleared, normalize_connection_status
from app.schemas.contracts import (
    AdminSettingsOut,
    LlmModelOptionOut,
    ProviderConfigOut,
    ProviderUpdateIn,
    TestConnectionOut,
    TradeSourceStatusOut,
)

# Only the active LLM drives research decisions. No mandatory Tavily/Exa/WITS/Comtrade keys.
DEFAULT_PROVIDERS = [
    ("gemini", "Gemini (legacy row)", "gemini-3.8-flash", None),
]

_PROVIDER_NOTES = {
    "gemini": "ردیف میراثی — انتخاب مدل و کلید نسخه از بخش مدل LLM انجام می‌شود.",
}

LLM_KEY_PREFIX = "llm_model_key::"


def _default_model() -> str:
    return (get_settings().default_llm_model or "gemini-3.8-flash").strip()


def _model_key_meta(model_id: str) -> str:
    return f"{LLM_KEY_PREFIX}{model_id}"


def ensure_providers(db: Session) -> None:
    existing = {p.provider_id for p in db.scalars(select(ProviderSetting)).all()}
    for pid, name, model, limit in DEFAULT_PROVIDERS:
        if pid in existing:
            continue
        db.add(
            ProviderSetting(
                provider_id=pid,
                name=name,
                enabled=0,
                model=model,
                encrypted_api_key=None,
                status="untested",
                usage_note_fa=_PROVIDER_NOTES.get(pid, "کلید فقط سمت سرور ذخیره می‌شود"),
                daily_limit=limit,
                used_today=0,
            )
        )
    # Soft-disable legacy trade/search key rows if present (no wipe)
    for legacy in ("tavily", "exa", "comtrade"):
        row = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == legacy))
        if row:
            row.enabled = 0
            row.usage_note_fa = (
                "غیرفعال — یکپارچگی اجباری حذف شد؛ ایجنت از وب رایگان کشف‌شده استفاده می‌کند."
            )
            row.status = "inactive"
    default = _default_model()
    if not db.get(AppMeta, "selected_model"):
        db.add(AppMeta(key="selected_model", value=default))
    db.commit()


def trade_sources_view(db: Session) -> list[TradeSourceStatusOut]:
    """Research tooling status for admin — no mandatory paid/trade APIs."""
    ensure_providers(db)
    now = datetime.now(timezone.utc).isoformat()
    model = get_selected_model(db)
    has_key = model_has_key(db, model)
    verification = read_model_verification(db, model)
    cleared = is_research_cleared(model, verification)
    return [
        TradeSourceStatusOut(
            id="free_web",
            name="Free web (Wikipedia + DuckDuckGo HTML)",
            status="active",
            optional=False,
            last_checked=now,
            note_fa="جست‌وجوی بدون کلید — حقایق وب جعل نمی‌شود",
        ),
        TradeSourceStatusOut(
            id="active_llm",
            name=f"Active research LLM ({model})",
            status="active" if cleared else "limited",
            optional=False,
            last_checked=now,
            note_fa=(
                "مدل تصمیم‌یار تحقیق — "
                + (
                    f"اتصال: {verification}. صورتحساب: {billing_status_for(verification)}. "
                    "انتخاب ادمین مجوز فراخوانی همین مدل است و بودجه سرور اعمال می‌شود."
                    if has_key
                    else "بدون کلید همین نسخه، پژوهش اجرا نمی‌شود"
                )
            ),
        ),
    ]


def get_selected_model(db: Session) -> str:
    ensure_providers(db)
    selected = db.get(AppMeta, "selected_model")
    default = _default_model()
    if selected and selected.value.strip():
        mid = selected.value.strip()
        # If DB still points at a removed/outdated id, remapped to current default
        if mid in models_by_id():
            return mid
        selected.value = default
        db.commit()
        return default
    return default


def get_model_api_key(db: Session, model_id: str) -> str | None:
    """Plaintext key for a specific model version, or legacy gemini provider key."""
    ensure_providers(db)
    row = db.get(AppMeta, _model_key_meta(model_id))
    if row and row.value:
        from app.core.security import decrypt_secret

        plain = decrypt_secret(row.value)
        if plain:
            return plain
    # Backward compat: gemini-* can fall back to provider-level gemini key
    meta = models_by_id().get(model_id)
    if meta and meta.provider == "google":
        prow = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == "gemini"))
        if prow and prow.encrypted_api_key:
            from app.core.security import decrypt_secret

            plain = decrypt_secret(prow.encrypted_api_key)
            if plain:
                return plain
    return None


def model_has_key(db: Session, model_id: str) -> bool:
    row = db.get(AppMeta, _model_key_meta(model_id))
    if row and row.value:
        return True
    meta = models_by_id().get(model_id)
    if meta and meta.provider == "google":
        prow = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == "gemini"))
        if prow and prow.encrypted_api_key:
            return True
    return False


def llm_models_view(db: Session) -> list[LlmModelOptionOut]:
    ensure_providers(db)
    return [
        LlmModelOptionOut(
            id=m.id,
            label=m.label,
            provider=m.provider,
            group=m.group,
            group_label_fa=m.group_label_fa,
            is_flash=m.is_flash,
            has_key_configured=model_has_key(db, m.id),
        )
        for m in all_models()
    ]


def settings_view(db: Session) -> AdminSettingsOut:
    ensure_providers(db)
    rows = list(db.scalars(select(ProviderSetting).order_by(ProviderSetting.id)).all())
    providers = [
        ProviderConfigOut(
            id=r.provider_id,
            name=r.name,
            enabled=bool(r.enabled),
            model=r.model,
            has_key_configured=bool(r.encrypted_api_key),
            status="untested" if r.status == "ok" and r.provider_id != "comtrade" else r.status,
            usage_note_fa=r.usage_note_fa,
            daily_limit=r.daily_limit,
            used_today=r.used_today,
        )
        for r in rows
    ]
    selected = get_selected_model(db)
    return AdminSettingsOut(
        providers=providers,
        selected_model=selected,
        llm_models=llm_models_view(db),
        llm_groups=catalog_grouped(),
        trade_sources=trade_sources_view(db),
        connection_message_fa=(
            "کلید هر نسخه مدل جداگانه رمزنگاری می‌شود. "
            "مدل فعال تصمیم‌یار تحقیق است (نه فقط HS). "
            "Saved key ≠ Verified connection. "
            "جست‌وجوی وب رایگان بدون کلید اجباری Tavily/Exa/WITS/Comtrade."
        ),
        error_history=[
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "message_fa": "پژوهش با مدل انتخاب‌شده ادمین اجرا می‌شود. اگر اتصال یا صورتحساب خطا بدهد، همان خطا نشان داده می‌شود. راهبرد اکتشافی اجرا نمی‌شود.",
            }
        ],
        is_mock_ui=False,
    )


def update_provider(db: Session, provider_id: str, body: ProviderUpdateIn) -> ProviderConfigOut:
    ensure_providers(db)
    row = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == provider_id))
    if not row:
        from app.core.errors import AppError

        raise AppError("PROVIDER_NOT_FOUND", "ارائه‌دهنده یافت نشد.", 404)
    if body.enabled is not None:
        row.enabled = 1 if body.enabled else 0
    if body.model is not None:
        row.model = body.model
    if body.api_key is not None:
        if body.api_key.strip() == "":
            row.encrypted_api_key = None
            # Comtrade key is optional — clearing key must NOT force-disable public preview
            if body.enabled is None and provider_id != "comtrade":
                row.enabled = 0
        else:
            row.encrypted_api_key = encrypt_secret(body.api_key.strip())
            # Saving a key enables the provider so runtime can use it
            if body.enabled is None:
                row.enabled = 1
        row.status = "untested"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ProviderConfigOut(
        id=row.provider_id,
        name=row.name,
        enabled=bool(row.enabled),
        model=row.model,
        has_key_configured=bool(row.encrypted_api_key),
        status="untested" if row.status == "ok" and provider_id != "comtrade" else row.status,
        usage_note_fa=row.usage_note_fa,
        daily_limit=row.daily_limit,
        used_today=row.used_today,
    )


def set_model(db: Session, model: str) -> str:
    model = model.strip()
    if model not in models_by_id():
        from app.core.errors import AppError

        raise AppError("INVALID_MODEL", "نسخه مدل در فهرست پشتیبانی‌شده نیست.")
    row = db.get(AppMeta, "selected_model")
    if not row:
        db.add(AppMeta(key="selected_model", value=model))
    else:
        row.value = model
    db.commit()
    return model


def set_model_api_key(db: Session, model_id: str, api_key: str | None) -> dict:
    """Save or clear encrypted key for one model version only."""
    if model_id not in models_by_id():
        from app.core.errors import AppError

        raise AppError("INVALID_MODEL", "نسخه مدل نامعتبر است.")
    meta_key = _model_key_meta(model_id)
    row = db.get(AppMeta, meta_key)
    if api_key is None or api_key.strip() == "":
        if row:
            db.delete(row)
            db.commit()
        return {"model": model_id, "has_key_configured": False}
    encrypted = encrypt_secret(api_key.strip())
    if not row:
        db.add(AppMeta(key=meta_key, value=encrypted))
    else:
        row.value = encrypted
    db.commit()
    _write_model_verification(db, model_id, "Configured")
    return {"model": model_id, "has_key_configured": True}


def _verify_key(model_id: str) -> str:
    return f"llm_verify::{model_id}"


def read_model_verification(db: Session, model_id: str) -> str:
    row = db.get(AppMeta, _verify_key(model_id))
    if not row or not row.value:
        return "Configured" if model_has_key(db, model_id) else "Failed"
    try:
        import json

        payload = json.loads(row.value)
    except json.JSONDecodeError:
        return "Failed"
    status = normalize_connection_status(str(payload.get("connection_status") or "Failed"))
    return status


def _write_model_verification(db: Session, model_id: str, status: str, *, detail: str = "") -> None:
    import json

    payload = json.dumps(
        {
            "connection_status": status,
            "detail": detail[:300],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    key = _verify_key(model_id)
    row = db.get(AppMeta, key)
    if row:
        row.value = payload
    else:
        db.add(AppMeta(key=key, value=payload))
    db.commit()


def _connection_message(model_id: str, status: str, *, http_status: int | None) -> str:
    http = f"HTTP {http_status}" if http_status is not None else "بدون پاسخ HTTP"
    labels = {
        "Verified": (
            f"Verified — اتصال «{model_id}» برقرار شد ({http}). "
            "هزینهٔ احتمالی داخل بودجه سرور مجاز است."
        ),
        "Billing problem": (
            f"Billing problem — «{model_id}» مشکل صورتحساب برگرداند ({http}). "
            "اتصال و صورتحساب جدا ثبت شدند. مدل دیگری جایگزین نشد."
        ),
        "Rate-limited": f"Rate-limited — سهمیه یا نرخ «{model_id}» محدود است ({http}).",
        "Unavailable": f"Unavailable — مدل «{model_id}» در نقطهٔ پایانی در دسترس نیست ({http}). شناسه کاتالوگ معتبر فرض نشد.",
        "Failed": f"Failed — آزمون اتصال «{model_id}» ناموفق بود ({http}).",
        "Configured": f"Configured — کلید «{model_id}» ذخیره شده و هنوز آزمون زنده نشده است.",
    }
    return labels.get(status, f"{status} — {http}")


def test_connection(db: Session, provider_id: str) -> TestConnectionOut:
    ensure_providers(db)
    # Model-version test: provider_id may be "model:<id>"
    if provider_id.startswith("model:"):
        from app.providers.keyed import probe_selected_endpoint
        from app.providers.model_clearance import billing_status_for, classify_probe

        model_id = provider_id.removeprefix("model:")
        meta = models_by_id().get(model_id)
        if meta is None:
            return TestConnectionOut(
                ok=False,
                checked=False,
                connection_status="Unavailable",
                message_fa="شناسه مدل در فهرست محلی نیست و معتبر فرض نمی‌شود.",
            )
        if not model_has_key(db, model_id):
            return TestConnectionOut(
                ok=False,
                checked=False,
                connection_status="Failed",
                message_fa="کلید این نسخه مدل پیکربندی نشده است.",
            )
        key = get_model_api_key(db, model_id) or ""
        probe = probe_selected_endpoint(meta.provider, model_id, key)
        status = classify_probe(
            provider=meta.provider,
            model_id=model_id,
            http_status=probe.get("http_status"),
            body=str(probe.get("body") or ""),
            error=probe.get("error"),
        )
        _write_model_verification(db, model_id, status, detail=str(probe.get("error") or probe.get("http_status") or ""))
        return TestConnectionOut(
            ok=status == "Verified",
            checked=True,
            connection_status=status,
            billing_status=billing_status_for(status),
            message_fa=_connection_message(model_id, status, http_status=probe.get("http_status")),
        )

    row = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == provider_id))
    if not row:
        return TestConnectionOut(ok=False, message_fa="ارائه‌دهنده یافت نشد.")

    if provider_id in {"comtrade", "tavily", "exa", "wits"}:
        row.enabled = 0
        row.status = "inactive"
        db.commit()
        return TestConnectionOut(
            ok=False,
            checked=False,
            connection_status="Unavailable",
            message_fa="این ارائه‌دهنده در مسیر تحقیق فعال نیست و آزمونی به API آن فرستاده نشد.",
        )

    if not row.encrypted_api_key:
        row.status = "error"
        db.commit()
        return TestConnectionOut(
            ok=False,
            checked=False,
            connection_status="Failed",
            message_fa="کلید پیکربندی نشده است.",
        )
    row.status = "untested"
    db.commit()
    return TestConnectionOut(
        ok=False,
        checked=False,
        connection_status="Configured",
        message_fa="کلید سمت سرور ذخیره شده است. این ردیف مسیر پژوهش مدل نیست.",
    )


def usage_summary(db: Session) -> dict:
    from app.models.entities import AgentBudget, UsageAudit
    from app.tools.budget import ensure_global_budget

    ensure_providers(db)
    rows = list(db.scalars(select(ProviderSetting)).all())
    budget = ensure_global_budget(db)
    recent = list(
        db.scalars(select(UsageAudit).order_by(UsageAudit.id.desc()).limit(40)).all()
    )
    return {
        "providers": [
            {
                "id": r.provider_id,
                "used_today": r.used_today,
                "daily_limit": r.daily_limit,
                "has_key_configured": bool(r.encrypted_api_key),
            }
            for r in rows
        ],
        "selected_model": get_selected_model(db),
        "selected_model_has_key": model_has_key(db, get_selected_model(db)),
        "agent_budget": {
            "scope": budget.scope,
            "max_model_calls": budget.max_model_calls,
            "max_search_queries": budget.max_search_queries,
            "max_pages": budget.max_pages,
            "max_retries": budget.max_retries,
            "max_wall_seconds": budget.max_wall_seconds,
            "model_calls_used": budget.model_calls_used,
            "search_queries_used": budget.search_queries_used,
            "pages_used": budget.pages_used,
        },
        "recent_tool_usage": [
            {
                "run_id": u.run_id,
                "provider_id": u.provider_id,
                "tool_name": u.tool_name,
                "units": u.units,
                "ok": bool(u.ok),
                "detail_fa": u.detail_fa,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in recent
        ],
    }


def update_global_budget(
    db: Session,
    *,
    max_model_calls: int | None = None,
    max_search_queries: int | None = None,
    max_pages: int | None = None,
    max_retries: int | None = None,
    max_wall_seconds: int | None = None,
) -> dict:
    from datetime import datetime, timezone

    from app.tools.budget import ensure_global_budget

    budget = ensure_global_budget(db)
    if max_model_calls is not None:
        budget.max_model_calls = max(1, int(max_model_calls))
    if max_search_queries is not None:
        budget.max_search_queries = max(1, int(max_search_queries))
    if max_pages is not None:
        budget.max_pages = max(1, int(max_pages))
    if max_retries is not None:
        budget.max_retries = max(0, int(max_retries))
    if max_wall_seconds is not None:
        budget.max_wall_seconds = max(30, int(max_wall_seconds))
    budget.updated_at = datetime.now(timezone.utc)
    db.commit()
    return usage_summary(db)["agent_budget"]
