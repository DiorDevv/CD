import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditAction(str):
    """Bo'sh bo'lmagan literal qiymatlar — DB'da oddiy string sifatida saqlanadi."""

    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REUSE_DETECTED = "token_reuse_detected"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    USER_CREATED = "user_created"
    USER_BLOCKED = "user_blocked"
    USER_UNBLOCKED = "user_unblocked"
    USER_DELETED = "user_deleted"
    ACCOUNT_LOCKED = "account_locked"

    # Dinamik jadvallar — struktura o'zgarishlari
    TABLE_CREATED = "table_created"
    TABLE_UPDATED = "table_updated"
    TABLE_ARCHIVED = "table_archived"
    TABLE_RESTORED = "table_restored"
    TABLE_DELETED = "table_deleted"
    COLUMN_ADDED = "column_added"
    COLUMN_UPDATED = "column_updated"
    COLUMN_DELETED = "column_deleted"

    # Dinamik jadvallar — eksport / yuklab olish
    EXPORT_CREATED = "export_created"
    EXPORT_DOWNLOADED = "export_downloaded"
    EXPORT_SHARED = "export_shared"
    EXPORT_SHARE_REVOKED = "export_share_revoked"
    EXPORT_CANCELLED = "export_cancelled"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # login_failed holatida user topilmasligi mumkin -> nullable
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
