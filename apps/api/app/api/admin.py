from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import (
    create_admin_session,
    require_admin,
    revoke_admin_session,
    verify_admin_password,
)
from app.db.session import get_db
from app.schemas.contracts import (
    AdminLoginIn,
    AdminLoginOut,
    AdminSettingsOut,
    ProviderConfigOut,
    ProviderUpdateIn,
    TestConnectionIn,
    TestConnectionOut,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminLoginOut)
def login(body: AdminLoginIn):
    if not verify_admin_password(body.username, body.password):
        raise AppError("AUTH_FAILED", "نام کاربری یا رمز نادرست است.", 401)
    token = create_admin_session()
    return AdminLoginOut(access_token=token)


@router.post("/logout")
def logout(token: str = Depends(require_admin)):
    revoke_admin_session(token)
    return {"ok": True}


@router.get("/providers", response_model=AdminSettingsOut)
def get_providers(db: Session = Depends(get_db), _auth: str = Depends(require_admin)):
    return admin_service.settings_view(db)


@router.patch("/providers/{provider_id}", response_model=ProviderConfigOut)
def patch_provider(
    provider_id: str,
    body: ProviderUpdateIn,
    db: Session = Depends(get_db),
    _auth: str = Depends(require_admin),
):
    return admin_service.update_provider(db, provider_id, body)


@router.get("/model")
def get_model(db: Session = Depends(get_db), _auth: str = Depends(require_admin)):
    view = admin_service.settings_view(db)
    return {"selected_model": view.selected_model}


@router.put("/model")
def put_model(
    body: dict,
    db: Session = Depends(get_db),
    _auth: str = Depends(require_admin),
):
    model = str(body.get("model") or "").strip()
    if not model:
        raise AppError("INVALID_MODEL", "مدل نامعتبر است.")
    return {"selected_model": admin_service.set_model(db, model)}


@router.get("/usage")
def usage(db: Session = Depends(get_db), _auth: str = Depends(require_admin)):
    return admin_service.usage_summary(db)


@router.post("/test-connection", response_model=TestConnectionOut)
def test_connection(
    body: TestConnectionIn,
    db: Session = Depends(get_db),
    _auth: str = Depends(require_admin),
):
    return admin_service.test_connection(db, body.provider_id)
