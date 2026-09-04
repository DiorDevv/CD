#!/usr/bin/env bash
# ============================================================
#  Sentinel — VM'da bir buyruqli o'rnatuvchi (HTTP, :8090)
#
#  Foydalanish (repo ildizidan yoki deploy/ ichidan):
#    ./deploy/vm-setup.sh                               # proksi Docker demonidan avtomatik olinadi
#    ./deploy/vm-setup.sh --proxy http://10.0.0.5:3128  # proksini qo'lda berish
#    ./deploy/vm-setup.sh --port 9000 --admin-pass 'Mening_Parolim1'
#    ./deploy/vm-setup.sh --no-build                    # air-gap: oldindan `docker load` qilingan
#
#  Nima qiladi:
#    1. Docker + compose borligini tekshiradi
#    2. Proksi: --proxy berilmasa /etc/systemd/system/docker.service.d/http-proxy.conf
#       dan avtomatik oladi; ./.env ga yozadi (compose build shu orqali chiqadi)
#    3. .env.prod ni yaratadi (yo'q bo'lsa) — tasodifiy JWT/DB/admin parollari
#    4. docker compose -f docker-compose.prod.yml up -d --build
#    5. /health ni kutadi va URL + kirish ma'lumotlarini chop etadi
#
#  .env / .env.prod ALLAQACHON bo'lsa — mos qatorlar yangilanadi, qolgani saqlanadi.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PROXY=""
PORT="8090"
ADMIN_PASS=""
BUILD_FLAG="--build"

while [ $# -gt 0 ]; do
  case "$1" in
    --proxy)      PROXY="$2"; shift 2 ;;
    --port)       PORT="$2"; shift 2 ;;
    --admin-pass) ADMIN_PASS="$2"; shift 2 ;;
    --no-build)   BUILD_FLAG=""; shift ;;
    -h|--help)    sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "Noma'lum parametr: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mXATO:\033[0m %s\n' "$*" >&2; exit 1; }

# --proxy berilmasa — Docker demoni konfiguratsiyasidan avtomatik topamiz
PROXY_AUTO=0
DAEMON_PROXY_FILE=/etc/systemd/system/docker.service.d/http-proxy.conf
if [ -z "$PROXY" ] && [ -r "$DAEMON_PROXY_FILE" ]; then
  PROXY="$(sed -n 's/.*"HTTP_PROXY=\([^"]*\)".*/\1/p' "$DAEMON_PROXY_FILE" | head -1)"
  [ -n "$PROXY" ] && { PROXY_AUTO=1; say "Proksi Docker demoni konfiguratsiyasidan olindi: $PROXY"; }
fi

# --- 1. Docker ------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker o'rnatilmagan. O'rnating:
  sudo apt-get update && sudo apt-get install -y docker.io docker-buildx docker-compose-v2 git
  sudo systemctl enable --now docker && sudo usermod -aG docker \$USER   # keyin qayta login"

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  die "'docker compose' topilmadi. O'rnating: sudo apt-get install -y docker-compose-v2"
fi
docker info >/dev/null 2>&1 || die "Docker demoniga ulanib bo'lmadi (sudo kerakmi? yoki 'newgrp docker')."

gen_hex() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex "$1"
  else docker run --rm python:3.11-slim python -c "import secrets;print(secrets.token_hex($1))"
  fi
}

# --- 2. Proksi: (a) demon — image tortish uchun; (b) ./.env — build uchun ---
if [ -n "$PROXY" ]; then
  if [ "$PROXY_AUTO" = 0 ]; then
    say "Docker demoni proksisi sozlanmoqda ($PROXY)"
    sudo mkdir -p /etc/systemd/system/docker.service.d
    printf '[Service]\nEnvironment="HTTP_PROXY=%s"\nEnvironment="HTTPS_PROXY=%s"\nEnvironment="NO_PROXY=localhost,127.0.0.1,::1"\n' \
      "$PROXY" "$PROXY" | sudo tee "$DAEMON_PROXY_FILE" >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl restart docker
    sleep 2
  fi

  # compose ./.env ni avtomatik o'qiydi -> build.args ga uzatiladi.
  # Shundan keyin oddiy `docker compose ... up -d --build` ham ishlaydi.
  say "./.env ga proksi yozilmoqda (build uchun)"
  touch "$ROOT/.env"
  e() {
    if grep -q "^$1=" "$ROOT/.env" 2>/dev/null; then
      sed -i "s|^$1=.*|$1=$2|" "$ROOT/.env"
    else
      printf '%s=%s\n' "$1" "$2" >> "$ROOT/.env"
    fi
  }
  e HTTP_PROXY  "$PROXY"
  e HTTPS_PROXY "$PROXY"
  e NO_PROXY    "localhost,127.0.0.1,::1,db,backend,web,frontend"
fi

# --- 3. .env.prod -----------------------------------------------------
GENERATED=0
if [ -f "$ROOT/.env.prod" ]; then
  say ".env.prod allaqachon mavjud — o'zgartirilmaydi"
else
  say ".env.prod yaratilmoqda (tasodifiy parollar bilan)"
  cp "$ROOT/.env.prod.example" "$ROOT/.env.prod"
  GENERATED=1

  JWT="$(gen_hex 32)"
  PGPASS="$(gen_hex 16)"
  if [ -z "$ADMIN_PASS" ]; then
    ADMIN_PASS="Sentinel-$(gen_hex 4)-Aa1"   # parol siyosatiga mos: katta+kichik+raqam, ≥10
  fi

  s() { sed -i "s|^$1=.*|$1=$2|" "$ROOT/.env.prod"; }
  s JWT_SECRET_KEY       "$JWT"
  s POSTGRES_PASSWORD    "$PGPASS"
  s DATABASE_URL         "postgresql+asyncpg://soc:${PGPASS}@db:5432/soc_platform"
  s SUPERADMIN_PASSWORD  "$ADMIN_PASS"
  s WEB_PORT             "$PORT"
  s COOKIE_SECURE        "false"
  if [ -n "$PROXY" ]; then
    s HTTP_PROXY  "$PROXY"
    s HTTPS_PROXY "$PROXY"
    s NO_PROXY    "localhost,127.0.0.1,::1,db,backend,web"
  fi
  chmod 600 "$ROOT/.env.prod"
fi

# --- 4. Ishga tushirish --------------------------------------------------
say "Konteynerlar qurilmoqda va ko'tarilmoqda (birinchi safar bir necha daqiqa)"
# shellcheck disable=SC2086
$DC -f docker-compose.prod.yml --env-file .env.prod up -d $BUILD_FLAG

# --- 5. Health kutish -------------------------------------------------
say "Salomatlik tekshiruvi kutilmoqda..."
OK=0
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then OK=1; break; fi
  sleep 2
done
[ "$OK" = 1 ] || die "Backend 3 daqiqada tayyor bo'lmadi. Loglar: $DC -f docker-compose.prod.yml logs -f"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; IP="${IP:-localhost}"

printf '\n\033[1;32m✓ Tayyor.\033[0m\n\n'
printf '  URL:        http://%s:%s\n' "$IP" "$PORT"
printf '  Foydalanuvchi: superadmin\n'
if [ "$GENERATED" = 1 ]; then
  printf '  Parol:      %s\n' "$ADMIN_PASS"
  printf '              (birinchi kirishда almashtirish so'\''raladi; .env.prod da ham saqlangan)\n'
else
  printf '  Parol:      .env.prod dagi SUPERADMIN_PASSWORD\n'
fi
printf '\n  Portni oching:  sudo ufw allow %s/tcp   (+ cloud security group)\n' "$PORT"
printf '  Loglar:         %s -f docker-compose.prod.yml logs -f\n' "$DC"
printf '  Yangilash:      ./deploy/vm-update.sh\n\n'
