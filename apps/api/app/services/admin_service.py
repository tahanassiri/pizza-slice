from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import encrypt_secret, mask_secret
from app.models.entities import AppMeta, ProviderSetting
from app.schemas.contracts import (
    AdminSettingsOut,
    ProviderConfigOut,
    ProviderUpdateIn,
    TestConnectionOut,
)

DEFAULT_PROVIDERS = [
    ("tavily", "Tavily", None, 50),
    ("exa", "Exa", None, 50),
    ("comtrade", "UN Comtrade", None, None),
    ("gemini", "Gemini", "gemini-2.0-flash", None),
]


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
                usage_note_fa="کلید فقط سمت سرور ذخیره می‌شود؛ در فاز B بدون تماس پولی",
                daily_limit=limit,
                used_today=0,
            )
        )
    if not db.get(AppMeta, "selected_model"):
        db.add(AppMeta(key="selected_model", value="gemini-2.0-flash"))
    db.commit()


def settings_view(db: Session) -> AdminSettingsOut:
    ensure_providers(db)
    rows = list(db.scalars(select(ProviderSetting).order_by(ProviderSetting.id)).all())
    selected = db.get(AppMeta, "selected_model")
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
    return AdminSettingsOut(
        providers=providers,
        selected_model=selected.value if selected else "gemini-2.0-flash",
        connection_message_fa="کلیدها رمزنگاری‌شده سمت سرورند؛ هیچ کلیدی به فرانت برنمی‌گردد.",
        error_history=[
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "message_fa": "فاز B: تماس واقعی provider پولی انجام نمی‌شود",
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
        # Encrypt at rest; never log plaintext
        if body.api_key.strip() == "":
            row.encrypted_api_key = None
        else:
            row.encrypted_api_key = encrypt_secret(body.api_key.strip())
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
    row = db.get(AppMeta, "selected_model")
    if not row:
        db.add(AppMeta(key="selected_model", value=model))
    else:
        row.value = model
    db.commit()
    return model


def test_connection(db: Session, provider_id: str) -> TestConnectionOut:
    ensure_providers(db)
    row = db.scalar(select(ProviderSetting).where(ProviderSetting.provider_id == provider_id))
    if not row:
        return TestConnectionOut(ok=False, message_fa="ارائه‌دهنده یافت نشد.")
    if not row.encrypted_api_key:
        row.status = "error"
        db.commit()
        return TestConnectionOut(
            ok=False,
            message_fa="کلید پیکربندی نشده است. در فاز B تماس پولی برقرار نمی‌شود.",
        )
    # Phase B: do not call paid APIs — report configured-but-untested-live
    row.status = "ok"
    db.commit()
    # Mask only — never return key
    _ = mask_secret("configured")
    return TestConnectionOut(
        ok=True,
        message_fa="کلید سمت سرور موجود است؛ آزمون زنده provider به فاز C موکول شده (بدون هزینه).",
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
        ]
    }
