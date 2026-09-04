# Sentinel — SOC/DLP Monitoring Platform

Ichki monitoring platformasi.

- **1-bosqich:** autentifikatsiya va role-based access control (RBAC) — login,
  majburiy parol almashtirish, super admin panel, audit jurnali.
- **2-bosqich:** dinamik jadvallar — admin logindan keyin o'zi jadval quradi
  (ustunlarni belgilaydi, turini tanlaydi, qatorlarni to'ldiradi). No-code
  data-grid, bo'lim bo'yicha RBAC bilan.

---

## Texnologiyalar

| Qatlam    | Stack |
|-----------|-------|
| Backend   | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL |
| Auth      | JWT (access + refresh), passlib/bcrypt, httpOnly refresh cookie |
| Frontend  | React + TypeScript, Vite, Tailwind CSS, Framer Motion, Radix (shadcn uslubi), lucide-react, sonner |
| Infra     | Docker Compose |

---

## Rollar

| Rol           | Ruxsatlar |
|---------------|-----------|
| `super_admin` | Faqat seed skript orqali yaratiladi. User CRUD, block/unblock, audit log. |
| `soc_admin`   | Faqat SOC bo'limi. DLP'ga kira olmaydi. |
| `dlp_admin`   | Faqat DLP bo'limi. SOC'ga kira olmaydi. |
| `viewer`      | SOC + DLP — **faqat o'qish** (backend darajasida ham). |

### Xavfsizlik xususiyatlari

- **Public sign-up yo'q** — foydalanuvchi faqat super_admin tomonidan yaratiladi.
- **Birinchi kirishda majburiy parol almashtirish** (`must_change_password`).
- **Parol siyosati** (`config.PASSWORD_MIN_LENGTH`, default 10): katta + kichik harf,
  raqam, bo'sh joysiz, oddiy parollar ro'yxatidan emas, username'ni o'z ichiga
  olmasligi. Seed, admin-create va change-password — bir xil qoida.
- **Login urinishlari limiti** — 5 ta xato → 15 daqiqa qulf. Hisoblagich yangilanishi
  qatorli `SELECT ... FOR UPDATE` bilan himoyalangan (race condition yo'q).
- **JWT + `token_version` (xavfsizlik shtampi)** — parol o'zgarganda yoki user
  bloklanganda shtamp oshiriladi va mavjud access tokenlar (30 daqiqagacha
  amal qiladigan) **darhol** yaroqsiz bo'ladi. Bloklangan user `is_active`
  tekshiruvi tufayli ham har so'rovda rad etiladi.
- **Refresh token rotation + reuse detection** — token DB'da faqat SHA-256 hash.
  Almashtirilgan (revoked) token qayta ishlatilsa, o'sha foydalanuvchining barcha
  refresh tokenlari bekor qilinadi va `token_reuse_detected` audit'ga yoziladi.
- **Xavfsizlik header'lari** — `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, `Permissions-Policy`, API uchun qattiq `Content-Security-Policy`,
  prod + HTTPS'da `Strict-Transport-Security`.
- **Retention** — muddati tugagan refresh tokenlar va eski audit yozuvlari (default
  180 kun) fon vazifasi orqali davriy tozalanadi (`CLEANUP_INTERVAL_HOURS`).
- **Audit log** — barcha muhim amallar `audit_logs` jadvaliga IP bilan yoziladi.

---

## Tez ishga tushirish (Docker Compose)

```bash
# 1. Konfiguratsiya
cp .env.example .env
#   .env ni oching va quyidagilarni almashtiring:
#     JWT_SECRET_KEY   ->  openssl rand -hex 32
#     SUPERADMIN_USERNAME / SUPERADMIN_PASSWORD

# 2. Ishga tushirish
docker compose up --build
```

Konteynerlar ko'tarilganda backend avtomatik ravishda:
1. PostgreSQL tayyor bo'lishini kutadi
2. `alembic upgrade head` — migratsiyalarni qo'llaydi
3. `scripts/seed_superadmin.py` — super admin bo'lmasa, uni yaratadi

| Xizmat        | URL |
|---------------|-----|
| Frontend      | http://localhost:5173 |
| Backend API   | http://localhost:8000/api |
| Swagger docs  | http://localhost:8000/docs |
| PostgreSQL    | localhost:5432 |

**Birinchi kirish:** `.env` dagi `SUPERADMIN_USERNAME` / `SUPERADMIN_PASSWORD`
bilan kiring → tizim majburiy parol almashtirish sahifasiga yo'naltiradi →
yangi parol o'rnating → qayta kiring.

---

## Ishlab chiqarish (production) — bitta port `:8090`

Bitta origin ortida: **nginx** SPA'ni (statik build) beradi va `/api` + `/health`
so'rovlarini backendga uzatadi. `backend` va `db` host'ga **ochilmaydi**.
Dev stekidan alohida: konteynerlar `sdp_*`, volume `sd-prod_sdp_db_data`,
loyiha nomi `sd-prod` — dev bilan yonma-yon ishlaydi.

**Eng oddiy — konfiguratsiyasiz (internet bor server):**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

> **Internetsiz VM (Squid ortida):** build vaqtida `pip`/`npm` proksi orqali
> chiqishi kerak — proksини **build'ga uzatish** shart (aks holda `Ign:` xatolari):
> ```bash
> HTTP_PROXY=http://PROXY:3128 HTTPS_PROXY=http://PROXY:3128 \
> NO_PROXY=localhost,127.0.0.1,::1,db,backend,web \
> docker compose -f docker-compose.prod.yml up -d --build
> ```
> yoki `./deploy/vm-setup.sh --proxy http://PROXY:3128`. (Backend'da `apt` yo'q —
> faqat `pip`; frontend build'да `npm ci`.)

`.env.prod` bo'lmasa: `JWT_SECRET_KEY` va super admin paroli konteyner ichida bir
marta generatsiya qilinib `sdp_secrets` volume'da saqlanadi. Parol backend
loglarida chop etiladi:

```bash
docker compose -f docker-compose.prod.yml logs backend | grep -A1 "SUPER ADMIN"
# yoki:  docker compose -f docker-compose.prod.yml exec backend cat /data/superadmin_password
```

**Kuchli parollarni o'zingiz belgilamoqchi bo'lsangiz:**

```bash
cp .env.prod.example .env.prod        # POSTGRES_PASSWORD, JWT_SECRET_KEY, SUPERADMIN_PASSWORD
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Holat / loglar / to'xtatish:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml down          # (+ `-v` volume bilan)
```

| Yo'l | |
|------|--|
| Ilova | http://localhost:8090 |
| API   | http://localhost:8090/api |
| Health | http://localhost:8090/health |

Portni o'zgartirish: `WEB_PORT=9000 docker compose ...` yoki `.env.prod` da.

**HTTPS — Docker orqali (Caddy):** `docker-compose.tls.yml` qo'shimcha fayli Caddy
konteynerini qo'shadi — 80/443 da turadi, `DOMAIN` uchun avtomatik Let's Encrypt
sertifikat oladi, `web` (nginx) ga uzatadi (`:8090` yopiladi). `.env.prod` da
`DOMAIN=...`, `COOKIE_SECURE=true`, `CORS_ORIGINS=https://...` va:
```
docker compose -f docker-compose.prod.yml -f docker-compose.tls.yml --env-file .env.prod up -d --build
```
(Tashqi TLS terminator ishlatsangiz — faqat `COOKIE_SECURE=true` yetadi.)

**Yangilash (qayta deploy):** `git pull` → yuqoridagi `up -d --build`. Migratsiyalar
konteyner startida avtomatik (`alembic upgrade head`), ma'lumotlar volume'da qoladi.

### Internetsiz VM (Squid proksi orqali)

VM to'g'ridan-to'g'ri internetga chiqmasa — build 3 qatlamda proksi orqali:
Docker demoni, build vaqti (`pip`/`npm`), runtime. Dockerfile'lar va
compose fayllar `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` ni qabul qiladi; `.env`
(yoki `.env.prod`) da to'ldiriladi (`NO_PROXY` ga `db`,`backend`,`web` qo'shiladi).
Proksi umuman bo'lmasa — air-gap bundle: internetli mashinada `./deploy/bundle.sh`
→ arxivni VM'ga → `docker load` → `up --no-build`.

**Eng oson:** Docker o'rnatilgan VM'da bitta buyruq — `.env.prod` (tasodifiy
parollar) yaratiladi, kerak bo'lsa demon proksisi sozlanadi, stack ko'tariladi:
```bash
./deploy/vm-setup.sh                              # internet bor
./deploy/vm-setup.sh --proxy http://PROXY:3128    # internetsiz (Squid)
```
**To'liq VM runbook:** **[`deploy/VM-DEPLOY.md`](deploy/VM-DEPLOY.md)** (0 dan:
proksi, Docker, `.env.prod`, build, port, kirish, yangilash, backup, HTTPS, air-gap).
Proksi mexanizmi tafsiloti: [`deploy/PROKSI-VA-VM.md`](deploy/PROKSI-VA-VM.md).

---

## Lokal ishga tushirish (Docker'siz)

### Backend

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql+asyncpg://soc:soc@localhost:5432/soc_platform"
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
export SUPERADMIN_USERNAME="superadmin"
export SUPERADMIN_PASSWORD="ChangeMe_S3cure!"

alembic upgrade head
python -m scripts.seed_superadmin
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
cp .env.example .env      # VITE_API_BASE_URL ni tekshiring
npm install
npm run dev
```

---

## API endpoint'lari

| Metod | Yo'l | Ruxsat | Tavsif |
|-------|------|--------|--------|
| POST | `/api/auth/login` | ochiq | access token + refresh cookie |
| POST | `/api/auth/refresh` | refresh cookie | yangi access token (rotation) |
| POST | `/api/auth/logout` | refresh cookie | refresh tokenni bekor qiladi |
| POST | `/api/auth/change-password` | auth | parolni o'zgartiradi, sessiyalarni tozalaydi |
| GET  | `/api/users/me` | auth | joriy foydalanuvchi |
| POST | `/api/admin/users` | super_admin | yangi admin/viewer yaratish |
| GET  | `/api/admin/users` | super_admin | sahifalangan ro'yxat: `{items,total,limit,offset}` (`?role=` `?is_active=` `?q=` `?limit=` `?offset=`) |
| PATCH | `/api/admin/users/{id}/block` | super_admin | bloklash (sessiyalar + access token bekor) |
| PATCH | `/api/admin/users/{id}/unblock` | super_admin | faollashtirish |
| POST | `/api/admin/users/{id}/reset-password` | super_admin | parolni tiklash — yangi vaqtinchalik parol (berilmasa generatsiya), `must_change_password=True` |
| DELETE | `/api/admin/users/{id}` | super_admin | o'chirish |
| GET  | `/api/admin/audit-logs` | super_admin | audit jurnali (filtrlash + pagination) |
| GET  | `/api/users/directory` | auth | faol foydalanuvchilar ro'yxati (`user` turidagi ustunlar uchun) |
| GET/POST | `/api/soc/overview` | SOC (yozish: soc_admin) | placeholder — RBAC namoyishi |
| GET/POST | `/api/dlp/overview` | DLP (yozish: dlp_admin) | placeholder — RBAC namoyishi |

### Dinamik jadvallar (2-bosqich)

Bo'lim bo'yicha ruxsat: `super_admin` = hammasi RW · `soc_admin` = `soc`+`shared` RW ·
`dlp_admin` = `dlp`+`shared` RW · `viewer` = hammasi faqat o'qish (backend'da qat'iy).

| Metod | Yo'l | Tavsif |
|-------|------|--------|
| GET/POST | `/api/tables` | sahifalangan ro'yxat (`?section=` `?include_archived=`) / jadval yaratish |
| GET/PATCH/DELETE | `/api/tables/{id}` | ta'rif+ustunlar / nom, izoh, arxiv / **butunlay o'chirish (faqat super_admin)** |
| POST/PATCH/DELETE | `/api/tables/{id}/columns[/{cid}]` | ustun qo'shish / tur+config (tur o'zgarishi qoidalari, ishlatilgan select variantini himoya) / o'chirish (kalitni barcha qatorlardan olib tashlaydi) |
| POST | `/api/tables/{id}/columns/reorder` | ustunlar tartibi |
| GET/POST | `/api/tables/{id}/rows` | sahifalangan qatorlar (`?sort=key:asc` `?q=`) / qator qo'shish (ustunlarga qarab tekshiriladi) |
| POST | `/api/tables/{id}/rows/bulk` | ommaviy (CSV) import — `{rows:[...]}`, yaroqlilar qo'shiladi, xatolilar `{index,errors}` bilan qaytadi (max 1000) |
| PATCH/DELETE | `/api/tables/{id}/rows/{rid}` | qatorni birlashtirib yangilash (`expected_updated_at` → 409 optimistik qulf) / o'chirish (revizionda snapshot) |
| GET | `/api/tables/{id}/rows/{rid}/revisions` | qator o'zgarishlar tarixi |
| POST | `/api/tables/{id}/rows/{rid}/revisions/{revid}/restore` | qatorni tanlangan reviziya holatiga tiklaydi (joriy ustunlarga qayta tekshiriladi) |

#### Eksport / yuklab olish (Squid uslubida)

| Metod | Yo'l | Tavsif |
|-------|------|--------|
| GET | `/api/tables/{id}/export?format=csv\|json` | sinxron yuklab olish (joriy `q`/`sort` bilan). xlsx → 400 |
| POST | `/api/tables/{id}/export/jobs?format=csv\|json\|xlsx` | fon job yaratadi (katta jadval / xlsx). Bir vaqtda `EXPORT_JOB_MAX_CONCURRENT` (3) dan ko'p → 429 |
| GET | `/api/tables/{id}/export/jobs` | jadvalning oxirgi eksport job'lari |
| GET | `/api/exports/{jid}` | job holati (`pending/running/done/failed/cancelled`, `row_count`, `checksum_sha256`, …) |
| POST | `/api/exports/{jid}/cancel` | ishlayotgan job'ni bekor qiladi (kooperativ) |
| GET | `/api/exports/{jid}/download` | tayyor faylni yuklaydi (auth), `downloaded_at`/`download_count` qayd etiladi |
| POST | `/api/exports/{jid}/share` \| `.../share/revoke` | vaqtli havola (`EXPORT_SHARE_TTL_HOURS`, DB'da faqat token hash) / bekor qilish |
| GET | `/api/exports/{jid}/shared?token=` | **autentifikatsiyasiz** yuklab olish (havola egasiga audit yoziladi) |

Tayyor fayllar `EXPORT_DIR` (dev: `sd_exports` vol · prod: `sdp_exports`); `EXPORT_KEEP_DAYS`
dan eskilari retention loop'da o'chadi. Audit: `export_created/downloaded/shared/
share_revoked/cancelled`. Frontend: `pages/tables/ExportDialog.tsx` (jadval sozlamalari
menyusi → "Eksport / yuklab olish").

Ustun turlari: `text`, `long_text`, `number` (min/max), `boolean`, `date`, `datetime`,
`select` / `multi_select` (rangli variantlar), `user`. Har turda `config.default`
(standart qiymat) qo'llab-quvvatlanadi. Qiymatlar `dynamic_rows.data` (JSONB) da;
tekshiruv API qatlamida (`app/services/dynamic_values.py`). Ustun yoki qator
o'zgarganda jadvalning `updated_at` yangilanadi.

**Frontend UX:** jadval yaratish oynasida ustun konstruktori + 5 tayyor shablon
(bo'sh / hodisalar / aktivlar / vazifalar / ruxsat so'rovlari). Grid — spreadsheet
uslubida: klaviatura navigatsiyasi (o'qlar, `Enter`/`F2` tahrir, `Del` tozalash,
`Tab`), pastda doimiy inline "yangi qator", ustunni sarlavhadan sudrab tartiblash,
`select` variantlarini sudrash, qatorni nusxalash, CSV import, **eksport oynasi**
(CSV/XLSX/JSON — sinxron yoki fon job + ulashish havolasi), reviziyani
tiklash. Umumiy komponentlar: `pages/tables/ColumnFields.tsx` (ustun qoralamasi),
`lib/tableTemplates.ts`, `lib/dynamic.ts` (`draftToColumnPayload`, CSV yordamchilari).

---

## Loyiha tuzilishi

```
SD/
├── docker-compose.yml           # dev (bind-mount, vite HMR, alohida portlar)
├── docker-compose.prod.yml      # prod (nginx :8090, backend/db yopiq)
├── docker-compose.tls.yml       # + Caddy (HTTPS, Let's Encrypt) — prod ustiga
├── .env.example  /  .env.prod.example   # (proksi + DOMAIN bloklari bilan)
├── deploy/
│   ├── vm-setup.sh              # ⚡ bir buyruqli VM o'rnatuvchi (.env.prod + up)
│   ├── vm-update.sh             # git pull + qayta build
│   ├── VM-DEPLOY.md             # to'liq VM runbook (0 dan HTTPS gacha)
│   ├── PROKSI-VA-VM.md          # internetsiz VM — proksi mexanizmi / air-gap
│   ├── Caddyfile                # docker-compose.tls.yml uchun
│   └── bundle.sh                # air-gap: image'larni bitta arxivga yig'ish
├── backend/
│   ├── app/
│   │   ├── config.py            # pydantic-settings
│   │   ├── database.py          # async engine + Base + get_db
│   │   ├── models/              # User, RefreshToken, AuditLog, Dynamic{Table,Column,Row,RowRevision}
│   │   ├── schemas/             # Pydantic I/O modellar (auth, user, audit, dynamic)
│   │   ├── core/
│   │   │   ├── security.py      # bcrypt hash + JWT (tv claim) + refresh token
│   │   │   ├── passwords.py     # yagona parol siyosati + generator
│   │   │   └── audit.py         # audit log yordamchisi
│   │   ├── services/
│   │   │   ├── auth_service.py     # login oqimi, lockout, rotation, reuse detection, cleanup
│   │   │   ├── dynamic_service.py  # slug, ustun kaliti, tur o'zgarishi qoidalari
│   │   │   └── dynamic_values.py   # qator qiymatlari tekshiruvi/normallashtirish, config
│   │   ├── api/
│   │   │   ├── deps.py          # get_current_user (tv tekshiruvi), require_role, can_{read,write}_section
│   │   │   ├── auth.py          # /auth/*
│   │   │   ├── users.py         # /users/me, /users/directory
│   │   │   ├── admin.py         # /admin/*  (pagination bilan)
│   │   │   ├── tables.py        # /tables/*  (dinamik jadval CRUD)
│   │   │   └── sections.py      # /soc, /dlp placeholder
│   │   └── main.py             # SecurityHeaders middleware + retention lifespan
│   ├── alembic/versions/        # 0001_initial, 0002_hardening, 0003_dynamic_tables
│   ├── scripts/seed_superadmin.py
│   ├── tests/                   # pytest (37 ta: auth 20 + dinamik jadval 17)
│   └── entrypoint.sh
└── frontend/
    ├── Dockerfile          # dev (vite)
    ├── Dockerfile.prod     # prod (build → nginx)
    ├── nginx.conf          # SPA fallback + /api, /health proxy
    └── src/
        ├── lib/                 # api (axios + refresh interceptor), types, utils (+ testlar)
        ├── context/AuthContext.tsx
        ├── components/
        │   ├── ui/              # shadcn uslubidagi primitives
        │   ├── ProtectedRoute.tsx  (+ test)
        │   ├── ErrorBoundary.tsx
        │   └── AppShell.tsx     # sidebar layout + sahifa o'tish animatsiyasi
        ├── test/setup.ts        # vitest sozlamasi
        └── pages/
            ├── LoginPage.tsx
            ├── ChangePasswordPage.tsx
            ├── superadmin/      # Dashboard, Users, AuditLogs, CreateUserDialog, ResetPasswordDialog
            ├── tables/          # TablesListPage, TableGridPage (spreadsheet grid), ColumnFields (umumiy),
            │                    #   NewTable/Column/NewRow/Import/RowHistory dialoglari, cells (display + editorlar)
            └── sections.tsx     # SOC / DLP / Viewer placeholder
```

---

## Testlar

### Backend (`pytest`) — 37 ta test

Alohida bo'sh PostgreSQL bazasini talab qiladi:

```bash
cd backend
pip install -r requirements-dev.txt

# tez yo'l — bir martalik test DB konteyneri
docker run -d --name sd_pg_test -e POSTGRES_USER=soc -e POSTGRES_PASSWORD=soc \
  -e POSTGRES_DB=soc_platform_test -p 55433:5432 postgres:16-alpine

DATABASE_URL="postgresql+asyncpg://soc:soc@localhost:55433/soc_platform_test" \
JWT_SECRET_KEY="test" pytest -q
```

`tests/test_auth_flow.py` (20) qamrovi: login / `/users/me`, majburiy parol
almashtirish himoyalangan endpointni bloklashi, SOC↔DLP RBAC izolyatsiyasi, viewer
read-only, urinishlar limiti (lockout), refresh rotation + logout, **token reuse
detection**, **parol o'zgarishi / block eski access tokenni darhol yaroqsiz qilishi**,
**admin parolni tiklash**, zaif parol rad etilishi, foydalanuvchi ro'yxati
pagination, o'z hisobiga amal qila olmaslik, boshqa super_adminni boshqarish,
xavfsizlik header'lari, audit yozuvlari.

`tests/test_dynamic_tables.py` (17) qamrovi: jadval yaratish ruxsatlari (bo'lim
bo'yicha), ustun config validatsiyasi, qator CRUD + har turdagi qiymat tekshiruvi
(majburiy, noma'lum kalit, yaroqsiz select/user), qator tarixi (revisions),
**reviziyani tiklash** (ruxsat + yangi snapshot), **ommaviy import** (yaroqli/xato
ajratish), **row o'zgarishida jadval `updated_at`**, ustun o'chirishda kalitni
qatorlardan olib tashlash, tur o'zgarishi qoidalari (bo'sh jadval), ishlatilayotgan
select variantini himoya, bo'lim izolyatsiyasi, viewer read-only, pagination + sort
+ search, optimistik qulf (409), arxiv yozishni bloklashi, qattiq o'chirish faqat
super_admin, slug to'qnashuvi, `/users/directory`.

### Frontend (`vitest`) — 10 ta test

```bash
cd frontend
npm install
npm test
```

`apiError` xatolik ajratishi, `cn` / `relativeTime` yordamchilari va `ProtectedRoute`
yo'naltirish mantig'i (loading / anonim / majburiy parol / rol mos emas / ruxsat).

---

## Ishlab chiqarish uchun eslatmalar

- **Prod stek tayyor:** `docker-compose.prod.yml` (yuqoridagi "Ishlab chiqarish —
  bitta port `:8090`" bo'limiga qarang). nginx SPA build'ni beradi + `/api` proxy;
  `backend`/`db` host'ga ochilmaydi.
- `.env.prod` da kuchli `JWT_SECRET_KEY` (`openssl rand -hex 32`), `POSTGRES_PASSWORD`,
  `SUPERADMIN_PASSWORD`. TLS ortida `COOKIE_SECURE=true` (shунda `HSTS` ham yoqiladi).
- `docker-compose.yml` dagi `volumes` (bind mount) va frontend dev-server faqat
  development uchun.
- PostgreSQL uchun tashqi managed instance va backup siyosati tavsiya etiladi
  (prod volume: `sd-prod_sdp_db_data`).
- **Ma'lum cheklov (dizayn qarori):** access token 30 daqiqa amal qiladi va oddiy
  `logout` faqat refresh tokenni bekor qiladi. Xavfsizlik uchun muhim hodisalar
  (parol o'zgarishi, block) `token_version` orqali access tokenni ham darhol
  yaroqsiz qiladi; oddiy logout uchun qisqa TTL yetarli deb hisoblanadi.
- Retention muddatlarini (`AUDIT_RETENTION_DAYS`, `REFRESH_TOKEN_RETENTION_DAYS`,
  `CLEANUP_INTERVAL_HOURS`) tashkilot siyosatiga moslang. `AUDIT_RETENTION_DAYS=0`
  — audit yozuvlarini cheksiz saqlaydi.
