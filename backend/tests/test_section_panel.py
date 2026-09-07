"""SOC/DLP bo'lim paneli — topshiriqlar (personal/shared) + yig'ma statistika."""

import pytest

from tests.conftest import ACTOR_PASSWORD

pytestmark = pytest.mark.asyncio


async def _tok(client, username: str) -> str:
    r = await client.post(
        "/api/auth/login", json={"username": username, "password": ACTOR_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# --- Topshiriqlar ---------------------------------------------------------------


async def test_personal_todos_are_private(client, actors):
    soc = await _tok(client, "soc_boss")
    root = await _tok(client, "root_admin")

    r = await client.post("/api/sections/soc/todos", headers=_h(soc),
                          json={"scope": "personal", "text": "Mening ishim"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    # egasi ko'radi
    mine = (await client.get("/api/sections/soc/todos", headers=_h(soc),
                             params={"scope": "personal"})).json()
    assert [t["id"] for t in mine] == [tid]

    # boshqa foydalanuvchi (super admin ham) — ko'rmaydi, tahrirlay olmaydi
    other = (await client.get("/api/sections/soc/todos", headers=_h(root),
                              params={"scope": "personal"})).json()
    assert other == []
    assert (await client.patch(f"/api/sections/soc/todos/{tid}", headers=_h(root),
                               json={"is_done": True})).status_code == 404


async def test_shared_todos_need_write_permission(client, actors):
    soc = await _tok(client, "soc_boss")
    viewer = await _tok(client, "watcher")
    dlp = await _tok(client, "dlp_boss")

    # viewer — shared qo'sha olmaydi
    assert (await client.post("/api/sections/soc/todos", headers=_h(viewer),
                              json={"scope": "shared", "text": "x"})).status_code == 403
    # dlp_admin — SOC bo'limiga umuman kira olmaydi
    assert (await client.get("/api/sections/soc/todos", headers=_h(dlp),
                             params={"scope": "shared"})).status_code == 404

    r = await client.post("/api/sections/soc/todos", headers=_h(soc),
                          json={"scope": "shared", "text": "Bo'lim ishi", "due_date": "2026-09-20"})
    assert r.status_code == 201
    tid = r.json()["id"]

    # viewer shared'ni ko'radi (o'qish), lekin o'chira olmaydi
    seen = (await client.get("/api/sections/soc/todos", headers=_h(viewer),
                             params={"scope": "shared"})).json()
    assert [t["id"] for t in seen] == [tid]
    assert (await client.delete(f"/api/sections/soc/todos/{tid}", headers=_h(viewer))).status_code == 403

    # egasi (soc_boss) belgilaydi -> done, keyin muddatni tozalaydi
    up = await client.patch(f"/api/sections/soc/todos/{tid}", headers=_h(soc),
                            json={"is_done": True, "due_date": None})
    assert up.status_code == 200
    assert up.json()["is_done"] is True and up.json()["done_at"] is not None
    assert up.json()["due_date"] is None

    # done'lar ro'yxat oxirida
    lst = (await client.get("/api/sections/soc/todos", headers=_h(soc),
                            params={"scope": "shared"})).json()
    assert lst[-1]["id"] == tid

    assert (await client.delete(f"/api/sections/soc/todos/{tid}", headers=_h(soc))).status_code == 200


async def test_invalid_section_404(client, actors):
    root = await _tok(client, "root_admin")
    assert (await client.get("/api/sections/shared/summary", headers=_h(root))).status_code == 404
    assert (await client.get("/api/sections/xxx/summary", headers=_h(root))).status_code == 404


# --- Yig'ma statistika ------------------------------------------------------


async def test_section_summary(client, actors):
    root = await _tok(client, "root_admin")
    t = (await client.post("/api/tables", headers=_h(root), json={
        "section": "soc", "name": "Hodisalar",
        "columns": [
            {"label": "Ism", "type": "text"},
            {"label": "Daraja", "type": "select", "config": {"options": [
                {"value": "low", "label": "Past"}, {"value": "high", "label": "Yuqori"}]}},
        ],
    })).json()
    tid = t["id"]
    k_name = next(c["key"] for c in t["columns"] if c["label"] == "Ism")
    k_lvl = next(c["key"] for c in t["columns"] if c["label"] == "Daraja")

    ids = []
    for name, lvl in [("A", "high"), ("B", "high"), ("C", "low")]:
        r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                              json={"data": {k_name: name, k_lvl: lvl}})
        ids.append(r.json()["id"])
    await client.patch(f"/api/tables/{tid}/rows/{ids[0]}", headers=_h(root),
                       json={"data": {"__done": True}})

    s = (await client.get("/api/sections/soc/summary", headers=_h(root))).json()
    assert s["section"] == "soc"
    assert s["totals"]["tables"] == 1
    assert s["totals"]["rows"] == 3
    assert s["totals"]["done"] == 1
    assert s["totals"]["open"] == 2
    assert s["totals"]["added_7d"] == 3

    tbl = s["tables"][0]
    assert tbl["row_count"] == 3 and tbl["done_count"] == 1
    assert tbl["breakdown_label"] == "Daraja"
    bd = {e["value"]: e["count"] for e in tbl["breakdown"]}
    assert bd == {"high": 2, "low": 1}

    assert len(s["recent"]) >= 3
    assert s["recent"][0]["table_name"] == "Hodisalar"
    assert s["recent"][0]["changed_by_name"] == "root_admin"

    assert len(s["trend"]) == 14
    assert sum(p["count"] for p in s["trend"]) == 3

    # dlp_admin SOC summary'ga kira olmaydi
    dlp = await _tok(client, "dlp_boss")
    assert (await client.get("/api/sections/soc/summary", headers=_h(dlp))).status_code == 404
