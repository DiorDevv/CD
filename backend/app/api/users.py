from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.dynamic import DirectoryUser
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> UserOut:
    """Joriy foydalanuvchi ma'lumotlari.

    `must_change_password=True` bo'lsa ham ishlaydi — frontend shu asosida
    foydalanuvchini /change-password sahifasiga yo'naltiradi.
    """
    return UserOut.model_validate(user)


@router.get("/directory", response_model=list[DirectoryUser])
async def user_directory(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[DirectoryUser]:
    """Foydalanuvchilar ro'yxati (id, username, role) — dinamik jadvaldagi
    `user` turidagi ustunlarni to'ldirish/ko'rsatish uchun.

    Kam maxfiylikdagi ma'lumot (ichki tizim), shuning uchun har qanday faol
    autentifikatsiyalangan foydalanuvchiga ochiq.
    """
    res = await db.execute(select(User).order_by(User.username))
    return [DirectoryUser.model_validate(u) for u in res.scalars().all()]
