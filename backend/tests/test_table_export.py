"""Jadval eksporti — sinxron yuklab olish, fon job, ulashish havolasi."""

import pytest

from app.services import export_job_service
from tests.conftest import ACTOR_PASSWORD, TestSession

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _export_test_wiring(monkeypatch):
    # Fon job'i o'z sessiyasini `AsyncSessionLocal` orqali ochadi — testda uni
    # NullPool'li test sessiyasiga yo'naltiramiz.
    monkeypatch.setattr(export_job_service, "AsyncSessionLocal", TestSession)
    # `start()` fire-and-forget task'i ASGI transport ostida deterministik emas —
    # testlar `run_job`ni to'g'ridan-to'g'ri (await bilan) ishlatadi.
    monkeypatch.setattr(export_job_service, "start", lambda _job_id: None)


async def _tok(client, username: str) -> str:
    r = await client.post("/api/auth/login", json={"username": username, "password": ACTOR_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


async def _table_with_rows(client, tok, n=3):
    t = (
        await client.post(
            "/api/tables",
            headers=_h(tok),
            json={
                "section": "soc",
                "name": "Eksport jadvali",
                "columns": [
                    {"label": "Ism", "type": "text", "config": {"required": True}},
                    {"label": "Ball", "type": "number"},
                    {
                        "label": "Daraja",
                        "type": "select",
                        "config": {"options": [
                            {"value": "low", "label": "Past"}, {"value": "high", "label": "Yuqori"}
                        ]},
                    },
                ],
            },
        )
    ).json()
    tid = t["id"]
    keys = {c["label"]: c["key"] for c in t["columns"]}
    for i in range(n):
        await client.post(
            f"/api/tables/{tid}/rows",
            headers=_h(tok),
            json={"data": {keys["Ism"]: f"user{i}", keys["Ball"]: i, keys["Daraja"]: "high"}},
        )
    return tid, keys


async def _run_latest_job(client, tok, tid):
    """API orqali job yaratadi, so'ng run_job'ни to'g'ridan-to'g'ri ishlatadi
    (ASGI transport ostida fire-and-forget task deterministik emas)."""
    jobs = (await client.get(f"/api/tables/{tid}/export/jobs", headers=_h(tok))).json()
    job_id = jobs[0]["id"]
    await export_job_service.run_job(job_id)
    return job_id


# --- Sinxron eksport -------------------------------------------------------


async def test_sync_csv_export(client, actors):
    root = await _tok(client, "root_admin")
    tid, keys = await _table_with_rows(client, root, n=2)

    r = await client.get(f"/api/tables/{tid}/export", headers=_h(root), params={"format": "csv"})
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers["content-disposition"]
    body = r.content.decode("utf-8-sig")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    assert lines[0].split(",")[:3] == ["Ism", "Ball", "Daraja"]
    assert len(lines) == 3  # header + 2 qator
    assert "Yuqori" in body  # select label matnlashtirilgan

    r = await client.get(f"/api/tables/{tid}/export", headers=_h(root), params={"format": "xlsx"})
    assert r.status_code == 400


async def test_export_rbac(client, actors):
    root = await _tok(client, "root_admin")
    dlp = await _tok(client, "dlp_boss")
    viewer = await _tok(client, "watcher")
    tid, _ = await _table_with_rows(client, root, n=1)

    assert (await client.get(f"/api/tables/{tid}/export", headers=_h(dlp))).status_code == 404
    assert (await client.get(f"/api/tables/{tid}/export", headers=_h(viewer))).status_code == 200


# --- Fon job -------------------------------------------------------------


async def test_export_job_and_download(client, actors):
    root = await _tok(client, "root_admin")
    tid, _ = await _table_with_rows(client, root, n=4)

    r = await client.post(
        f"/api/tables/{tid}/export/jobs", headers=_h(root), params={"format": "xlsx"}
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    assert r.json()["status"] in ("pending", "running")

    await export_job_service.run_job(job_id)

    done = (await client.get(f"/api/exports/{job_id}", headers=_h(root))).json()
    assert done["status"] == "done"
    assert done["row_count"] == 4
    assert done["checksum_sha256"] and len(done["checksum_sha256"]) == 64
    assert done["file_size_bytes"] > 0

    dl = await client.get(f"/api/exports/{job_id}/download", headers=_h(root))
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"  # xlsx = zip

    after = (await client.get(f"/api/exports/{job_id}", headers=_h(root))).json()
    assert after["downloaded_at"] is not None
    assert after["download_count"] == 1

    lst = await client.get(f"/api/tables/{tid}/export/jobs", headers=_h(root))
    assert job_id in {j["id"] for j in lst.json()}


async def test_export_job_concurrency_limit(client, actors, monkeypatch):
    monkeypatch.setattr(
        __import__("app.config", fromlist=["settings"]).settings, "EXPORT_JOB_MAX_CONCURRENT", 1
    )
    root = await _tok(client, "root_admin")
    tid, _ = await _table_with_rows(client, root, n=1)
    r1 = await client.post(f"/api/tables/{tid}/export/jobs", headers=_h(root))
    assert r1.status_code == 201
    r2 = await client.post(f"/api/tables/{tid}/export/jobs", headers=_h(root))
    assert r2.status_code == 429


async def test_export_share_link(client, actors):
    root = await _tok(client, "root_admin")
    viewer = await _tok(client, "watcher")
    tid, _ = await _table_with_rows(client, root, n=2)

    await client.post(f"/api/tables/{tid}/export/jobs", headers=_h(root), params={"format": "csv"})
    job_id = await _run_latest_job(client, root, tid)

    assert (await client.post(f"/api/exports/{job_id}/share", headers=_h(viewer))).status_code == 403

    sh = await client.post(f"/api/exports/{job_id}/share", headers=_h(root))
    assert sh.status_code == 200, sh.text
    token = sh.json()["token"]
    assert sh.json()["url"].endswith(token)

    pub = await client.get(f"/api/exports/{job_id}/shared", params={"token": token})
    assert pub.status_code == 200
    assert pub.content.decode("utf-8-sig").splitlines()[0].startswith("Ism")

    assert (
        await client.get(f"/api/exports/{job_id}/shared", params={"token": "wrong-token-xxxxxxxx"})
    ).status_code == 404

    rev = await client.post(f"/api/exports/{job_id}/share/revoke", headers=_h(root))
    assert rev.status_code == 200
    assert (
        await client.get(f"/api/exports/{job_id}/shared", params={"token": token})
    ).status_code == 404


async def test_export_cancel_after_done_conflicts(client, actors):
    root = await _tok(client, "root_admin")
    tid, _ = await _table_with_rows(client, root, n=1)
    await client.post(f"/api/tables/{tid}/export/jobs", headers=_h(root), params={"format": "csv"})
    job_id = await _run_latest_job(client, root, tid)
    r = await client.post(f"/api/exports/{job_id}/cancel", headers=_h(root))
    assert r.status_code == 409


async def test_export_audit(client, actors):
    root = await _tok(client, "root_admin")
    tid, _ = await _table_with_rows(client, root, n=1)
    await client.get(f"/api/tables/{tid}/export", headers=_h(root), params={"format": "csv"})
    logs = await client.get("/api/admin/audit-logs", headers=_h(root))
    assert "export_created" in {x["action"] for x in logs.json()["items"]}


async def test_export_import_roundtrip(client, actors):
    """Eksport qilingan CSV'ni o'zgartirmasdan qayta import qilib bo'ladi:
    select/multi_select label'i va `user` username'i id'ga yechiladi."""
    import csv as _csv
    import io as _io

    from sqlalchemy import select as _select

    from app.models.user import User as _User

    root = await _tok(client, "root_admin")
    async with TestSession() as db:
        root_id = str(
            (await db.execute(_select(_User.id).where(_User.username == "root_admin"))).scalar_one()
        )

    t = (
        await client.post(
            "/api/tables",
            headers=_h(root),
            json={
                "section": "soc",
                "name": "Round trip",
                "columns": [
                    {"label": "Ism", "type": "text"},
                    {
                        "label": "Daraja",
                        "type": "select",
                        "config": {"options": [
                            {"value": "low", "label": "Past"},
                            {"value": "high", "label": "Yuqori"},
                        ]},
                    },
                    {
                        "label": "Teglar",
                        "type": "multi_select",
                        "config": {"options": [
                            {"value": "a", "label": "Alfa"},
                            {"value": "b", "label": "Beta"},
                            {"value": "c", "label": "Gamma"},
                        ]},
                    },
                    {"label": "Mas'ul", "type": "user"},
                    {"label": "Faol", "type": "boolean"},
                ],
            },
        )
    ).json()
    tid = t["id"]
    key = {c["label"]: c["key"] for c in t["columns"]}

    originals = [
        {key["Ism"]: "Bir", key["Daraja"]: "high", key["Teglar"]: ["a", "b"],
         key["Mas'ul"]: root_id, key["Faol"]: True},
        {key["Ism"]: "Ikki", key["Daraja"]: "low", key["Teglar"]: ["c"], key["Faol"]: False},
    ]
    for data in originals:
        r = await client.post(f"/api/tables/{tid}/rows", headers=_h(root), json={"data": data})
        assert r.status_code == 201, r.text

    r = await client.get(f"/api/tables/{tid}/export", headers=_h(root), params={"format": "csv"})
    assert r.status_code == 200
    grid = list(_csv.reader(_io.StringIO(r.content.decode("utf-8-sig"))))
    header = grid[0]
    body = [g for g in grid[1:] if any(c.strip() for c in g)]
    assert len(body) == 2

    # eksport kataklari (label / username) — bulk import'ga o'zgartirmasdan
    rows_payload = [
        {key[h]: v for h, v in zip(header, line) if v != ""} for line in body
    ]
    res = await client.post(f"/api/tables/{tid}/rows/bulk", headers=_h(root), json={"rows": rows_payload})
    assert res.status_code == 201, res.text
    j = res.json()
    assert j["failed"] == 0, j["errors"]
    assert j["created"] == 2

    got = sorted(j["items"], key=lambda x: x["data"][key["Ism"]])
    assert got[0]["data"][key["Daraja"]] == "high"
    assert got[0]["data"][key["Teglar"]] == ["a", "b"]
    assert got[0]["data"][key["Mas'ul"]] == root_id
    assert got[0]["data"][key["Faol"]] is True
    assert got[1]["data"][key["Daraja"]] == "low"
    assert got[1]["data"][key["Teglar"]] == ["c"]
    assert got[1]["data"].get(key["Faol"]) is False


async def test_reconcile_orphans_after_restart(client, actors, monkeypatch):
    """Backend restart'ini taqlid qilamiz: 'running' da qolgan job'lar —
    cap ichidagilari qayta navbatga, ortiqchasi 'failed'."""
    from app.config import settings as _settings
    from app.models.export_job import ExportJob, ExportJobStatus

    monkeypatch.setattr(_settings, "EXPORT_JOB_MAX_CONCURRENT", 1)
    root = await _tok(client, "root_admin")
    tid, _ = await _table_with_rows(client, root, n=2)

    # ikkita job yaratamiz (autouse fixture start()'ni no-op qilgan)
    j1 = (await client.post(f"/api/tables/{tid}/export/jobs", headers=_h(root))).json()["id"]
    # 429 bo'lmasligi uchun 1-jobни vaqtincha "running" dan chiqaramiz emas —
    # buning o'rniga ikkinchisini to'g'ridan-to'g'ri DB'ga qo'shamiz
    async with TestSession() as db:
        first = await db.get(ExportJob, __import__("uuid").UUID(j1))
        j2 = ExportJob(
            table_id=first.table_id,
            section=first.section,
            status=ExportJobStatus.running,
            format=first.format,
            filters={"q": None, "sort": None},
            created_by=first.created_by,
        )
        db.add(j2)
        first.status = ExportJobStatus.running
        await db.commit()
        j2_id = str(j2.id)

    async with TestSession() as db:
        n = await export_job_service.reconcile_orphans(db)
    assert n == 2

    async with TestSession() as db:
        a = await db.get(ExportJob, __import__("uuid").UUID(j1))
        b = await db.get(ExportJob, __import__("uuid").UUID(j2_id))
        by_created = sorted([a, b], key=lambda x: x.created_at)
        assert by_created[0].status is ExportJobStatus.pending
        assert by_created[0].error_message is None
        assert by_created[1].status is ExportJobStatus.failed
        assert "qayta" in (by_created[1].error_message or "").lower()

    # tiklangan job haqiqatan tugay oladi
    resumed_id = str(by_created[0].id)
    await export_job_service.run_job(resumed_id)
    done = (await client.get(f"/api/exports/{resumed_id}", headers=_h(root))).json()
    assert done["status"] == "done"
