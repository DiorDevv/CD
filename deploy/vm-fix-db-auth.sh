#!/usr/bin/env bash
# ============================================================
#  Sentinel — DB "password authentication failed for user" ni
#  BITTA buyruqda tuzatish.
#
#  Qachon: `sdp_backend` unhealthy, loglarda
#    "password authentication failed for user "soc""
#  Sabab: Postgres `sdp_db_data` volume'i BOSHQA parol bilan yaratilgan
#  (Postgres parolni faqat bo'sh volume'da, birinchi startda o'rnatadi).
#
#  Nima qiladi (MA'LUMOT SAQLANADI, volume o'chirilmaydi):
#    1. `.env.prod` dagi POSTGRES_USER/PASSWORD ni aniqlaydi (yo'q bo'lsa: soc/sentinel)
#    2. Faqat `db` ni ko'taradi va tayyor bo'lishini kutadi
#    3. DB ichidagi foydalanuvchi parolini o'sha qiymatga tenglaydi (ALTER USER)
#    4. Butun tizimni qayta quradi: `up -d --build`
#    5. Holat + backend loglarini ko'rsatadi
#
#  Foydalanish (repo ildizidan yoki deploy/ ichidan):
#    ./deploy/vm-fix-db-auth.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

DC="docker compose"; docker compose version >/dev/null 2>&1 || DC="docker-compose"
CF="-f docker-compose.prod.yml"
ENVF=""; [ -f .env.prod ] && ENVF="--env-file .env.prod"

envval() {  # envval KEY DEFAULT  — .env.prod dan qiymat oladi (o'rovchi tirnoqlarsiz)
  local v=""
  [ -f .env.prod ] && v="$(grep -E "^$1=" .env.prod | head -1 | cut -d= -f2- | tr -d '\042\047')"
  printf '%s' "${v:-$2}"
}

DB_USER="$(envval POSTGRES_USER soc)"
DB_PASS="$(envval POSTGRES_PASSWORD sentinel)"

echo "==> Mo'ljallangan: user='$DB_USER'  (compose $ENVF)"

echo "==> Yangi versiyani olishga urinamiz (git pull)..."
git pull --ff-only || echo "   (git pull o'tkazib yuborildi — muhim emas)"

echo "==> Faqat 'db' ko'tarilmoqda..."
$DC $CF $ENVF up -d db

echo "==> 'db' tayyor bo'lishini kutamiz..."
for _ in $(seq 1 45); do
  $DC $CF $ENVF exec -T db pg_isready -U "$DB_USER" >/dev/null 2>&1 && break
  sleep 2
done

echo "==> '$DB_USER' parolini moslashtiramiz (ALTER USER)..."
SQL="ALTER USER \"$DB_USER\" PASSWORD '$DB_PASS';"
if ! $DC $CF $ENVF exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d postgres -c "$SQL" 2>/dev/null; then
  echo "   '$DB_USER' bilan bo'lmadi — 'postgres' superuser bilan urinamiz..."
  $DC $CF $ENVF exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "$SQL"
fi
echo "   OK."

echo "==> Butun tizim qayta quriladi va ishga tushiriladi..."
$DC $CF $ENVF up -d --build

echo
echo "==> Holat:"
$DC $CF $ENVF ps
echo
echo "==> Backend loglari (oxirgi 25 qator):"
$DC $CF $ENVF logs --tail=25 backend || true
echo
echo "Tayyor. 'sdp_backend' healthy bo'lishi kerak. Sayt: http://<host>:${WEB_PORT:-8090}"
