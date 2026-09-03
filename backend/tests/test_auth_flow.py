"""Auth oqimi va RBAC uchun integratsion testlar."""

import pytest

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


async def test_login_success_and_me(client, superadmin):
    res = await _login(client, "root_admin", "RootPass123")
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["role"] == "super_admin"
    assert body["must_change_password"] is False
    assert client.cookies.get("sd_refresh_token")

    me = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "root_admin"


async def test_login_wrong_password(client, superadmin):
    res = await _login(client, "root_admin", "nope")
    assert res.status_code == 401


async def test_lockout_after_max_attempts(client, superadmin):
    for _ in range(5):
        await _login(client, "root_admin", "wrong")
    # To'g'ri parol ham endi ishlamaydi — hisob qulflangan
    res = await _login(client, "root_admin", "RootPass123")
    assert res.status_code == 401
    assert "blok" in res.json()["detail"].lower()


async def test_forced_password_change_blocks_admin_api(client, superadmin):
    # Super admin yangi user yaratadi (must_change_password=True)
    login = (await _login(client, "root_admin", "RootPass123")).json()
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    created = await client.post(
        "/api/admin/users",
        headers=hdr,
        json={
            "username": "soc_guy",
            "temporary_password": "TempPass123",
            "role": "soc_admin",
        },
    )
    assert created.status_code == 201

    # Yangi user login qiladi, lekin himoyalangan endpoint'ga kira olmaydi
    new_login = (await _login(client, "soc_guy", "TempPass123")).json()
    assert new_login["must_change_password"] is True
    new_hdr = {"Authorization": f"Bearer {new_login['access_token']}"}

    blocked = await client.get("/api/soc/overview", headers=new_hdr)
    assert blocked.status_code == 403

    # Parolni o'zgartirgach — kirish ochiladi
    ch = await client.post(
        "/api/auth/change-password",
        headers=new_hdr,
        json={"current_password": "TempPass123", "new_password": "SocGuy123!"},
    )
    assert ch.status_code == 200

    relogin = (await _login(client, "soc_guy", "SocGuy123!")).json()
    ok = await client.get(
        "/api/soc/overview",
        headers={"Authorization": f"Bearer {relogin['access_token']}"},
    )
    assert ok.status_code == 200


async def test_rbac_section_isolation(client, superadmin):
    login = (await _login(client, "root_admin", "RootPass123")).json()
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    for name, role in [("soc_x", "soc_admin"), ("dlp_x", "dlp_admin"), ("view_x", "viewer")]:
        await client.post(
            "/api/admin/users",
            headers=hdr,
            json={"username": name, "temporary_password": "TempPass123", "role": role},
        )

    async def token_after_change(username, new_pw):
        first = (await _login(client, username, "TempPass123")).json()
        await client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {first['access_token']}"},
            json={"current_password": "TempPass123", "new_password": new_pw},
        )
        return (await _login(client, username, new_pw)).json()["access_token"]

    soc_t = await token_after_change("soc_x", "SocX12345!")
    dlp_t = await token_after_change("dlp_x", "DlpX12345!")
    view_t = await token_after_change("view_x", "ViewX1234!")

    # SOC admin: SOC ha, DLP yo'q
    assert (await client.get("/api/soc/overview", headers={"Authorization": f"Bearer {soc_t}"})).status_code == 200
    assert (await client.get("/api/dlp/overview", headers={"Authorization": f"Bearer {soc_t}"})).status_code == 403

    # DLP admin: DLP ha, SOC yo'q
    assert (await client.get("/api/dlp/overview", headers={"Authorization": f"Bearer {dlp_t}"})).status_code == 200
    assert (await client.get("/api/soc/overview", headers={"Authorization": f"Bearer {dlp_t}"})).status_code == 403

    # Viewer: ikkalasini ham o'qiydi, lekin yoza olmaydi
    assert (await client.get("/api/soc/overview", headers={"Authorization": f"Bearer {view_t}"})).status_code == 200
    assert (await client.get("/api/dlp/overview", headers={"Authorization": f"Bearer {view_t}"})).status_code == 200
    assert (await client.post("/api/soc/overview", headers={"Authorization": f"Bearer {view_t}"})).status_code == 403


async def test_only_superadmin_reaches_admin_api(client, superadmin):
    login = (await _login(client, "root_admin", "RootPass123")).json()
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    await client.post(
        "/api/admin/users",
        headers=hdr,
        json={"username": "plain_soc", "temporary_password": "TempPass123", "role": "soc_admin"},
    )
    first = (await _login(client, "plain_soc", "TempPass123")).json()
    await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {first['access_token']}"},
        json={"current_password": "TempPass123", "new_password": "PlainSoc1!"},
    )
    tok = (await _login(client, "plain_soc", "PlainSoc1!")).json()["access_token"]
    res = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 403


async def test_refresh_rotation_and_logout(client, superadmin):
    await _login(client, "root_admin", "RootPass123")
    r1 = await client.post("/api/auth/refresh")
    assert r1.status_code == 200
    assert r1.json()["access_token"]

    out = await client.post("/api/auth/logout")
    assert out.status_code == 200
    # Logout'dan keyin eski cookie bilan refresh ishlamaydi
    r2 = await client.post("/api/auth/refresh")
    assert r2.status_code == 401


async def test_audit_log_written(client, superadmin):
    login = (await _login(client, "root_admin", "RootPass123")).json()
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    await _login(client, "root_admin", "bad")  # login_failed yozuvi

    logs = await client.get("/api/admin/audit-logs", headers=hdr)
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()["items"]}
    assert "login" in actions
    assert "login_failed" in actions


# ---------------------------------------------------------------------------
# Xavfsizlik qattiqlashtirishlari uchun testlar
# ---------------------------------------------------------------------------


async def _root_headers(client):
    body = (await _login(client, "root_admin", "RootPass123")).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


async def _create(client, hdr, username, role="soc_admin", pw="TempPass123"):
    return await client.post(
        "/api/admin/users",
        headers=hdr,
        json={"username": username, "temporary_password": pw, "role": role},
    )


async def test_blocked_user_cannot_login(client, superadmin):
    hdr = await _root_headers(client)
    created = (await _create(client, hdr, "blockme")).json()
    uid = created["user"]["id"]

    r = await client.patch(f"/api/admin/users/{uid}/block", headers=hdr)
    assert r.status_code == 200

    res = await _login(client, "blockme", "TempPass123")
    assert res.status_code == 401
    assert "blok" in res.json()["detail"].lower()

    # unblock -> yana kira oladi
    assert (await client.patch(f"/api/admin/users/{uid}/unblock", headers=hdr)).status_code == 200
    assert (await _login(client, "blockme", "TempPass123")).status_code == 200


async def test_password_change_revokes_old_access_token(client, superadmin):
    hdr = await _root_headers(client)
    await _create(client, hdr, "pwuser")

    first = (await _login(client, "pwuser", "TempPass123")).json()
    old_token = first["access_token"]

    ch = await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={"current_password": "TempPass123", "new_password": "BrandNew123"},
    )
    assert ch.status_code == 200

    # Eski access token endi yaroqsiz (token_version oshdi)
    me = await client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert me.status_code == 401


async def test_block_revokes_access_token_immediately(client, superadmin):
    hdr = await _root_headers(client)
    created = (await _create(client, hdr, "livesession")).json()
    uid = created["user"]["id"]

    # Parolni almashtirib, to'liq faol sessiya olamiz
    first = (await _login(client, "livesession", "TempPass123")).json()
    await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {first['access_token']}"},
        json={"current_password": "TempPass123", "new_password": "LiveOne1234"},
    )
    active = (await _login(client, "livesession", "LiveOne1234")).json()
    tok = active["access_token"]
    assert (await client.get("/api/soc/overview", headers={"Authorization": f"Bearer {tok}"})).status_code == 200

    # Super admin bloklaydi -> eski access token darhol yaroqsiz
    await client.patch(f"/api/admin/users/{uid}/block", headers=hdr)
    r = await client.get("/api/soc/overview", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code in (401, 403)


async def test_refresh_token_reuse_detected(client, superadmin):
    await _login(client, "root_admin", "RootPass123")
    old_cookie = client.cookies.get("sd_refresh_token")

    # Rotatsiya -> yangi cookie o'rnatiladi, eskisi bekor qilinadi
    r1 = await client.post("/api/auth/refresh")
    assert r1.status_code == 200
    new_cookie = client.cookies.get("sd_refresh_token")
    assert new_cookie != old_cookie

    # Eski (bekor qilingan) tokenni qayta ishlatish -> reuse detection
    reuse = await client.post(
        "/api/auth/refresh", cookies={"sd_refresh_token": old_cookie}
    )
    assert reuse.status_code == 401

    # Endi YANGI token ham ishlamaydi (butun oila bekor qilindi)
    assert (
        await client.post(
            "/api/auth/refresh", cookies={"sd_refresh_token": new_cookie}
        )
    ).status_code == 401

    logs = await client.get(
        "/api/admin/audit-logs", headers=await _root_headers(client)
    )
    assert "token_reuse_detected" in {i["action"] for i in logs.json()["items"]}


async def test_weak_password_rejected_on_create_and_change(client, superadmin):
    hdr = await _root_headers(client)

    weak = await client.post(
        "/api/admin/users",
        headers=hdr,
        json={"username": "weaky", "temporary_password": "short1", "role": "viewer"},
    )
    assert weak.status_code == 422

    no_upper = await client.post(
        "/api/admin/users",
        headers=hdr,
        json={"username": "weaky2", "temporary_password": "alllower123", "role": "viewer"},
    )
    assert no_upper.status_code == 422

    # to'g'ri parol -> 201
    ok = await _create(client, hdr, "goodpw", role="viewer", pw="GoodPass123")
    assert ok.status_code == 201

    first = (await _login(client, "goodpw", "GoodPass123")).json()
    bad_change = await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {first['access_token']}"},
        json={"current_password": "GoodPass123", "new_password": "password123"},
    )
    assert bad_change.status_code == 422


async def test_users_pagination(client, superadmin):
    hdr = await _root_headers(client)
    for i in range(7):
        await _create(client, hdr, f"paged{i}", role="viewer")

    page1 = (await client.get("/api/admin/users", headers=hdr, params={"limit": 3, "offset": 0})).json()
    assert page1["total"] == 8  # 7 + root_admin
    assert len(page1["items"]) == 3
    assert page1["limit"] == 3

    page3 = (await client.get("/api/admin/users", headers=hdr, params={"limit": 3, "offset": 6})).json()
    assert len(page3["items"]) == 2

    filtered = (await client.get("/api/admin/users", headers=hdr, params={"q": "paged3"})).json()
    assert filtered["total"] == 1


async def test_cannot_act_on_self(client, superadmin):
    hdr = await _root_headers(client)
    me = (await client.get("/api/users/me", headers=hdr)).json()
    r = await client.patch(f"/api/admin/users/{me['id']}/block", headers=hdr)
    assert r.status_code == 400


async def test_can_manage_other_super_admin(client, superadmin):
    """Boshqa super_adminni bloklash mumkin (o'zini emas)."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole
    from tests.conftest import TestSession

    async with TestSession() as db:
        db.add(
            User(
                username="second_root",
                hashed_password=hash_password("SecondRoot1"),
                role=UserRole.super_admin,
                is_active=True,
                must_change_password=False,
            )
        )
        await db.commit()

    hdr = await _root_headers(client)
    users = (await client.get("/api/admin/users", headers=hdr, params={"q": "second_root"})).json()
    uid = users["items"][0]["id"]
    r = await client.patch(f"/api/admin/users/{uid}/block", headers=hdr)
    assert r.status_code == 200
    assert (await _login(client, "second_root", "SecondRoot1")).status_code == 401


async def test_security_headers_present(client, superadmin):
    r = await client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in {k.lower() for k in r.headers}


async def test_admin_reset_password(client, superadmin):
    hdr = await _root_headers(client)
    created = (await _create(client, hdr, "forgetful")).json()
    uid = created["user"]["id"]

    # Foydalanuvchi parolni almashtirib, faol sessiya oladi
    first = (await _login(client, "forgetful", "TempPass123")).json()
    await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {first['access_token']}"},
        json={"current_password": "TempPass123", "new_password": "IForgot1234"},
    )
    active = (await _login(client, "forgetful", "IForgot1234")).json()
    old_tok = active["access_token"]

    # Super admin parolni tiklaydi (server generatsiya qiladi)
    r = await client.post(
        f"/api/admin/users/{uid}/reset-password", headers=hdr, json={}
    )
    assert r.status_code == 200
    new_temp = r.json()["temporary_password"]
    assert r.json()["user"]["must_change_password"] is True

    # Eski parol va eski access token endi ishlamaydi
    assert (await _login(client, "forgetful", "IForgot1234")).status_code == 401
    assert (
        await client.get("/api/users/me", headers={"Authorization": f"Bearer {old_tok}"})
    ).status_code == 401

    # Yangi vaqtinchalik parol bilan kiradi -> majburiy almashtirish
    relog = await _login(client, "forgetful", new_temp)
    assert relog.status_code == 200
    assert relog.json()["must_change_password"] is True

    logs = await client.get("/api/admin/audit-logs", headers=hdr)
    assert "password_reset" in {i["action"] for i in logs.json()["items"]}


async def test_admin_reset_password_explicit_value_and_policy(client, superadmin):
    hdr = await _root_headers(client)
    created = (await _create(client, hdr, "resetme2")).json()
    uid = created["user"]["id"]

    weak = await client.post(
        f"/api/admin/users/{uid}/reset-password",
        headers=hdr,
        json={"temporary_password": "weak"},
    )
    assert weak.status_code == 422

    ok = await client.post(
        f"/api/admin/users/{uid}/reset-password",
        headers=hdr,
        json={"temporary_password": "FreshStart99"},
    )
    assert ok.status_code == 200
    assert (await _login(client, "resetme2", "FreshStart99")).status_code == 200


async def test_cannot_reset_own_password_via_admin(client, superadmin):
    hdr = await _root_headers(client)
    me = (await client.get("/api/users/me", headers=hdr)).json()
    r = await client.post(
        f"/api/admin/users/{me['id']}/reset-password", headers=hdr, json={}
    )
    assert r.status_code == 400
