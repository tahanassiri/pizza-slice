import hmac

from fastapi import Request, Response

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import validate_admin_session


def _run_access_signature(run_id: str) -> str:
    key = get_settings().session_secret.encode()
    return hmac.digest(key, f"nova-run-access:v1:{run_id}".encode(), "sha256").hex()


def grant_run_access(run_id: str, request: Request, response: Response) -> None:
    settings = get_settings()
    response.set_cookie(
        f"nova_{run_id}",
        _run_access_signature(run_id),
        path=f"{settings.api_prefix}/runs/{run_id}",
        max_age=30 * 24 * 60 * 60,
        secure=settings.environment == "production" or request.url.scheme == "https",
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"


def require_run_access(run_id: str, request: Request, response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.casefold() == "bearer" and validate_admin_session(token):
        return

    received = request.cookies.get(f"nova_{run_id}", "").encode()
    expected = _run_access_signature(run_id).encode("ascii")
    if not hmac.compare_digest(received, expected):
        raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
