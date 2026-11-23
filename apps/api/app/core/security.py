"""Admin auth + server-side secret encryption. Never log plaintext keys."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

# In-memory sessions for MVP (private demo). Tokens are opaque random strings.
_sessions: dict[str, datetime] = {}
SESSION_TTL = timedelta(hours=12)


def _password_hash(password: str, salt: str, settings: Settings) -> str:
    material = f"{salt}:{password}:{settings.session_secret}".encode()
    return hashlib.sha256(material).hexdigest()


def verify_admin_password(username: str, password: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not hmac.compare_digest(username, settings.admin_username):
        return False
    # Constant-time compare against derived hash of configured password
    expected = _password_hash(settings.admin_password, "nova-admin", settings)
    provided = _password_hash(password, "nova-admin", settings)
    return hmac.compare_digest(expected, provided)


def create_admin_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = datetime.now(timezone.utc) + SESSION_TTL
    return token


def revoke_admin_session(token: str) -> None:
    _sessions.pop(token, None)


def validate_admin_session(token: str | None) -> bool:
    if not token:
        return False
    expires = _sessions.get(token)
    if not expires:
        return False
    if expires < datetime.now(timezone.utc):
        _sessions.pop(token, None)
        return False
    return True


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    token = creds.credentials if creds else None
    if not validate_admin_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="احراز هویت مدیر لازم است.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token or ""


def _fernet(settings: Settings) -> Fernet:
    key = settings.secrets_fernet_key.strip()
    if not key:
        # Deterministic dev key from session_secret so restarts keep decryptable local data.
        # Production MUST set SECRETS_FERNET_KEY.
        digest = hashlib.sha256(settings.session_secret.encode()).digest()
        import base64

        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str, settings: Settings | None = None) -> str:
    if not plaintext:
        return ""
    settings = settings or get_settings()
    return _fernet(settings).encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str, settings: Settings | None = None) -> str:
    if not ciphertext:
        return ""
    settings = settings or get_settings()
    try:
        return _fernet(settings).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"
