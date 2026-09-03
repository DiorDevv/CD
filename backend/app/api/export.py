"""Jadval eksporti / yuklab olish — sinxron + fon job + vaqtli ulashish havolasi."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_read_section, can_write_section, get_current_active_user
from app.api.tables import _guard_read, _load_table
from app.core.audit import write_audit
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.export_job import ExportFormat, ExportJob, ExportJobStatus
from app.models.user import User
from app.schemas.export import ExportJobOut, ShareLinkOut
from app.schemas.user import MessageOut
from app.services import export_job_service, export_service
from app.config import settings

router = APIRouter(tags=["export"])


# --- Sinxron eksport (kichik jadval uchun) --------------------------------


@router.get("/tables/{table_id}/export")
async def export_table_now(
    table_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
    fmt: ExportFormat = Query(default=ExportFormat.csv, alias="format"),
    q: str | None = Query(default=None, max_length=200),
    sort: str | None = Query(default=None, max_length=80),
) -> Response:
    table = await _load_table(db, table_id)
    _guard_read(user, table)
    if fmt is ExportFormat.xlsx:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "xlsx faqat fon job orqali: POST /tables/{id}/export/jobs",
        )

    columns = sorted(table.columns, key=lambda c: c.position)
    rows = await export_service.fetch_rows(db, table, q=q, sort=sort, limit=settings.EXPORT_MAX_ROWS)
    usernames = await export_service.usernames_for(db, rows, columns)
    data = export_service.SERIALIZERS[fmt.value](columns, rows, usernames)

    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in table.name).strip("-").lower()
    filename = f"{safe or 'jadval'}.{fmt.value}"

    await write_audit(
        db,
        action=AuditAction.EXPORT_CREATED,
        user_id=user.id,
        details={"table_id": str(table.id), "format": fmt.value, "mode": "sync", "rows": len(rows)},
        request=request,
    )
    await db.commit()

    return Response(
        content=data,
        media_type=export_service.MEDIA_TYPES[fmt.value],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Fon job ---------------------------------------------------------------


@router.post(
    "/tables/{table_id}/export/jobs",
    response_model=ExportJobOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_export_job(
    table_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
    fmt: ExportFormat = Query(default=ExportFormat.csv, alias="format"),
    q: str | None = Query(default=None, max_length=200),
    sort: str | None = Query(default=None, max_length=80),
) -> ExportJobOut:
    table = await _load_table(db, table_id)
    _guard_read(user, table)

    if await export_job_service.count_active(db) >= settings.EXPORT_JOB_MAX_CONCURRENT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Juda ko'p eksport ishlamoqda. Biri tugashini kuting.",
        )

    job = await export_job_service.create_job(
        db, table=table, fmt=fmt, q=q, sort=sort, user_id=user.id, request=request
    )
    export_job_service.start(job.id)
    return ExportJobOut(**export_job_service.to_out(job))


@router.get("/tables/{table_id}/export/jobs", response_model=list[ExportJobOut])
async def list_export_jobs(
    table_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[ExportJobOut]:
    table = await _load_table(db, table_id)
    _guard_read(user, table)
    jobs = await export_job_service.list_for_table(db, table.id)
    return [ExportJobOut(**export_job_service.to_out(j)) for j in jobs]


# --- Job amallari (job_id bo'yicha) --------------------------------------


async def _job_for_read(db: AsyncSession, job_id: uuid.UUID, user: User) -> ExportJob:
    job = await export_job_service.get(db, job_id)
    if job is None or not can_read_section(user, job.section):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eksport topilmadi")
    return job


async def _job_for_write(db: AsyncSession, job_id: uuid.UUID, user: User) -> ExportJob:
    job = await export_job_service.get(db, job_id)
    if job is None or not can_read_section(user, job.section):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eksport topilmadi")
    if not can_write_section(user, job.section):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu bo'lim uchun ruxsat yo'q")
    return job


@router.get("/exports/{job_id}", response_model=ExportJobOut)
async def get_export_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ExportJobOut:
    job = await _job_for_read(db, job_id, user)
    return ExportJobOut(**export_job_service.to_out(job))


@router.post("/exports/{job_id}/cancel", response_model=ExportJobOut)
async def cancel_export_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ExportJobOut:
    job = await _job_for_write(db, job_id, user)
    if job.status not in (ExportJobStatus.pending, ExportJobStatus.running):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Eksport allaqachon tugagan (holat: {job.status.value})",
        )
    export_job_service.request_cancel(job.id)
    await write_audit(
        db,
        action=AuditAction.EXPORT_CANCELLED,
        user_id=user.id,
        details={"job_id": str(job.id)},
        request=request,
    )
    await db.commit()
    await db.refresh(job)
    return ExportJobOut(**export_job_service.to_out(job))


@router.get("/exports/{job_id}/download")
async def download_export_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> FileResponse:
    job = await _job_for_read(db, job_id, user)
    if job.status is not ExportJobStatus.done or not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Eksport tayyor emas (holat: {job.status.value})"
        )
    await export_job_service.record_download(db, job, user.id, request=request)
    return FileResponse(
        job.file_path,
        media_type=export_service.MEDIA_TYPES[job.format.value],
        filename=job.file_name or f"{job.id}.{job.format.value}",
    )


@router.post("/exports/{job_id}/share", response_model=ShareLinkOut)
async def share_export_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ShareLinkOut:
    job = await _job_for_write(db, job_id, user)
    if job.status is not ExportJobStatus.done or not job.file_path:
        raise HTTPException(status.HTTP_409_CONFLICT, "Eksport hali tayyor emas")
    raw = await export_job_service.create_share_link(db, job, user.id, request=request)
    await db.refresh(job)
    base = str(request.base_url).rstrip("/")
    return ShareLinkOut(
        job_id=job.id,
        token=raw,
        url=f"{base}/api/exports/{job.id}/shared?token={raw}",
        expires_at=job.share_expires_at,
    )


@router.post("/exports/{job_id}/share/revoke", response_model=MessageOut)
async def revoke_export_share(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MessageOut:
    job = await _job_for_write(db, job_id, user)
    await export_job_service.revoke_share(db, job, user.id, request=request)
    return MessageOut(detail="Ulashish havolasi bekor qilindi")


@router.get("/exports/{job_id}/shared")
async def download_shared_export(
    job_id: uuid.UUID,
    token: str = Query(..., min_length=10, max_length=200),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Ataylab autentifikatsiyasiz — ulashish havolasining butun mohiyati
    tizimga kirmasdan yuklab olish. Token (256 bit, faqat hash saqlanadi)
    yagona kalit."""
    job = await export_job_service.verify_share_token(db, job_id, token)
    if job is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Havola yaroqsiz, muddati o'tgan yoki bekor qilingan"
        )
    if job.status is not ExportJobStatus.done or not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(status.HTTP_409_CONFLICT, "Eksport tayyor emas")
    await export_job_service.record_download(db, job, job.share_created_by, via_share=True)
    return FileResponse(
        job.file_path,
        media_type=export_service.MEDIA_TYPES[job.format.value],
        filename=job.file_name or f"{job.id}.{job.format.value}",
    )
