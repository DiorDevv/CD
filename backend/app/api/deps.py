"""FastAPI dependency'lar — autentifikatsiya va role tekshiruvi.

Himoya BACKEND darajasida shu yerda qat'iy amalga oshiriladi.
"""

import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Autentifikatsiya talab qilinadi",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Access tokenni tekshiradi va foydalanuvchini qaytaradi.

    FastAPI bu dependency natijasini bir so'rov davomida kešlaydi, shuning uchun
    bir nechta joyda ishlatilsa ham DB'ga faqat bir marta murojaat qilinadi.
    """
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_EXC

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token muddati tugagan",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise _CREDENTIALS_EXC

    sub = payload.get("sub")
    if not sub:
        raise _CREDENTIALS_EXC
    try:
        user_id = uuid.UUID(str(sub))
    except ValueError:
        raise _CREDENTIALS_EXC

    user = await db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchi bloklangan",
        )

    # Xavfsizlik shtampi: parol o'zgargan yoki user bloklangan bo'lsa, eski
    # access tokenlar (30 daqiqagacha amal qiladigan) darhol yaroqsiz bo'ladi.
    if payload.get("tv") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya bekor qilingan. Qaytadan tizimga kiring",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.current_user = user
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """`must_change_password` faol bo'lsa — faqat parol o'zgartirishga ruxsat.

    Bu dependency himoyalangan biznes-endpoint'larda ishlatiladi.
    /auth/change-password esa faqat get_current_user'dan foydalanadi.
    """
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Avval parolni o'zgartirish talab qilinadi",
            headers={"X-Password-Change-Required": "1"},
        )
    return user


def require_role(*roles: UserRole | str):
    """Berilgan rollardan biriga ega bo'lishni talab qiladi.

    Namuna:  user = Depends(require_role(UserRole.soc_admin, UserRole.viewer))
    """
    allowed: set[str] = {r.value if isinstance(r, UserRole) else str(r) for r in roles}

    async def _checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role.value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ushbu amal uchun ruxsat yo'q",
            )
        return user

    return _checker


async def require_super_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """Yagona (modul darajasidagi) dependency — kešlash tufayli bir so'rovda
    router-level va handler-level ishlatilsa ham bir marta bajariladi."""
    if user.role is not UserRole.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat super admin uchun",
        )
    return user


def forbid_roles(*roles: UserRole | str):
    """Ko'rsatilgan rollarni RAD etadi (masalan viewer'ga yozishni taqiqlash)."""
    denied: set[str] = {r.value if isinstance(r, UserRole) else str(r) for r in roles}

    async def _checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role.value in denied:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ushbu rol uchun bu amal taqiqlangan (read-only)",
            )
        return user

    return _checker


# Bo'limlarga kirish uchun tayyor dependency'lar (keyingi bosqichda jadvallar shu bilan himoyalanadi)
soc_read = require_role(UserRole.super_admin, UserRole.soc_admin, UserRole.viewer)
soc_write = require_role(UserRole.super_admin, UserRole.soc_admin)
dlp_read = require_role(UserRole.super_admin, UserRole.dlp_admin, UserRole.viewer)
dlp_write = require_role(UserRole.super_admin, UserRole.dlp_admin)


# --- Dinamik jadval bo'lim ruxsatlari (section per-table, DB'dan olinadi) ------


def can_read_section(user: User, section: str) -> bool:
    role = user.role
    if role in (UserRole.super_admin, UserRole.viewer):
        return True
    if section == "shared":
        return True
    if section == "soc":
        return role is UserRole.soc_admin
    if section == "dlp":
        return role is UserRole.dlp_admin
    return False


def can_write_section(user: User, section: str) -> bool:
    role = user.role
    if role is UserRole.viewer:
        return False
    if role is UserRole.super_admin:
        return True
    if section == "shared":
        return role in (UserRole.soc_admin, UserRole.dlp_admin)
    if section == "soc":
        return role is UserRole.soc_admin
    if section == "dlp":
        return role is UserRole.dlp_admin
    return False


def readable_sections(user: User) -> list[str]:
    return [s for s in ("soc", "dlp", "shared") if can_read_section(user, s)]


def writable_sections(user: User) -> list[str]:
    return [s for s in ("soc", "dlp", "shared") if can_write_section(user, s)]


__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "require_super_admin",
    "forbid_roles",
    "soc_read",
    "soc_write",
    "dlp_read",
    "dlp_write",
    "can_read_section",
    "can_write_section",
    "readable_sections",
    "writable_sections",
]
