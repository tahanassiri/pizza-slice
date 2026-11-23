from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, runs
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.session import SessionLocal, init_db
from app.schemas.contracts import HealthOut
from app.services.admin_service import ensure_providers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_providers(db)
    finally:
        db.close()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(runs.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)


@app.get("/health", response_model=HealthOut)
@app.get("/api/health", response_model=HealthOut)
def health():
    return HealthOut(status="ok", service="nova-export-api")
