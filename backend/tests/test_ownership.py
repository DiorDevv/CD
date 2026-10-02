"""Mualliflik qoidasi: super admin hammasini qiladi; boshqa adminlar faqat o'zi yozgan qatorni,
o'zi yaratgan jadval tuzilishini va o'zi yozgan umumiy topshiriqni o'zgartiradi."""

import pytest
from sqlalchemy import update

from app.core.security import hash_password
from app.models.dynamic import DynamicRow
from app.models.user import User, UserRole
from tests.conftest import ACTOR_PASSWORD, TestSession

pytestmark = pytest.mark.asyncio


async def _tok(client, username: str) -> dict:
    r = await client.post(
        "/api/auth/login", json={"username": username, "password": ACTOR_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _users(client) -> tuple[dict, dict, dict]:
    """(muallif soc_admin, ikkinchi soc_admin, super admin) tokenlari."""
    async with TestSession() as db:
        db.add(User(username="soc_mate", hashed_password=hash_password(ACTOR_PASSWORD),
                    role=UserRole.soc_admin, is_active=True, must_change_password=False))
        await db.commit()
    return (
        await _tok(client, "soc_boss"),
        await _tok(client, "soc_mate"),
        await _tok(client, "root_admin"),
    )


async def _table_with_row(client, owner: dict) -> tuple[dict, str, dict]:
    t = (await client.post("/api/tables", headers=owner, json={
        "section": "soc", "name": "Hodisalar", "columns": [{"label": "Izoh", "type": "text"}],
    })).json()
    key = t["columns"][0]["key"]
    row = await client.post(
        f"/api/tables/{t['id']}/rows", headers=owner, json={"data": {key: "egasi"}}
    )
    return t, key, row.json()


async def test_other_admin_cannot_modify_row_but_can_add_own(client, actors):
    owner, mate, _root = await _users(client)
    t, key, row = await _table_with_row(client, owner)
    base = f"/api/tables/{t['id']}/rows"
    url = f"{base}/{row['id']}"

    # Boshqa admin: ko'radi, lekin o'zgartira / "bajarildi" qila / o'chira / tiklay olmaydi
    assert (await client.get(base, headers=mate)).status_code == 200
    r = await client.patch(url, headers=mate, json={"data": {key: "buzdim"}})
    assert r.status_code == 403 and "faqat uni yozgan" in r.json()["detail"]
    r = await client.patch(url, headers=mate, json={"data": {"__done": True}})
    assert r.status_code == 403
    assert (await client.delete(url, headers=mate)).status_code == 403
    rev = (await client.get(f"{url}/revisions", headers=mate)).json()[0]
    r = await client.post(f"{url}/revisions/{rev['id']}/restore", headers=mate)
    assert r.status_code == 403

    # Ma'lumot o'zgarmagan
    items = (await client.get(base, headers=owner)).json()["items"]
    assert items[0]["data"][key] == "egasi" and not items[0]["data"].get("__done")

    # O'z qatorini qo'shadi va uni o'zgartiradi; muallif esa uning qatoriga tega olmaydi
    mine = (await client.post(base, headers=mate, json={"data": {key: "meniki"}})).json()
    r = await client.patch(f"{base}/{mine['id']}", headers=mate, json={"data": {"__done": True}})
    assert r.status_code == 200, r.text
    r = await client.patch(f"{base}/{mine['id']}", headers=owner, json={"data": {key: "x"}})
    assert r.status_code == 403
    assert (await client.delete(f"{base}/{mine['id']}", headers=mate)).status_code == 200


async def test_owner_and_superadmin_can_modify(client, actors):
    owner, _mate, root = await _users(client)
    t, key, row = await _table_with_row(client, owner)
    url = f"/api/tables/{t['id']}/rows/{row['id']}"

    r = await client.patch(url, headers=owner, json={"data": {key: "yangi"}})
    assert r.status_code == 200, r.text
    r = await client.patch(url, headers=root, json={"data": {"__done": True}})
    assert r.status_code == 200, r.text
    first = (await client.get(f"{url}/revisions", headers=root)).json()[-1]
    r = await client.post(f"{url}/revisions/{first['id']}/restore", headers=root)
    assert r.status_code == 200, r.text
    assert (await client.delete(url, headers=root)).status_code == 200


async def test_table_structure_only_creator_or_superadmin(client, actors):
    owner, mate, root = await _users(client)
    t, key, _row = await _table_with_row(client, owner)
    tid, cid = t["id"], t["columns"][0]["id"]
    tbl, cols = f"/api/tables/{tid}", f"/api/tables/{tid}/columns"

    # Boshqa admin jadval tuzilishiga tega olmaydi: ustunlar, tartib, nom, arxiv
    new_col = {"label": "Yangi", "type": "text"}
    assert (await client.post(cols, headers=mate, json=new_col)).status_code == 403
    r = await client.patch(f"{cols}/{cid}", headers=mate, json={"label": "Boshqa"})
    assert r.status_code == 403
    assert (await client.delete(f"{cols}/{cid}", headers=mate)).status_code == 403
    order = {"items": [{"id": cid, "position": 3}]}
    assert (await client.post(f"{cols}/reorder", headers=mate, json=order)).status_code == 403
    assert (await client.patch(tbl, headers=mate, json={"name": "X"})).status_code == 403
    assert (await client.patch(tbl, headers=mate, json={"is_archived": True})).status_code == 403
    items = (await client.get(f"{tbl}/rows", headers=owner)).json()["items"]
    assert items[0]["data"][key] == "egasi"   # ustun o'chmagan — qiymatlar joyida

    # Yaratuvchi va super admin — mumkin
    assert (await client.post(cols, headers=owner, json=new_col)).status_code == 201
    assert (await client.patch(tbl, headers=root, json={"name": "Hodisalar 2"})).status_code == 200
    assert (await client.patch(tbl, headers=owner, json={"is_archived": True})).status_code == 200


async def test_legacy_row_without_author_only_superadmin(client, actors):
    owner, _mate, root = await _users(client)
    t, key, row = await _table_with_row(client, owner)
    async with TestSession() as db:
        await db.execute(
            update(DynamicRow).where(DynamicRow.id == row["id"]).values(created_by=None)
        )
        await db.commit()
    url = f"/api/tables/{t['id']}/rows/{row['id']}"
    assert (await client.patch(url, headers=owner, json={"data": {key: "x"}})).status_code == 403
    assert (await client.patch(url, headers=root, json={"data": {key: "x"}})).status_code == 200


async def test_shared_todo_only_author_or_superadmin(client, actors):
    owner, mate, root = await _users(client)
    todo = (await client.post("/api/sections/soc/todos", headers=owner,
                              json={"scope": "shared", "text": "Loglarni tekshirish"})).json()
    url = f"/api/sections/soc/todos/{todo['id']}"

    # Boshqa admin ko'radi, lekin matn, "bajarildi" va o'chirish — yo'q
    listed = (await client.get("/api/sections/soc/todos?scope=shared", headers=mate)).json()
    assert [x["id"] for x in listed] == [todo["id"]]
    assert (await client.patch(url, headers=mate, json={"text": "boshqa"})).status_code == 403
    assert (await client.patch(url, headers=mate, json={"is_done": True})).status_code == 403
    assert (await client.delete(url, headers=mate)).status_code == 403

    assert (await client.patch(url, headers=owner, json={"is_done": True})).status_code == 200
    assert (await client.patch(url, headers=root, json={"text": "Tahrir"})).status_code == 200
    assert (await client.delete(url, headers=root)).status_code == 200
