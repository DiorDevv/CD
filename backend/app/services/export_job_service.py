"""Eksport job'lari — yaratish, fon'da ishlatish, holat, yuklab olish, ulashish.

Fon vazifasi (`run_job`) o'z DB sessiyasini ochadi (so'rov sessiyasidan alohida),
natijani `settings.EXPORT_DIR` ga fayl qilib yozadi, SHA-256 hisoblaydi.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.audit import write_audit
from app.database import AsyncSessionLocal
from app.models.audit_log import AuditAction
from app.models.dynamic import DynamicTable
from app.models.export_job import ExportFormat, ExportJob, ExportJobStatus
from app.services import export_service

logger = logging.getLogger("app.export")

# job_id -> asyncio.Task  (fon vazifalarini kuzatish)
_tasks: dict[str, asyncio.Task] = {}
# bekor qilish so'ralgan job id'lari (kooperativ)
_cancel_requested: set[str] = set()

_ACTIVE = (ExportJobStatus.pending, ExportJobStatus.running)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ext(fmt: ExportFormat) -> str:
    return fmt.value


def result_filename(job: ExportJob, table_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in table_name).strip("-").lower()
    stamp = job.created_at.strftime("%Y%m%d-%H%M") if job.created_at else "export"
    return f"{safe or 'jadval'}-{stamp}.{_ext(job.format)}"


async def count_active(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(ExportJob).where(ExportJob.status.in_(_ACTIVE))
        )
    ).scalar_one()


async def create_job(
    db: AsyncSession,
    *,
    table: DynamicTable,
    fmt: ExportFormat,
    q: str | None,
    sort: str | None,
    user_id: uuid.UUID,
    request=None,
) -> ExportJob:
    job = ExportJob(
        table_id=table.id,
        section=table.section.value,
        status=ExportJobStatus.pending,
        format=fmt,
        filters={"q": q or None, "sort": sort or None},
        file_name=None,
        created_by=user_id,
    )
    db.add(job)
    await db.flush()
    await write_audit(
        db,
        action=AuditAction.EXPORT_CREATED,
        user_id=user_id,
        details={
            "job_id": str(job.id),
            "table_id": str(table.id),
            "format": fmt.value,
            "mode": "job",
        },
        request=request,
    )
    await db.commit()
    await db.refresh(job)
    return job


def start(job_id: uuid.UUID) -> None:
    jid = str(job_id)
    task = asyncio.create_task(run_job(jid))
    _tasks[jid] = task
    task.add_done_callback(lambda _t: _tasks.pop(jid, None))


async def run_job(job_id: str) -> None:
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    async with AsyncSessionLocal() as db:
        job = await db.get(ExportJob, uuid.UUID(job_id))
        if job is None or job.status is not ExportJobStatus.pending:
            return
        if job_id in _cancel_requested:
            _cancel_requested.discard(job_id)
            job.status = ExportJobStatus.cancelled
            job.completed_at = _now()
            await db.commit()
            return

        job.status = ExportJobStatus.running
        await db.commit()

        try:
            table = (
                await db.execute(
                    select(DynamicTable)
                    .where(DynamicTable.id == job.table_id)
                    .options(selectinload(DynamicTable.columns))
                )
            ).scalar_one_or_none()
            if table is None:
                raise RuntimeError("Jadval topilmadi")

            columns = sorted(table.columns, key=lambda c: c.position)
            rows = await export_service.fetch_rows(
                db,
                table,
                q=job.filters.get("q"),
                sort=job.filters.get("sort"),
                limit=settings.EXPORT_MAX_ROWS,
            )
            if job_id in _cancel_requested:
                raise _Cancelled()

            usernames = await export_service.usernames_for(db, rows, columns)
            data = export_service.SERIALIZERS[job.format.value](columns, rows, usernames)

            fname = result_filename(job, table.name)
            path = os.path.join(settings.EXPORT_DIR, f"{job.id}.{_ext(job.format)}")
            with open(path, "wb") as fh:
                fh.write(data)

            job.file_path = path
            job.file_name = fname
            job.row_count = len(rows)
            job.file_size_bytes = len(data)
            job.checksum_sha256 = hashlib.sha256(data).hexdigest()
            job.status = ExportJobStatus.done
            job.completed_at = _now()
            await db.commit()
            logger.info("export job %s done: %s qator, %s bayt", job.id, len(rows), len(data))
        except _Cancelled:
            _cancel_requested.discard(job_id)
            job.status = ExportJobStatus.cancelled
            job.completed_at = _now()
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - job hech qachon crash qilmasin
            logger.exception("export job %s failed", job.id)
            job.status = ExportJobStatus.failed
            job.error_message = str(exc)[:2000]
            job.completed_at = _now()
            await db.commit()


class _Cancelled(Exception):
    pass


async def list_for_table(db: AsyncSession, table_id: uuid.UUID, *, limit: int = 30) -> list[ExportJob]:
    res = await db.execute(
        select(ExportJob)
        .where(ExportJob.table_id == table_id)
        .order_by(ExportJob.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def get(db: AsyncSession, job_id: uuid.UUID) -> ExportJob | None:
    return await db.get(ExportJob, job_id)


def request_cancel(job_id: uuid.UUID) -> None:
    _cancel_requested.add(str(job_id))
    task = _tasks.get(str(job_id))
    if task is not None:
        task.cancel()


async def record_download(
    db: AsyncSession, job: ExportJob, user_id: uuid.UUID | None, *, via_share: bool = False, request=None
) -> None:
    if job.downloaded_at is None:
        job.downloaded_at = _now()
    job.download_count += 1
    await write_audit(
        db,
        action=AuditAction.EXPORT_DOWNLOADED,
        user_id=user_id,
        details={"job_id": str(job.id), "via_share": via_share},
        request=request,
    )
    await db.commit()


async def create_share_link(
    db: AsyncSession, job: ExportJob, user_id: uuid.UUID, *, request=None
) -> str:
    raw = secrets.token_urlsafe(32)
    job.share_token_hash = _hash_token(raw)
    job.share_expires_at = _now() + timedelta(hours=settings.EXPORT_SHARE_TTL_HOURS)
    job.share_created_by = user_id
    await write_audit(
        db,
        action=AuditAction.EXPORT_SHARED,
        user_id=user_id,
        details={"job_id": str(job.id), "expires_at": job.share_expires_at.isoformat()},
        request=request,
    )
    await db.commit()
    return raw


async def revoke_share(db: AsyncSession, job: ExportJob, user_id: uuid.UUID, *, request=None) -> None:
    job.share_token_hash = None
    job.share_expires_at = None
    await write_audit(
        db,
        action=AuditAction.EXPORT_SHARE_REVOKED,
        user_id=user_id,
        details={"job_id": str(job.id)},
        request=request,
    )
    await db.commit()


async def verify_share_token(db: AsyncSession, job_id: uuid.UUID, raw_token: str) -> ExportJob | None:
    job = await db.get(ExportJob, job_id)
    if job is None or not job.share_token_hash:
        return None
    if not secrets.compare_digest(job.share_token_hash, _hash_token(raw_token)):
        return None
    exp = job.share_expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp is None or exp < _now():
        return None
    return job


async def cleanup_old(db: AsyncSession) -> int:
    """Muddati o'tgan tayyor eksport fayllari va yozuvlarini o'chiradi."""
    keep_days = settings.EXPORT_KEEP_DAYS
    if keep_days <= 0:
        return 0
    cutoff = _now() - timedelta(days=keep_days)
    old = (
        await db.execute(select(ExportJob).where(ExportJob.created_at < cutoff))
    ).scalars().all()
    n = 0
    for job in old:
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except OSError:
                pass
        await db.delete(job)
        n += 1
    if n:
        await db.commit()
    return n


def to_out(job: ExportJob) -> dict:
    return {
        "id": job.id,
        "table_id": job.table_id,
        "status": job.status.value,
        "format": job.format.value,
        "filters": job.filters or {},
        "file_name": job.file_name,
        "row_count": job.row_count,
        "file_size_bytes": job.file_size_bytes,
        "checksum_sha256": job.checksum_sha256,
        "error_message": job.error_message,
        "has_share_link": job.share_token_hash is not None,
        "share_expires_at": job.share_expires_at,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "downloaded_at": job.downloaded_at,
        "download_count": job.download_count,
    }
