"""SOC / DLP bo'limlari uchun PLACEHOLDER endpoint'lar.

Keyingi bosqichda haqiqiy jadval/dashboard endpoint'lari shu yerga qo'shiladi.
Hozircha maqsad — RBAC dependency'lari ishlashini ko'rsatish:
  * viewer  -> faqat GET (read)
  * soc_admin -> DLP'ga umuman kira olmaydi
  * dlp_admin -> SOC'ga umuman kira olmaydi
"""

from fastapi import APIRouter, Depends

from app.api.deps import dlp_read, dlp_write, soc_read, soc_write
from app.models.user import User

soc_router = APIRouter(prefix="/soc", tags=["soc"])
dlp_router = APIRouter(prefix="/dlp", tags=["dlp"])


@soc_router.get("/overview")
async def soc_overview(user: User = Depends(soc_read)) -> dict:
    return {"section": "SOC", "message": "SOC bo'limi (placeholder)", "role": user.role.value}


@soc_router.post("/overview")
async def soc_write_demo(user: User = Depends(soc_write)) -> dict:
    return {"section": "SOC", "message": "yozildi (placeholder)", "role": user.role.value}


@dlp_router.get("/overview")
async def dlp_overview(user: User = Depends(dlp_read)) -> dict:
    return {"section": "DLP", "message": "DLP bo'limi (placeholder)", "role": user.role.value}


@dlp_router.post("/overview")
async def dlp_write_demo(user: User = Depends(dlp_write)) -> dict:
    return {"section": "DLP", "message": "yozildi (placeholder)", "role": user.role.value}
