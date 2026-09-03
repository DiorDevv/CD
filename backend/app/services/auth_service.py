"""Login oqimi biznes-mantig'i: parol tekshirish, urinishlar limiti, lock, token rotation."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.audit import write_audit
from app.core.security import (
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.audit_log import AuditAction, AuditLog
from app.models.refresh_token import RefreshToken
from app.models.user import User


class LoginError(Exception):
    """Login rad etilganda ko'tariladi — barchasi 401 sifatida qaytariladi."""

    def __init__(self, detail: str, *, locked: bool = False) -> None:
        super().__init__(detail)
        self.detail = detail
        self.locked = locked


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def authenticate(
    db: AsyncSession, *, username: str, password: str, request: Request | None
) -> User:
    """Foydalanuvchini tekshiradi. Muvaffaqiyatli bo'lsa User qaytaradi.

    Xato holatlarda LoginError ko'taradi va audit yozadi.
    Vaqt hujumidan (user enumeration) himoya uchun xabarlar umumiy.
    Qator `FOR UPDATE` bilan qulflanadi — parallel noto'g'ri loginlarda
    `failed_attempts` hisoblagichi buzilmaydi (race condition yo'q).
    """
    res = await db.execute(
        select(User).where(User.username == username).with_for_update()
    )
    user = res.scalar_one_or_none()

    generic = "Login yoki parol noto'g'ri"

    if user is None:
        # User yo'q bo'lsa ham bcrypt vaqtini "sarflaymiz" (timing attack himoyasi)
        verify_password(password, "$2b$12$" + "x" * 53)
        await write_audit(
            db,
            action=AuditAction.LOGIN_FAILED,
            details={"username": username, "reason": "user_not_found"},
            request=request,
            commit=True,
        )
        raise LoginError(generic)

    # 1) Lock tekshiruvi
    if user.locked_until is not None and user.locked_until > _now():
        remaining = int((user.locked_until - _now()).total_seconds() // 60) + 1
        await write_audit(
            db,
            action=AuditAction.LOGIN_FAILED,
            user_id=user.id,
            details={"reason": "account_locked", "minutes_left": remaining},
            request=request,
            commit=True,
        )
        raise LoginError(
            f"Hisob vaqtincha bloklangan. ~{remaining} daqiqadan so'ng qayta urinib ko'ring",
            locked=True,
        )

    # 2) is_active tekshiruvi
    if not user.is_active:
        await write_audit(
            db,
            action=AuditAction.LOGIN_FAILED,
            user_id=user.id,
            details={"reason": "inactive"},
            request=request,
            commit=True,
        )
        raise LoginError("Hisob bloklangan. Administrator bilan bog'laning")

    # 3) Parol tekshiruvi
    if not verify_password(password, user.hashed_password):
        user.failed_attempts += 1
        attempts_reached = user.failed_attempts
        locked_now = False
        if user.failed_attempts >= settings.MAX_FAILED_ATTEMPTS:
            user.locked_until = _now() + timedelta(minutes=settings.LOCKOUT_MINUTES)
            user.failed_attempts = 0
            locked_now = True
        await write_audit(
            db,
            action=AuditAction.LOGIN_FAILED,
            user_id=user.id,
            details={"reason": "bad_password", "attempts": attempts_reached},
            request=request,
        )
        if locked_now:
            await write_audit(
                db,
                action=AuditAction.ACCOUNT_LOCKED,
                user_id=user.id,
                details={
                    "minutes": settings.LOCKOUT_MINUTES,
                    "after_attempts": attempts_reached,
                },
                request=request,
            )
        await db.commit()
        if locked_now:
            raise LoginError(
                f"Juda ko'p noto'g'ri urinish. Hisob {settings.LOCKOUT_MINUTES} daqiqaga bloklandi",
                locked=True,
            )
        raise LoginError(generic)

    # 4) Muvaffaqiyat — hisoblagichlarni tozalash
    user.failed_attempts = 0
    user.locked_until = None
    await write_audit(
        db,
        action=AuditAction.LOGIN,
        user_id=user.id,
        details={"username": user.username, "role": user.role.value},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def issue_refresh_token(db: AsyncSession, user: User) -> str:
    """Yangi refresh token yaratadi, DB'ga hash saqlaydi, xom tokenni qaytaradi."""
    raw = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            expires_at=refresh_token_expiry(),
        )
    )
    await db.commit()
    return raw


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str, *, request: Request | None
) -> tuple[User, str]:
    """Refresh tokenni tekshiradi, bekor qiladi va yangisini beradi (rotation).

    Reuse detection: allaqachon almashtirilgan (revoked) tokenni qayta ishlatishga
    urinilsa — bu o'g'irlangan token belgisi. O'sha foydalanuvchining BARCHA refresh
    tokenlari bekor qilinadi va hodisa audit'ga yoziladi.
    """
    token_hash = hash_refresh_token(raw_token)
    res = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rec = res.scalar_one_or_none()

    if rec is None:
        raise LoginError("Refresh token yaroqsiz")

    if rec.revoked:
        # Token oilasini butunlay bekor qilamiz
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == rec.user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await write_audit(
            db,
            action=AuditAction.TOKEN_REUSE_DETECTED,
            user_id=rec.user_id,
            details={"note": "revoked refresh token replayed — barcha sessiyalar bekor qilindi"},
            request=request,
        )
        await db.commit()
        raise LoginError("Sessiya xavfsizlik sababli bekor qilindi. Qaytadan tizimga kiring")

    if rec.expires_at <= _now():
        raise LoginError("Refresh token muddati tugagan")

    user = await db.get(User, rec.user_id)
    if user is None or not user.is_active:
        rec.revoked = True
        await db.commit()
        raise LoginError("Foydalanuvchi mavjud emas yoki bloklangan")

    rec.revoked = True
    new_raw = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(new_raw),
            expires_at=refresh_token_expiry(),
        )
    )
    await write_audit(
        db, action=AuditAction.TOKEN_REFRESHED, user_id=user.id, request=request
    )
    await db.commit()
    return user, new_raw


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await db.commit()


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> uuid.UUID | None:
    token_hash = hash_refresh_token(raw_token)
    res = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rec = res.scalar_one_or_none()
    if rec is None:
        return None
    rec.revoked = True
    await db.commit()
    return rec.user_id


# --- Fon tozalash (retention) --------------------------------------------------


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """Muddati tugagan yoki ancha oldin bekor qilingan refresh tokenlarni o'chiradi."""
    cutoff = _now() - timedelta(days=settings.REFRESH_TOKEN_RETENTION_DAYS)
    result = await db.execute(
        delete(RefreshToken).where(
            (RefreshToken.expires_at < _now())
            | ((RefreshToken.revoked.is_(True)) & (RefreshToken.created_at < cutoff))
        )
    )
    await db.commit()
    return result.rowcount or 0


async def purge_old_audit_logs(db: AsyncSession) -> int:
    """Retention muddatidan oshgan audit yozuvlarini o'chiradi (0 = cheksiz)."""
    if settings.AUDIT_RETENTION_DAYS <= 0:
        return 0
    cutoff = _now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0
