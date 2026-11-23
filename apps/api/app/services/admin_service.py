from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_secret, mask_secret
from app.models.entities import AppMeta, ProviderSetting
from app.providers.llm_catalog import all_models, catalog_grouped, models_by_id
from app.schemas.contracts import (
    AdminSettingsOut,
    LlmModelOptionOut,
    ProviderConfigOut,
    ProviderUpdateIn,
    TestConnectionOut,
)

DEFAULT_PROVIDERS = [
    ("tavily", "Tavily", None, 50),
    ("exa", "Exa", None, 50),
    ("comtrade", "UN Comtrade", None, None),
    ("gemini", "Gemini", "gemini-3.8-flash", None),
]

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
                usage_note_fa="کلید فقط سمت سرور ذخیره می‌شود",
                daily_limit=limit,
                used_today=0,
            )
        )
    default = _default_model()
    if not db.get(AppMeta, "selected_model"):
        db.add(AppMeta(key="selected_model", value=default))
    db.commit()


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
            status=r.status,
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
        connection_message_fa="کلید هر نسخه مدل جداگانه رمزنگاری می‌شود؛ فقط سمت سرور.",
        error_history=[
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "message_fa": "بدون کلید نسخهٔ فعال، مسیر رایگان/stub برای LLM استفاده می‌شود.",
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
            if body.enabled is None:
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
        status=row.status,
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
    return {"model": model_id, "has_key_configured": True}


def test_connection(db: Session, provider_id: str) -> TestConnectionOut:
    ensure_providers(db)
    # Model-version test: provider_id may be "model:<id>"
    if provider_id.startswith("model:"):
        model_id = provider_id.removeprefix("model:")
        if model_id not in models_by_id():
            return TestConnectionOut(ok=False, message_fa="مدل یافت نشد.")
        if not model_has_key(db, model_id):
            return TestConnectionOut(
                ok=False,
                message_fa="کلید این نسخه مدل پیکربندی نشده است.",
            )
        return TestConnectionOut(
            ok=True,
            message_fa=f"کلید نسخه «{model_id}» سمت سرور موجود است (بدون تماس پولی در آزمون).",
        )

    row = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == provider_id))
    if not row:
        return TestConnectionOut(ok=False, message_fa="ارائه‌دهنده یافت نشد.")
    if not row.encrypted_api_key:
        row.status = "error"
        db.commit()
        return TestConnectionOut(
            ok=False,
            message_fa="کلید پیکربندی نشده است.",
        )
    row.status = "ok"
    db.commit()
    _ = mask_secret("configured")
    return TestConnectionOut(
        ok=True,
        message_fa="کلید سمت سرور موجود است؛ آزمون زنده اختیاری است (بدون هزینه خودکار).",
    )


def usage_summary(db: Session) -> dict:
    ensure_providers(db)
    rows = list(db.scalars(select(ProviderSetting)).all())
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
    }
