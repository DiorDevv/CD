# Internetsiz VM — Squid proksi orqali (yoki to'liq air-gap)

VM to'g'ridan-to'g'ri internetga chiqa olmaydi. Chiqish Squid (yoki boshqa HTTP)
proksi orqali. Muammo 3 qatlamda hal qilinadi — uchalasiga **bir xil**
`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` beriladi. Proksi umuman bo'lmasa —
oxiridagi `docker save` / `docker load` yo'li.

`PROXY_HOST:3128` — Squid manzilingiz bilan almashtiring.

---

## Qatlam 1 — Docker demoni (base image'larni `docker pull` qilish)

`python:3.11-slim`, `node:20-alpine`, `nginx:1.27-alpine`, `postgres:16-alpine` —
bularni **Docker demoni** tortadi. Demon `.env` ni ham, `build-arg` ni ham
o'qimaydi — unga alohida proksi beriladi:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf <<'EOF'
[Service]
Environment="HTTP_PROXY=http://PROXY_HOST:3128"
Environment="HTTPS_PROXY=http://PROXY_HOST:3128"
Environment="NO_PROXY=localhost,127.0.0.1,::1,*.internal"
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

Tekshirish:

```bash
docker pull hello-world      # ishlashi kerak
```

---

## Qatlam 2 — Build vaqti (`apt`, `pip`, `npm` — `RUN` ichida)

Bu loyihada allaqachon ulangan:

- **`backend/Dockerfile`, `frontend/Dockerfile`, `frontend/Dockerfile.prod`** —
  `ARG HTTP_PROXY/HTTPS_PROXY/NO_PROXY` qabul qiladi va `ENV` ga o'tkazadi
  (`npm` uchun qo'shimcha `npm_config_proxy` / `npm_config_https_proxy` —
  npm standart env'ni har doim hurmat qilmaydi).
- **`docker-compose.yml` va `docker-compose.prod.yml`** — `.env` dagi qiymatni
  `build.args` ga uzatadi.

Sizga faqat `.env` (yoki `.env.prod`) ni to'ldirish qoladi:

```ini
HTTP_PROXY=http://PROXY_HOST:3128
HTTPS_PROXY=http://PROXY_HOST:3128
NO_PROXY=localhost,127.0.0.1,::1,db,backend,web
```

> **`NO_PROXY` ga compose servis nomlarini (`db`, `backend`, `web`) qo'shish
> SHART** — aks holda konteynerlararo trafik ham (masalan backend → `db:5432`)
> proksiga yuboriladi va buziladi.

So'ng odatiy tarzda:

```bash
# dev
docker compose up -d --build

# prod (:8090)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

---

## Qatlam 3 — Runtime (konteyner ishlab turганда)

**SD backend'i ishlab turganда internetga chiqmaydi** (Telegram/Sentry/tashqi
API yo'q) — shu sabab proksi runtime image'ga **baked qilinmaydi**
(`Dockerfile.prod` da nginx bosqichiga proksi umuman berilmaydi).

Kelajakda tashqi chaqiruv qo'shilsa — `docker-compose*.yml` da o'sha servisning
`environment:` bo'limiga `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` qo'shing (image'ni
qayta build qilmasdan).

---

## Muqobil — to'liq air-gap (proksi ham yo'q)

Internetli mashinada build qilib, VM ga fayl orqali tashiysiz.

**Internetli mashinada:**

```bash
# prod image'lar
docker compose -f docker-compose.prod.yml --env-file .env.prod build

docker save \
  sd-prod-backend sd-prod-web \
  postgres:16-alpine \
  | gzip > sentinel-images.tar.gz
```

(dev uchun: `sd-backend sd-frontend node:20-alpine postgres:16-alpine`)

**VM ga ko'chirib:**

```bash
gunzip -c sentinel-images.tar.gz | docker load

# .env.prod tayyorlang (JWT_SECRET_KEY, parollar), so'ng build/pull'siz:
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build
```

> `--no-build` — compose faqat mavjud image'lardan ishga tushiradi, hech narsa
> tortmaydi/build qilmaydi. `image:` nomlari (`sd-prod-backend`, `sd-prod-web`)
> `docker load` qilingan nomlarga mos bo'lishi kerak — compose fayllarida
> shunday belgilangan.

---

## Xulosa

| Qatlam | Qayerda | Nima uchun |
|--------|---------|-----------|
| 1. Demon | `/etc/systemd/system/docker.service.d/http-proxy.conf` | `docker pull` base image'lar |
| 2. Build | `.env` → compose `build.args` → Dockerfile `ARG/ENV` | `apt`, `pip`, `npm` |
| 3. Runtime | (SD'da kerak emas) compose `environment:` | konteyner tashqi chaqiruvlari |
| Air-gap | `docker save` / `docker load` + `up --no-build` | proksi ham bo'lmasa |
