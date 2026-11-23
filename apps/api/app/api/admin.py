from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.request_budget import enforce_request_budget
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
    ModelKeyIn,
    ModelSelectIn,
    ProviderConfigOut,
    ProviderUpdateIn,
    TestConnectionIn,
    TestConnectionOut,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminLoginOut)
def login(body: AdminLoginIn):
    enforce_request_budget("admin-login", get_settings().login_requests_per_minute, 60)
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
    return {
        "selected_model": view.selected_model,
        "llm_models": view.llm_models,
        "llm_groups": view.llm_groups,
    }


@router.put("/model")
def put_model(
    body: ModelSelectIn,
    db: Session = Depends(get_db),
    _auth: str = Depends(require_admin),
):
    model = body.model.strip()
    if not model:
        raise AppError("INVALID_MODEL", "مدل نامعتبر است.")
    return {"selected_model": admin_service.set_model(db, model)}


@router.put("/model/key")
def put_model_key(
    body: ModelKeyIn,
    db: Session = Depends(get_db),
    _auth: str = Depends(require_admin),
):
    model = body.model.strip()
    if not model:
        raise AppError("INVALID_MODEL", "مدل نامعتبر است.")
    return admin_service.set_model_api_key(db, model, body.api_key)


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
