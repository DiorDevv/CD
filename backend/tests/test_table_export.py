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
