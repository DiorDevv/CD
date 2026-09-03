"""Super admin seed skripti.

Foydalanish:
    python -m scripts.seed_superadmin

Xatti-harakat:
  * .env dan SUPERADMIN_USERNAME / SUPERADMIN_PASSWORD o'qiladi
  * Agar DB'da super_admin roli allaqachon MAVJUD bo'lsa — hech narsa qilmaydi
    (xavfsizlik: mavjud super admin qayta yozilmasin / dublikat bo'lmasin)
  * Aks holda super admin yaratadi (must_change_password=True)
"""

import asyncio
import sys

from sqlalchemy import select

from app.config import settings
from app.core.passwords import validate_password_strength
from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole


async def seed() -> int:
    if not settings.SUPERADMIN_USERNAME or not settings.SUPERADMIN_PASSWORD:
        print("XATO: SUPERADMIN_USERNAME va SUPERADMIN_PASSWORD .env'da to'ldirilishi shart.")
        return 2

    try:
        validate_password_strength(
            settings.SUPERADMIN_PASSWORD, username=settings.SUPERADMIN_USERNAME
        )
    except ValueError as exc:
        print(f"XATO: SUPERADMIN_PASSWORD parol siyosatiga mos emas — {exc}")
        return 4

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(User).where(User.role == UserRole.super_admin)
        )
        if existing.scalar_one_or_none() is not None:
            print("Super admin allaqachon mavjud — hech narsa qilinmadi.")
            return 0

        clash = await db.execute(
            select(User.id).where(User.username == settings.SUPERADMIN_USERNAME)
        )
        if clash.scalar_one_or_none() is not None:
            print(
                f"XATO: '{settings.SUPERADMIN_USERNAME}' username band, lekin super_admin emas."
            )
            return 3

        user = User(
            username=settings.SUPERADMIN_USERNAME,
            hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
            role=UserRole.super_admin,
            is_active=True,
            # Seed parol .env'da ochiq turgani uchun birinchi login'da almashtirilsin
            must_change_password=True,
        )
        db.add(user)
        await db.commit()
        print(
            f"Super admin yaratildi: username='{settings.SUPERADMIN_USERNAME}'. "
            "Birinchi login'da parolni o'zgartirish talab qilinadi."
        )
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(seed()))
