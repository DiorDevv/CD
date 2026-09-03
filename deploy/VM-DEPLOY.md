# VM'da to'liq ishga tushirish (production, `:8090`)

Boshdan oxirigacha. VM — Ubuntu/Debian, Squid proksi ortida (to'g'ridan internet yo'q).
Almashtiring: `PROXY_HOST:3128` (Squid), `<VM-IP>` (VM manzili).

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
sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(openssl rand -hex 32)|" .env.prod
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

## 13. (Ixtiyoriy) Domen + HTTPS

`:8090` oldiga TLS tugatuvchi qo'ying — host nginx + certbot yoki Caddy.

1. DNS: `sentinel.example.com` → `<VM-IP>` (A yozuv)
2. Host'da reverse-proxy (namuna: Caddy — avtomatik Let's Encrypt):

   ```bash
   sudo apt-get install -y caddy
   sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
   sentinel.example.com {
       reverse_proxy 127.0.0.1:8090
   }
   EOF
   sudo systemctl restart caddy
   ```
3. `.env.prod` da `COOKIE_SECURE=true` qiling va qayta ishga tushiring:

   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```
4. Endi faqat `https://sentinel.example.com`. 8090 portini tashqaridan yoping
   (`sudo ufw delete allow 8090/tcp`), Caddy 80/443 ni ishlatadi.

---

## Muammolar

| Belgi | Sabab / yechim |
|-------|----------------|
| `docker pull` osilib qoladi | Qatlam 1 (demon proksi) qilinmagan — 3-bo'lim |
| build'da `pip`/`npm` timeout | `.env.prod` da `HTTP_PROXY/HTTPS_PROXY` bo'sh yoki noto'g'ri |
| backend `db`ga ulanmaydi | `NO_PROXY` da `db` yo'q — 5-bo'limдаги qiymatni qo'ying |
| login bo'ladi-yu, darhol chiqib ketadi | HTTPS ortida `COOKIE_SECURE=false` qolgan → `true` qiling |
| `POSTGRES_PASSWORD ... belgilanishi shart` | `.env.prod` da `POSTGRES_PASSWORD` bo'sh |
| `sdp_web` unhealthy, lekin sayt ochiladi | eski build — `up -d --build` qayta qiling |
