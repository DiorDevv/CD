"""soc_dlp_admin — bitta foydalanuvchi SOC va DLP bo'limlarining ikkalasiga kiradi."""

import pytest

from tests.conftest import ACTOR_PASSWORD

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _both_user(client) -> dict:
    """Super admin orqali soc_dlp_admin yaratadi, parolini almashtiradi, token qaytaradi."""
    root = await _login(client, "root_admin", ACTOR_PASSWORD)
    r = await client.post(
        "/api/admin/users",
        headers=root,
        json={"username": "both_boss", "temporary_password": "TempPass123", "role": "soc_dlp_admin"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "soc_dlp_admin"

    tmp = await _login(client, "both_boss", "TempPass123")
    r = await client.post(
        "/api/auth/change-password",
        headers=tmp,
        json={"current_password": "TempPass123", "new_password": ACTOR_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return await _login(client, "both_boss", ACTOR_PASSWORD)


async def test_soc_dlp_admin_reads_and_writes_both_sections(client, actors):
    both = await _both_user(client)
    root = await _login(client, "root_admin", ACTOR_PASSWORD)

    # ikkala bo'limda + umumiyda jadval yarata oladi
    tids = {}
    for section in ("soc", "dlp", "shared"):
        r = await client.post(
            "/api/tables",
            headers=both,
            json={"section": section, "name": f"{section} jadval",
                  "columns": [{"label": "Izoh", "type": "text"}]},
        )
        assert r.status_code == 201, r.text
        tids[section] = r.json()

    # qator qo'shadi (yozish) va ro'yxatda hammasini ko'radi (o'qish)
    for t in tids.values():
        key = t["columns"][0]["key"]
        r = await client.post(f"/api/tables/{t['id']}/rows", headers=both, json={"data": {key: "x"}})
        assert r.status_code == 201, r.text
    listed = (await client.get("/api/tables", headers=both)).json()
    assert {t["section"] for t in listed["items"]} == {"soc", "dlp", "shared"}

    # super admin yaratgan DLP jadvalini ham ko'radi
    r = await client.post("/api/tables", headers=root, json={"section": "dlp", "name": "Root DLP"})
    assert (await client.get(f"/api/tables/{r.json()['id']}", headers=both)).status_code == 200

    # bo'lim panellari va placeholder endpoint'lar
    for section in ("soc", "dlp"):
        assert (await client.get(f"/api/sections/{section}/summary", headers=both)).status_code == 200
        r = await client.post(f"/api/sections/{section}/todos", headers=both,
                              json={"scope": "shared", "text": "ish"})
        assert r.status_code == 201, r.text
        assert (await client.post(f"/api/{section}/overview", headers=both)).status_code == 200

    # lekin super admin emas — admin panelga kira olmaydi, jadvalni butunlay o'chira olmaydi
    assert (await client.get("/api/admin/users", headers=both)).status_code == 403
    assert (await client.delete(f"/api/tables/{tids['soc']['id']}", headers=both)).status_code == 403


async def test_single_section_admins_still_isolated(client, actors):
    """Yangi rol qo'shilishi soc_admin/dlp_admin izolyatsiyasini buzmasligi kerak."""
    both = await _both_user(client)
    soc = await _login(client, "soc_boss", ACTOR_PASSWORD)
    dlp = await _login(client, "dlp_boss", ACTOR_PASSWORD)

    r = await client.post("/api/tables", headers=both, json={"section": "dlp", "name": "Faqat DLP"})
    dlp_tid = r.json()["id"]
    r = await client.post("/api/tables", headers=both, json={"section": "soc", "name": "Faqat SOC"})
    soc_tid = r.json()["id"]

    assert (await client.get(f"/api/tables/{dlp_tid}", headers=soc)).status_code == 404
    assert (await client.get(f"/api/tables/{soc_tid}", headers=dlp)).status_code == 404
    assert (await client.get("/api/sections/dlp/summary", headers=soc)).status_code == 404
    assert (await client.get("/api/sections/soc/summary", headers=dlp)).status_code == 404
