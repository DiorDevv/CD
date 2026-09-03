"""Audit log yozish yordamchisi — har bir muhim amalda chaqiriladi."""

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def write_audit(
    db: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    commit: bool = False,
) -> None:
    """Audit yozuvini sessiyaga qo'shadi.

    Odatda chaqiruvchi endpoint o'z tranzaksiyasi bilan commit qiladi;
    login_failed kabi mustaqil yozuvlar uchun commit=True beriladi.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=client_ip(request),
    )
    db.add(entry)
    if commit:
        await db.commit()
