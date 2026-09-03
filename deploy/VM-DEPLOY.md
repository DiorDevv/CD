# VM'da to'liq ishga tushirish (production, `:8090`)

Boshdan oxirigacha. VM — Ubuntu/Debian, Squid proksi ortida (to'g'ridan internet yo'q).
Almashtiring: `PROXY_HOST:3128` (Squid), `<VM-IP>` (VM manzili).

---

## Hammasi Docker orqalimi?

**Ha — deyarli hammasi.** Baza, backend, frontend/nginx, hatto HTTPS (Caddy) —
barchasi `docker compose`. Host'da faqat quyidagilar qoladi:

| Host ishi | Majburiymi? | Chetlab o'tish |
|-----------|-------------|----------------|
| Docker + compose plugin o'rnatish | Ha (yagona prerekvizit) | — |
| Docker demoni proksisi (`http-proxy.conf`) | Internetsiz VM'da base image tortish uchun | **Air-gap bundle** — B yo'li (pastda), hech qanday proksi shart emas |
| `openssl` (JWT kaliti) | Yo'q | konteynerда: `docker run --rm alpine sh -c "apk add -q openssl && openssl rand -hex 32"` |
| Firewall / cloud security group | Portni tashqariga ochish uchun | — (Docker'dan tashqarida, provayder ishi) |

Ikki yo'l:
- **A — build VM'da** (Squid proksi bor): 1–8 bo'limlar.
- **B — air-gap bundle** (proksi ham yo'q): internetli mashinada `deploy/bundle.sh`
  → arxivni VM'ga → `docker load` → `up --no-build`. "B yo'li" bo'limiga qarang.

---

## 0. VM ga ulanish

```bash
ssh foydalanuvchi@<VM-IP>
```

---

## 1. Proksi — apt uchun (Docker'ni o'rnatish kerak bo'lsa)

```bash
sudo tee /etc/apt/apt.conf.d/95proxy >/dev/null <<'EOF'
Acquire::http::Proxy  "http://PROXY_HOST:3128";
Acquire::https::Proxy "http://PROXY_HOST:3128";
EOF
```

Shell uchun ham (git clone, openssl kabi):

```bash
echo 'export http_proxy=http://PROXY_HOST:3128
export https_proxy=http://PROXY_HOST:3128
export no_proxy=localhost,127.0.0.1,::1' | sudo tee /etc/profile.d/proxy.sh
source /etc/profile.d/proxy.sh
```

---

## 2. Docker + Compose (o'rnatilmagan bo'lsa)

```bash
docker --version && docker compose version   # bo'lsa — bu bo'limни o'tkazing

sudo apt-get update
sudo apt-get install -y docker.io docker-buildx docker-compose-v2 git openssl

sudo systemctl enable --now docker
sudo usermod -aG docker $USER      # sudosiz ishlash uchun
# shu yerda tizimdan chiqib qayta kiring (yoki: newgrp docker)
```

---

## 3. Proksi — Docker demoni uchun (Qatlam 1)

`docker pull` base image'larni (`postgres:16-alpine`, `python:3.11-slim`,
`node:20-alpine`, `nginx:1.27-alpine`) tortadi — demon `.env` ni o'qimaydi:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf >/dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=http://PROXY_HOST:3128"
Environment="HTTPS_PROXY=http://PROXY_HOST:3128"
Environment="NO_PROXY=localhost,127.0.0.1,::1,*.internal"
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker

docker pull hello-world     # ishlashi kerak
```

> **Proksi umuman bo'lmasa** (air-gap): bu qadamni tashlab, `deploy/PROKSI-VA-VM.md`
> dagi `docker save` / `docker load` yo'lidan boring.

---

## 4. Kodni olish

```bash
cd ~
git clone https://github.com/DiorDevv/CD.git sentinel
cd sentinel
```

---

## 5. `.env.prod` — konfiguratsiya

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

**Majburiy almashtiriladigan qatorlar:**

| Qator | Qiymat |
|-------|--------|
| `POSTGRES_PASSWORD` | kuchli parol (kamida 16 belgi) |
| `DATABASE_URL` | ичидаги parolni ham yuqoridagiga moslang |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` natijasi |
| `SUPERADMIN_PASSWORD` | parol siyosati: ≥10 belgi, katta+kichik harf, raqam, bo'sh joysiz, `superadmin` so'zisiz |
| `HTTP_PROXY` / `HTTPS_PROXY` | `http://PROXY_HOST:3128` |
| `NO_PROXY` | `localhost,127.0.0.1,::1,db,backend,web` (o'zgartirmang) |
| `WEB_PORT` | `8090` (kerak bo'lsa boshqa) |
| `COOKIE_SECURE` | `false` (oddiy HTTP) · **HTTPS qo'ysangiz → `true`**, keyingi bo'limga qarang |

`JWT_SECRET_KEY` ni tez qo'yish:

```bash
# openssl bo'lsa:
sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(openssl rand -hex 32)|" .env.prod

# openssl yo'q bo'lsa — konteynerда:
KEY=$(docker run --rm python:3.11-slim python -c "import secrets;print(secrets.token_hex(32))")
sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$KEY|" .env.prod
```

---

## 6. Qurish va ishga tushirish

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Birinchi safar 3–6 daqiqa (proksi orqali `pip`/`npm`). Konteyner startida backend
avtomatik: PostgreSQL kutadi → `alembic upgrade head` → super admin seed.

---

## 7. Tekshirish

```bash
docker compose -f docker-compose.prod.yml ps
# uchalasi ham "Up (healthy)" bo'lishi kerak: sdp_db, sdp_backend, sdp_web

curl -fsS http://localhost:8090/health      # {"status":"ok","env":"prod"}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/     # 200
```

Loglar: `docker compose -f docker-compose.prod.yml logs -f`

---

## 8. Portni tashqariga ochish

```bash
sudo ufw allow 8090/tcp     # ufw yoqilgan bo'lsa
```

Bulutli VM bo'lsa — **security group / firewall** da ham 8090/TCP kirish ruxsatini
qo'shing. So'ng brauzerdan: **`http://<VM-IP>:8090`**

---

## 9. Birinchi kirish

1. `http://<VM-IP>:8090` → `superadmin` / `.env.prod` dagi `SUPERADMIN_PASSWORD`
2. Tizim majburiy parol almashtirishga yo'naltiradi → yangi parol → qayta kiring
3. "Foydalanuvchilar" bo'limidan SOC/DLP admin, viewer'lar yarating

---

## 10. Reboot'dan keyin

Hech narsa qilish shart emas — `restart: unless-stopped` + `systemctl enable docker`
tufayli VM qayta yuklanganда o'zi ko'tariladi.

---

## 11. Yangilash (yangi versiya)

```bash
cd ~/sentinel
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Migratsiyalar konteyner startida avtomatik. Ma'lumotlar `sdp_db_data`,
eksport fayllari `sdp_exports` volume'ida qoladi.

---

## 12. Zaxira (backup)

```bash
# baza
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U soc soc_platform | gzip > ~/backup-$(date +%F).sql.gz

# tiklash
gunzip -c ~/backup-YYYY-MM-DD.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U soc -d soc_platform
```

---

## 13. (Ixtiyoriy) Domen + HTTPS — **Docker orqali** (Caddy)

Host'ga hech narsa o'rnatmaysiz — `docker-compose.tls.yml` Caddy konteynerini
qo'shadi: 80/443 da turadi, DOMEN uchun avtomatik Let's Encrypt sertifikat oladi,
`web` (nginx) ga uzatadi. `web` ning `:8090` porti yopiladi — tashqariga faqat Caddy.

1. **DNS:** `sentinel.example.com` → `<VM-IP>` (A yozuv)
2. **Firewall:** 80 va 443 ochiq (`sudo ufw allow 80,443/tcp`), cloud SG da ham.
   VM internetdan ko'rinishi shart (ACME tekshiruvi uchun).
3. **`.env.prod`:**
   ```ini
   DOMAIN=sentinel.example.com
   COOKIE_SECURE=true
   CORS_ORIGINS=https://sentinel.example.com
   ```
4. **Ishga tushirish** (ikkала compose fayl bilan):
   ```bash
   docker compose -f docker-compose.prod.yml -f docker-compose.tls.yml \
     --env-file .env.prod up -d --build
   ```
5. `docker compose -f docker-compose.prod.yml -f docker-compose.tls.yml logs -f caddy`
   — sertifikat olinganini kuting. So'ng: **`https://sentinel.example.com`**.
   8090 ni tashqaridan yoping (`sudo ufw delete allow 8090/tcp`).

> Keyingi har `up`/`logs`/`down` da ikkала `-f` faylni ham bering.

---

## B yo'li — air-gap bundle (proksi umuman yo'q)

VM'da internet ham, Squid ham yo'q. Image'larni **internetli mashinada** yig'ib
fayl orqali tashiysiz. Docker demoni proksisi (3-bo'lim) **kerak emas**.

**Internetli mashinada** (repo klon qilingan):
```bash
./deploy/bundle.sh              # -> sentinel-bundle.tgz  (~300–400 MB)
```

**Arxivni VM'ga ko'chiring** (`scp sentinel-bundle.tgz foydalanuvchi@<VM-IP>:~/`),
so'ng VM'da:
```bash
gunzip -c ~/sentinel-bundle.tgz | docker load

git clone ... sentinel     # yoki repo'ni ham fayl orqali ko'chiring
cd sentinel
cp .env.prod.example .env.prod && nano .env.prod   # 5-bo'limдек to'ldiring
                                                   # HTTP_PROXY/HTTPS_PROXY — BO'SH qoldiring

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build
```
`--no-build` — hech narsa tortilmaydi/qurilmaydi, faqat `docker load` qilingan
image'lardan ishga tushadi. Keyin 7–9 bo'limlar bir xil.

HTTPS ham xohlasangiz: `docker compose -f docker-compose.prod.yml
-f docker-compose.tls.yml --env-file .env.prod up -d --no-build` (bundle `caddy`
image'ini ham o'z ichiga oladi).

---

## Muammolar

| Belgi | Sabab / yechim |
|-------|----------------|
| `docker pull` osilib qoladi | Docker demoni proksisi (3-bo'lim) qilinmagan — yoki B yo'li (air-gap) |
| build'da `pip`/`npm` timeout | `.env.prod` da `HTTP_PROXY/HTTPS_PROXY` bo'sh yoki noto'g'ri |
| backend `db`ga ulanmaydi | `NO_PROXY` da `db` yo'q — 5-bo'limдаги qiymatni qo'ying |
| login bo'ladi-yu, darhol chiqib ketadi | HTTPS ortida `COOKIE_SECURE=false` qolgan → `true` |
| `POSTGRES_PASSWORD ... belgilanishi shart` | `.env.prod` da `POSTGRES_PASSWORD` bo'sh |
| `sdp_web` unhealthy, lekin sayt ochiladi | eski build — `up -d --build` qayta qiling |
| Caddy sertifikat ololmaydi | 80/443 tashqaridan yopiq yoki DNS noto'g'ri; VM internetdan ko'rinmaydi (ACME) |
| `!reset` xato beradi (eski compose) | Docker Compose ≥ v2.24 kerak — `docker compose version` bilan tekshiring |
