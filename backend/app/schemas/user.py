import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.passwords import validate_password_strength
from app.models.user import UserRole

# viewer/admin yaratish mumkin bo'lgan rollar (super_admin bu ro'yxatda YO'Q)
CREATABLE_ROLES = {UserRole.soc_admin, UserRole.dlp_admin, UserRole.viewer}

USERNAME_RE = r"^[a-zA-Z0-9._-]{3,64}$"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    failed_attempts: int
    locked_until: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_RE)
    temporary_password: str = Field(min_length=1, max_length=128)
    role: UserRole

    @model_validator(mode="after")
    def _validate(self) -> "UserCreate":
        if self.role not in CREATABLE_ROLES:
            raise ValueError(
                "Faqat soc_admin, dlp_admin yoki viewer roli yaratilishi mumkin"
            )
        # Vaqtinchalik parol ham to'liq siyosatga bo'ysunadi
        validate_password_strength(self.temporary_password, username=self.username)
        return self


class AdminResetPasswordRequest(BaseModel):
    # Bo'sh qoldirilsa — server kuchli vaqtinchalik parol generatsiya qiladi.
    temporary_password: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _validate(self) -> "AdminResetPasswordRequest":
        if self.temporary_password is not None:
            validate_password_strength(self.temporary_password)
        return self


class UserCreatedOut(BaseModel):
    user: UserOut
    # Super admin ushbu vaqtinchalik parolni foydalanuvchiga uzatadi.
    temporary_password: str


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int


class MessageOut(BaseModel):
    detail: str
