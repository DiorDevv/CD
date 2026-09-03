import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExportJobOut(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    status: str
    format: str
    filters: dict[str, Any]
    file_name: str | None
    row_count: int | None
    file_size_bytes: int | None
    checksum_sha256: str | None
    error_message: str | None
    has_share_link: bool
    share_expires_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None
    downloaded_at: datetime | None
    download_count: int


class ShareLinkOut(BaseModel):
    job_id: uuid.UUID
    token: str
    url: str
    expires_at: datetime
