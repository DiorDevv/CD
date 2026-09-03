import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.audit import write_audit
from app.core.passwords import generate_temp_password
from app.core.security import hash_password
from app.database import get_db
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogOut, AuditLogPage
from app.schemas.user import (
    AdminResetPasswordRequest,
    MessageOut,
    UserCreate,
    UserCreatedOut,
    UserOut,
    UserPage,
)
from app.services.auth_service import revoke_all_refresh_tokens

# Blanket enforcement — require_super_admin endi modul darajasidagi funksiya,
# shuning uchun FastAPI uni bir so'rov davomida faqat BIR marta bajaradi
# (router-level va handler-level ishlatilsa ham).
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_super_admin)],
)


@router.post("/users", response_model=UserCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_super_admin),
) -> UserCreatedOut:
    exists = await db.execute(select(User.id).where(User.username == payload.username))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bunday username allaqachon mavjud"
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.temporary_password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
        created_by=current.id,
    )
    db.add(user)
    await db.flush()

    await write_audit(
        db,
        action=AuditAction.USER_CREATED,
        user_id=current.id,
        details={
            "created_user_id": str(user.id),
            "username": user.username,
            "role": user.role.value,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(user)

    return UserCreatedOut(
        user=UserOut.model_validate(user),
        temporary_password=payload.temporary_password,
    )


@router.get("/users", response_model=UserPage)
async def list_users(
    db: AsyncSession = Depends(get_db),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="username bo'yicha qidiruv"),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserPage:
    conditions = []
    if role is not None:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    if q:
        conditions.append(User.username.ilike(f"%{q}%"))

    base = select(User)
    count_stmt = select(func.count()).select_from(User)
    for c in conditions:
        base = base.where(c)
        count_stmt = count_stmt.where(c)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()

    return UserPage(
        items=[UserOut.model_validate(u) for u in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _get_target(db: AsyncSession, user_id: uuid.UUID, current: User) -> User:
    """Amal bajariladigan foydalanuvchini qaytaradi.

    Boshqa super_adminlarni ham boshqarish mumkin, LEKIN o'z hisobiga nisbatan
    emas. Bu cheklovning o'zi tizimda doim kamida bitta faol super_admin
    qolishini kafolatlaydi (chaqiruvchi har doim faol super_admin).
    """
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Foydalanuvchi topilmadi"
        )
    if target.id == current.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'z hisobingizga nisbatan bu amalni bajarib bo'lmaydi",
        )
    return target


@router.patch("/users/{user_id}/block", response_model=UserOut)
async def block_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_super_admin),
) -> UserOut:
    target = await _get_target(db, user_id, current)
    target.is_active = False
    target.token_version += 1  # mavjud access tokenlarni ham darhol yaroqsiz qiladi
    await revoke_all_refresh_tokens(db, target.id)
    await write_audit(
        db,
        action=AuditAction.USER_BLOCKED,
        user_id=current.id,
        details={"target_user_id": str(target.id), "username": target.username},
        request=request,
    )
    await db.commit()
    await db.refresh(target)
    return UserOut.model_validate(target)


@router.patch("/users/{user_id}/unblock", response_model=UserOut)
async def unblock_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_super_admin),
) -> UserOut:
    target = await _get_target(db, user_id, current)
    target.is_active = True
    target.failed_attempts = 0
    target.locked_until = None
    await write_audit(
        db,
        action=AuditAction.USER_UNBLOCKED,
        user_id=current.id,
        details={"target_user_id": str(target.id), "username": target.username},
        request=request,
    )
    await db.commit()
    await db.refresh(target)
    return UserOut.model_validate(target)


@router.post("/users/{user_id}/reset-password", response_model=UserCreatedOut)
async def reset_user_password(
    user_id: uuid.UUID,
    payload: AdminResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_super_admin),
) -> UserCreatedOut:
    """Super admin foydalanuvchi parolini tiklaydi (parolini unutgan holatlar uchun).

    - yangi vaqtinchalik parol o'rnatiladi (berilmasa — generatsiya qilinadi)
    - `must_change_password=True` -> foydalanuvchi keyingi kirishda almashtiradi
    - qulf va urinishlar hisoblagichi tozalanadi
    - `token_version` oshiriladi + barcha refresh sessiyalar bekor qilinadi
    """
    target = await _get_target(db, user_id, current)

    temp = payload.temporary_password or generate_temp_password()
    target.hashed_password = hash_password(temp)
    target.must_change_password = True
    target.failed_attempts = 0
    target.locked_until = None
    target.token_version += 1
    await revoke_all_refresh_tokens(db, target.id)

    await write_audit(
        db,
        action=AuditAction.PASSWORD_RESET,
        user_id=current.id,
        details={
            "target_user_id": str(target.id),
            "username": target.username,
            "generated": payload.temporary_password is None,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(target)

    return UserCreatedOut(
        user=UserOut.model_validate(target), temporary_password=temp
    )


@router.delete("/users/{user_id}", response_model=MessageOut)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_super_admin),
) -> MessageOut:
    target = await _get_target(db, user_id, current)
    username = target.username
    await write_audit(
        db,
        action=AuditAction.USER_DELETED,
        user_id=current.id,
        details={
            "target_user_id": str(target.id),
            "username": username,
            "role": target.role.value,
        },
        request=request,
    )
    await db.delete(target)
    await db.commit()
    return MessageOut(detail=f"'{username}' o'chirildi")


@router.get("/audit-logs", response_model=AuditLogPage)
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    action: str | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogPage:
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    base = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    for c in conditions:
        base = base.where(c)
        count_stmt = count_stmt.where(c)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()

    return AuditLogPage(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
