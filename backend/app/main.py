import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import admin, auth, export, sections, tables, users
from app.config import settings
from app.database import AsyncSessionLocal
from app.services.auth_service import cleanup_expired_tokens, purge_old_audit_logs
from app.services.export_job_service import cleanup_old as cleanup_old_exports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP tavsiya qilgan asosiy javob header'lari."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")

        # Swagger/Redoc CDN skript va inline style ishlatadi — ularga qattiq CSP qo'ymaymiz.
        if not request.url.path.startswith(_DOCS_PATHS):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
        if settings.is_prod and settings.COOKIE_SECURE:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains; preload",
            )
        return response


async def _retention_loop() -> None:
    """Davriy tozalash: eskirgan refresh tokenlar va audit yozuvlari."""
    interval = max(1, settings.CLEANUP_INTERVAL_HOURS) * 3600
    while True:
        try:
            async with AsyncSessionLocal() as db:
                tokens = await cleanup_expired_tokens(db)
                logs = await purge_old_audit_logs(db)
                exports = await cleanup_old_exports(db)
            if tokens or logs or exports:
                logger.info(
                    "retention: %s token, %s audit, %s eksport o'chirildi", tokens, logs, exports
                )
        except Exception:  # pragma: no cover - fon vazifasi hech qachon crash qilmasin
            logger.exception("retention loop xatosi")
        await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    with contextlib.suppress(OSError):
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    task = asyncio.create_task(_retention_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="SOC/DLP Monitoring Platform — Auth & RBAC moduli",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,  # httpOnly refresh cookie uchun majburiy
    allow_methods=["*"],
    allow_headers=["*"],
)

api = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=api)
app.include_router(users.router, prefix=api)
app.include_router(admin.router, prefix=api)
app.include_router(tables.router, prefix=api)
app.include_router(export.router, prefix=api)
app.include_router(sections.soc_router, prefix=api)
app.include_router(sections.dlp_router, prefix=api)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "env": settings.ENV}
