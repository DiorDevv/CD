from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.audit import write_audit
from app.core.passwords import validate_password_strength
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
)
from app.schemas.user import MessageOut, UserOut
from app.services import auth_service
from app.services.auth_service import LoginError

router = APIRouter(prefix="/auth", tags=["auth"])

_ACCESS_TTL = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=settings.COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path=settings.COOKIE_PATH,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        user = await auth_service.authenticate(
            db, username=payload.username, password=payload.password, request=request
        )
    except LoginError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.detail)

    access = create_access_token(
        subject=user.id, role=user.role.value, token_version=user.token_version
    )
    raw_refresh = await auth_service.issue_refresh_token(db, user)
    _set_refresh_cookie(response, raw_refresh)

    return TokenResponse(
        access_token=access,
        expires_in=_ACCESS_TTL,
        must_change_password=user.must_change_password,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token topilmadi"
        )
    try:
        user, new_raw = await auth_service.rotate_refresh_token(db, raw, request=request)
    except LoginError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.detail)

    access = create_access_token(
        subject=user.id, role=user.role.value, token_version=user.token_version
    )
    _set_refresh_cookie(response, new_raw)
    return AccessTokenResponse(access_token=access, expires_in=_ACCESS_TTL)


@router.post("/logout", response_model=MessageOut)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw:
        user_id = await auth_service.revoke_refresh_token(db, raw)
        if user_id:
            await write_audit(
                db, action=AuditAction.LOGOUT, user_id=user_id, request=request, commit=True
            )
    _clear_refresh_cookie(response)
    return MessageOut(detail="Tizimdan chiqildi")


@router.post("/change-password", response_model=MessageOut)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Joriy parol noto'g'ri"
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Yangi parol eskisidan farq qilishi kerak",
        )
    try:
        validate_password_strength(payload.new_password, username=user.username)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    user.failed_attempts = 0
    user.locked_until = None
    # Xavfsizlik shtampini oshiramiz -> mavjud access tokenlar ham darhol yaroqsiz
    user.token_version += 1

    # Barcha eski refresh sessiyalari bekor qilinadi
    await auth_service.revoke_all_refresh_tokens(db, user.id)
    await write_audit(
        db, action=AuditAction.PASSWORD_CHANGED, user_id=user.id, request=request
    )
    await db.commit()

    _clear_refresh_cookie(response)
    return MessageOut(detail="Parol yangilandi. Iltimos qaytadan tizimga kiring")
