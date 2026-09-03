"""Dinamik jadvallar (jadval/ustun/qator) uchun integratsion testlar."""

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


async def _mk_table(client, tok, section="soc", name="Hodisalar", columns=None):
    return await client.post(
        "/api/tables",
        headers=_h(tok),
        json={"section": section, "name": name, "columns": columns or []},
    )


# --- Ruxsatlar ---------------------------------------------------------------


async def test_create_table_permissions(client, actors):
    soc = await _tok(client, "soc_boss")
    dlp = await _tok(client, "dlp_boss")
    viewer = await _tok(client, "watcher")
    root = await _tok(client, "root_admin")

    assert (await _mk_table(client, soc, "soc", "SOC jadval")).status_code == 201
    assert (await _mk_table(client, soc, "dlp", "no")).status_code == 403
    assert (await _mk_table(client, soc, "shared", "Umumiy")).status_code == 201
    assert (await _mk_table(client, dlp, "dlp", "DLP jadval")).status_code == 201
    assert (await _mk_table(client, dlp, "soc", "no")).status_code == 403
    assert (await _mk_table(client, viewer, "soc", "no")).status_code == 403
    assert (await _mk_table(client, root, "dlp", "Root DLP")).status_code == 201


async def test_column_config_validation(client, actors):
    root = await _tok(client, "root_admin")
    # select ustuni variantsiz -> 422
    r = await _mk_table(
        client, root, "soc", "T1",
        columns=[{"label": "Holat", "type": "select", "config": {}}],
    )
    assert r.status_code == 422

    # number min > max -> 422
    r = await _mk_table(
        client, root, "soc", "T2",
        columns=[{"label": "Ball", "type": "number", "config": {"min": 10, "max": 1}}],
    )
    assert r.status_code == 422

    # to'g'ri
    r = await _mk_table(
        client, root, "soc", "T3",
        columns=[
            {"label": "Sarlavha", "type": "text", "config": {"required": True}},
            {"label": "Daraja", "type": "select", "config": {
                "options": [{"value": "low", "label": "Past"}, {"value": "high", "label": "Yuqori"}]
            }},
            {"label": "Ball", "type": "number", "config": {"min": 0, "max": 100}},
            {"label": "Ochiq", "type": "boolean"},
        ],
    )
    assert r.status_code == 201
    assert len(r.json()["columns"]) == 4


async def test_row_crud_and_validation(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "Hodisalar", columns=[
        {"label": "Sarlavha", "type": "text", "config": {"required": True}},
        {"label": "Daraja", "type": "select", "config": {
            "options": [{"value": "low", "label": "Past"}, {"value": "high", "label": "Yuqori"}]}},
        {"label": "Mas'ul", "type": "user"},
    ])).json()
    tid = t["id"]
    k_title = next(c["key"] for c in t["columns"] if c["label"] == "Sarlavha")
    k_level = next(c["key"] for c in t["columns"] if c["label"] == "Daraja")
    k_user = next(c["key"] for c in t["columns"] if c["label"] == "Mas'ul")

    # majburiy yo'q -> 422
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root), json={"data": {k_level: "low"}})
    assert r.status_code == 422
    assert k_title in r.json()["detail"]["errors"]

    # noma'lum kalit -> 422
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                          json={"data": {k_title: "A", "xxx": 1}})
    assert r.status_code == 422

    # yaroqsiz select -> 422
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                          json={"data": {k_title: "A", k_level: "wrong"}})
    assert r.status_code == 422

    # yaroqsiz user ref -> 422
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                          json={"data": {k_title: "A", k_user: "00000000-0000-0000-0000-000000000000"}})
    assert r.status_code == 422

    # to'g'ri
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                          json={"data": {k_title: "  Fishing  ", k_level: "high"}})
    assert r.status_code == 201
    row = r.json()
    assert row["data"][k_title] == "Fishing"  # strip
    rid = row["id"]

    # patch — birlashtiradi
    r = await client.patch(f"/api/tables/{tid}/rows/{rid}", headers=_h(root),
                           json={"data": {k_level: "low"}})
    assert r.status_code == 200
    assert r.json()["data"][k_title] == "Fishing"
    assert r.json()["data"][k_level] == "low"

    # delete + revisions
    assert (await client.delete(f"/api/tables/{tid}/rows/{rid}", headers=_h(root))).status_code == 200
    revs = await client.get(f"/api/tables/{tid}/rows/{rid}/revisions", headers=_h(root))
    actions = [x["action"] for x in revs.json()]
    assert actions == ["delete", "update", "create"]


async def test_column_delete_strips_key_from_rows(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[
        {"label": "A", "type": "text"}, {"label": "B", "type": "text"},
    ])).json()
    tid = t["id"]
    ka = next(c["key"] for c in t["columns"] if c["label"] == "A")
    kb = next(c["key"] for c in t["columns"] if c["label"] == "B")
    cid_b = next(c["id"] for c in t["columns"] if c["label"] == "B")

    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                          json={"data": {ka: "x", kb: "y"}})
    rid = r.json()["id"]

    assert (await client.delete(f"/api/tables/{tid}/columns/{cid_b}", headers=_h(root))).status_code == 200

    rows = await client.get(f"/api/tables/{tid}/rows", headers=_h(root))
    data = rows.json()["items"][0]["data"]
    assert ka in data and kb not in data


async def test_column_type_change_rules(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[{"label": "A", "type": "text"}])).json()
    tid = t["id"]
    cid = t["columns"][0]["id"]
    ka = t["columns"][0]["key"]

    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root), json={"data": {ka: "hello"}})
    assert r.status_code == 201

    # text -> long_text: bo'sh bo'lmasa ham OK
    r = await client.patch(f"/api/tables/{tid}/columns/{cid}", headers=_h(root),
                           json={"type": "long_text"})
    assert r.status_code == 200

    # long_text -> number: qatorlar bor -> 409
    r = await client.patch(f"/api/tables/{tid}/columns/{cid}", headers=_h(root),
                           json={"type": "number"})
    assert r.status_code == 409

    # qatorni o'chirib, endi mumkin
    rid = (await client.get(f"/api/tables/{tid}/rows", headers=_h(root))).json()["items"][0]["id"]
    await client.delete(f"/api/tables/{tid}/rows/{rid}", headers=_h(root))
    r = await client.patch(f"/api/tables/{tid}/columns/{cid}", headers=_h(root),
                           json={"type": "number"})
    assert r.status_code == 200


async def test_select_option_in_use_cannot_be_removed(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[{"label": "S", "type": "select", "config": {
        "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]}}])).json()
    tid, cid, ks = t["id"], t["columns"][0]["id"], t["columns"][0]["key"]
    await client.post(f"/api/tables/{tid}/rows", headers=_h(root), json={"data": {ks: "a"}})

    # 'a' ni olib tashlash -> 409
    r = await client.patch(f"/api/tables/{tid}/columns/{cid}", headers=_h(root),
                           json={"config": {"options": [{"value": "b", "label": "B"}]}})
    assert r.status_code == 409

    # yangi variant qo'shish -> OK
    r = await client.patch(f"/api/tables/{tid}/columns/{cid}", headers=_h(root),
                           json={"config": {"options": [
                               {"value": "a", "label": "A"}, {"value": "b", "label": "B"},
                               {"value": "c", "label": "C"}]}})
    assert r.status_code == 200


async def test_section_isolation_and_viewer_readonly(client, actors):
    root = await _tok(client, "root_admin")
    soc = await _tok(client, "soc_boss")
    dlp = await _tok(client, "dlp_boss")
    viewer = await _tok(client, "watcher")

    tid = (await _mk_table(client, root, "soc", "Faqat SOC")).json()["id"]

    # dlp_admin soc jadvalini ko'ra olmaydi
    assert (await client.get(f"/api/tables/{tid}", headers=_h(dlp))).status_code == 404
    # soc_admin ko'radi
    assert (await client.get(f"/api/tables/{tid}", headers=_h(soc))).status_code == 200
    # viewer ko'radi, lekin yoza olmaydi
    assert (await client.get(f"/api/tables/{tid}", headers=_h(viewer))).status_code == 200
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(viewer), json={"data": {}})
    assert r.status_code == 403
    # viewer jadval ro'yxatida dlp jadvalini ham ko'radi
    (await _mk_table(client, dlp, "dlp", "DLP jadval"))
    lst = await client.get("/api/tables", headers=_h(viewer))
    sections = {t["section"] for t in lst.json()["items"]}
    assert {"soc", "dlp"} <= sections


async def test_rows_pagination_sort_search(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[
        {"label": "Ism", "type": "text"}, {"label": "Ball", "type": "number"},
    ])).json()
    tid = t["id"]
    kn = next(c["key"] for c in t["columns"] if c["label"] == "Ism")
    kb = next(c["key"] for c in t["columns"] if c["label"] == "Ball")
    for i in range(7):
        await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                          json={"data": {kn: f"user{i}", kb: (7 - i)}})

    p = (await client.get(f"/api/tables/{tid}/rows", headers=_h(root),
                          params={"limit": 3, "offset": 0})).json()
    assert p["total"] == 7 and len(p["items"]) == 3

    s = (await client.get(f"/api/tables/{tid}/rows", headers=_h(root),
                          params={"sort": f"{kb}:asc"})).json()
    balls = [r["data"][kb] for r in s["items"]]
    assert balls == sorted(balls)

    f = (await client.get(f"/api/tables/{tid}/rows", headers=_h(root),
                          params={"q": "user3"})).json()
    assert f["total"] == 1


async def test_optimistic_lock(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[{"label": "A", "type": "text"}])).json()
    tid, ka = t["id"], t["columns"][0]["key"]
    row = (await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                             json={"data": {ka: "v1"}})).json()
    rid, stamp = row["id"], row["updated_at"]

    # birinchi tahrir -> OK
    r1 = await client.patch(f"/api/tables/{tid}/rows/{rid}", headers=_h(root),
                            json={"data": {ka: "v2"}, "expected_updated_at": stamp})
    assert r1.status_code == 200
    # eski stamp bilan ikkinchi tahrir -> 409
    r2 = await client.patch(f"/api/tables/{tid}/rows/{rid}", headers=_h(root),
                            json={"data": {ka: "v3"}, "expected_updated_at": stamp})
    assert r2.status_code == 409


async def test_archive_blocks_writes(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[{"label": "A", "type": "text"}])).json()
    tid, ka = t["id"], t["columns"][0]["key"]

    await client.patch(f"/api/tables/{tid}", headers=_h(root), json={"is_archived": True})
    r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root), json={"data": {ka: "x"}})
    assert r.status_code == 409
    # arxivlangan jadval ro'yxatda ko'rinmaydi, lekin GET ishlaydi
    lst = await client.get("/api/tables", headers=_h(root))
    assert tid not in {x["id"] for x in lst.json()["items"]}
    assert (await client.get(f"/api/tables/{tid}", headers=_h(root))).status_code == 200
    lst2 = await client.get("/api/tables", headers=_h(root), params={"include_archived": True})
    assert tid in {x["id"] for x in lst2.json()["items"]}


async def test_hard_delete_only_superadmin(client, actors):
    root = await _tok(client, "root_admin")
    soc = await _tok(client, "soc_boss")
    tid = (await _mk_table(client, root, "soc", "T")).json()["id"]
    assert (await client.delete(f"/api/tables/{tid}", headers=_h(soc))).status_code == 403
    assert (await client.delete(f"/api/tables/{tid}", headers=_h(root))).status_code == 200
    assert (await client.get(f"/api/tables/{tid}", headers=_h(root))).status_code == 404


async def test_slug_collision(client, actors):
    root = await _tok(client, "root_admin")
    a = (await _mk_table(client, root, "soc", "Bir xil nom")).json()
    b = (await _mk_table(client, root, "soc", "Bir xil nom")).json()
    assert a["slug"] != b["slug"]
    assert b["slug"].endswith("-2")


async def test_row_revision_restore(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[
        {"label": "A", "type": "text", "config": {"required": True}},
    ])).json()
    tid = t["id"]
    ka = t["columns"][0]["key"]

    row = (await client.post(f"/api/tables/{tid}/rows", headers=_h(root),
                             json={"data": {ka: "v1"}})).json()
    rid = row["id"]
    await client.patch(f"/api/tables/{tid}/rows/{rid}", headers=_h(root),
                       json={"data": {ka: "v2"}})

    revs = (await client.get(f"/api/tables/{tid}/rows/{rid}/revisions", headers=_h(root))).json()
    # [update(v2), create(v1)] — eng eskisi create
    create_rev = next(r for r in revs if r["action"] == "create")

    r = await client.post(
        f"/api/tables/{tid}/rows/{rid}/revisions/{create_rev['id']}/restore",
        headers=_h(root),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"][ka] == "v1"

    # yangi 'update' reviziyasi qo'shildi
    revs2 = (await client.get(f"/api/tables/{tid}/rows/{rid}/revisions", headers=_h(root))).json()
    assert [x["action"] for x in revs2] == ["update", "update", "create"]

    # boshqa qatorning reviziyasi -> 404
    r = await client.post(
        f"/api/tables/{tid}/rows/{rid}/revisions/00000000-0000-0000-0000-000000000000/restore",
        headers=_h(root),
    )
    assert r.status_code == 404

    # viewer tiklay olmaydi
    viewer = await _tok(client, "watcher")
    r = await client.post(
        f"/api/tables/{tid}/rows/{rid}/revisions/{create_rev['id']}/restore",
        headers=_h(viewer),
    )
    assert r.status_code == 403


async def test_bulk_create_rows(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[
        {"label": "Ism", "type": "text", "config": {"required": True}},
        {"label": "Ball", "type": "number", "config": {"min": 0, "max": 10}},
    ])).json()
    tid = t["id"]
    kn = next(c["key"] for c in t["columns"] if c["label"] == "Ism")
    kb = next(c["key"] for c in t["columns"] if c["label"] == "Ball")

    r = await client.post(
        f"/api/tables/{tid}/rows/bulk",
        headers=_h(root),
        json={"rows": [
            {kn: "Ali", kb: 5},
            {kn: "Vali", kb: 99},   # max > 10 -> xato
            {kb: 3},                # majburiy Ism yo'q -> xato
            {kn: "Guli"},
        ]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["failed"] == 2
    assert {e["index"] for e in body["errors"]} == {1, 2}

    lst = await client.get(f"/api/tables/{tid}/rows", headers=_h(root))
    assert lst.json()["total"] == 2

    # viewer -> 403
    viewer = await _tok(client, "watcher")
    r = await client.post(f"/api/tables/{tid}/rows/bulk", headers=_h(viewer),
                          json={"rows": [{kn: "x"}]})
    assert r.status_code == 403


async def test_table_touched_on_row_change(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T", columns=[{"label": "A", "type": "text"}])).json()
    tid, ka = t["id"], t["columns"][0]["key"]
    before = (await client.get(f"/api/tables/{tid}", headers=_h(root))).json()["updated_at"]

    await client.post(f"/api/tables/{tid}/rows", headers=_h(root), json={"data": {ka: "x"}})
    after = (await client.get(f"/api/tables/{tid}", headers=_h(root))).json()["updated_at"]
    assert after > before


async def test_user_directory(client, actors):
    tok = await _tok(client, "watcher")
    r = await client.get("/api/users/directory", headers=_h(tok))
    assert r.status_code == 200
    names = {u["username"] for u in r.json()}
    assert {"root_admin", "soc_boss", "dlp_boss", "watcher"} <= names


async def test_audit_for_structural_changes(client, actors):
    root = await _tok(client, "root_admin")
    t = (await _mk_table(client, root, "soc", "T")).json()
    await client.post(f"/api/tables/{t['id']}/columns", headers=_h(root),
                      json={"label": "Yangi", "type": "text"})
    logs = await client.get("/api/admin/audit-logs", headers=_h(root))
    actions = {x["action"] for x in logs.json()["items"]}
    assert {"table_created", "column_added"} <= actions
