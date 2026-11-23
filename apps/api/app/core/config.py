from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NOVA Export API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = f"sqlite:///{DATA_DIR / 'nova.db'}"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Admin — change in production via env; never commit real secrets
    admin_username: str = "admin"
    admin_password: str = "nova-dev-change-me"
    session_secret: str = "dev-session-secret-change-me"
    # Fernet key for encrypting provider API keys at rest (generate with Fernet.generate_key())
    secrets_fernet_key: str = ""

    sse_heartbeat_seconds: float = 15.0
    orchestrator_step_delay_ms: int = 120
    # auto = free World Bank/Wiki + keyed providers when configured; stub = no external calls
    provider_mode: str = "auto"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
