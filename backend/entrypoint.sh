#!/usr/bin/env bash
set -e

# ---------------------------------------------------------------------------
# Maxfiy qiymatlar berilmagan bo'lsa — bir marta generatsiya qilib, doimiy
# volume'ga (/data) saqlaymiz. Shu tufayli `.env` faylsiz ham ishlaydi.
# Aniq berilgan env qiymatlari (docker-compose / .env.prod) ustunlik qiladi.
# ---------------------------------------------------------------------------
SECRETS_DIR="${SECRETS_DIR:-/data}"
mkdir -p "$SECRETS_DIR" 2>/dev/null || true

if [ -z "${JWT_SECRET_KEY:-}" ]; then
  if [ ! -s "$SECRETS_DIR/jwt_secret" ]; then
    python -c "import secrets,pathlib; pathlib.Path('$SECRETS_DIR/jwt_secret').write_text(secrets.token_hex(32))"
    echo "==> JWT_SECRET_KEY avtomatik yaratildi: $SECRETS_DIR/jwt_secret"
  fi
  export JWT_SECRET_KEY="$(cat "$SECRETS_DIR/jwt_secret")"
fi

if [ -z "${SUPERADMIN_PASSWORD:-}" ]; then
  if [ ! -s "$SECRETS_DIR/superadmin_password" ]; then
    python -c "import secrets,pathlib; pathlib.Path('$SECRETS_DIR/superadmin_password').write_text('Sentinel-'+secrets.token_hex(4)+'-Aa1')"
  fi
  export SUPERADMIN_PASSWORD="$(cat "$SECRETS_DIR/superadmin_password")"
  echo "======================================================================"
  echo "  SUPER ADMIN:  ${SUPERADMIN_USERNAME:-superadmin} / ${SUPERADMIN_PASSWORD}"
  echo "  Keyin ko'rish:  docker compose exec backend cat $SECRETS_DIR/superadmin_password"
  echo "======================================================================"
fi

echo "==> PostgreSQL kutilmoqda..."
python - <<'PY'
import asyncio, os, sys
import asyncpg

url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

async def wait():
    for i in range(30):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            print("==> PostgreSQL tayyor.")
            return
        except Exception as e:
            print(f"   ... ({i+1}/30) {e}")
            await asyncio.sleep(1)
    print("XATO: PostgreSQL'ga ulanib bo'lmadi.", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PY

echo "==> Alembic migratsiyalar..."
alembic upgrade head

echo "==> Super admin seed..."
python -m scripts.seed_superadmin || true

echo "==> Ilova ishga tushirilmoqda..."
exec "$@"
