"""Oddiy, jarayon ichidagi IP bo'yicha rate-limit — auth endpoint'lari uchun.

Login'da hisob bo'yicha lockout bor, lekin u ko'p hisobga birma-bir urinishni
(credential stuffing) sekinlashtirmaydi. Bu middleware IP bo'yicha
`/api/auth/{login,refresh,change-password}` ga sirg'aluvchi oyna cheklovi qo'yadi.

Eslatma: xotirada saqlanadi — bitta uvicorn jarayoni uchun. Ko'p worker/instance
bo'lsa, tashqi (Redis) limiter yoki reverse-proxy limiti kerak.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

_PROTECTED = (
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/change-password",
)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            settings.ENV != "test"
            and request.method == "POST"
            and any(path.startswith(p) for p in _PROTECTED)
        ):
            limit = max(1, settings.AUTH_RATE_LIMIT)
            window = max(1, settings.AUTH_RATE_WINDOW_SEC)
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            dq = self._hits[ip]
            cutoff = now - window
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= limit:
                retry = int(dq[0] + window - now) + 1
                return JSONResponse(
                    {"detail": "Juda ko'p urinish. Birozdan so'ng qayta urining."},
                    status_code=429,
                    headers={"Retry-After": str(max(1, retry))},
                )
            dq.append(now)
            # xotira o'smasin: bo'sh kalitlarni vaqti-vaqti bilan tozalash
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
        return await call_next(request)
