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


def die_password(err: str) -> None:
    sys.stderr.write(
        "\n"
        "======================================================================\n"
        "  XATO: PostgreSQL autentifikatsiyasi muvaffaqiyatsiz.\n"
        "  (" + err + ")\n"
        "\n"
        "  Sabab: `db` ma'lumotlar volume'i BOSHQA parol bilan yaratilgan.\n"
        "  Postgres parolni FAQAT birinchi ishga tushishda (bo'sh volume'da)\n"
        "  o'rnatadi. Keyin POSTGRES_PASSWORD ni o'zgartirsangiz DB'dagi\n"
        "  haqiqiy parol o'zgarmaydi, backend esa yangi parol bilan urinadi.\n"
        "  Ko'pincha sabab: `.env.prod` bilan / usiz oralab ishga tushirish.\n"
        "\n"
        "  YECHIM A - ma'lumot saqlanadi (DB parolini hozirgisiga tenglash).\n"
        "  <PAROL> = .env.prod dagi POSTGRES_PASSWORD (yo'q bo'lsa: sentinel):\n"
        "    docker compose -f docker-compose.prod.yml --env-file .env.prod \\\n"
        "      exec db psql -U soc -d postgres \\\n"
        "      -c \"ALTER USER soc PASSWORD '<PAROL>';\"\n"
        "    docker compose -f docker-compose.prod.yml --env-file .env.prod up -d\n"
        "\n"
        "  YECHIM B - BARCHA DB ma'lumoti o'chadi:\n"
        "    docker compose -f docker-compose.prod.yml --env-file .env.prod down\n"
        "    docker volume rm sd-prod_sdp_db_data\n"
        "    docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build\n"
        "======================================================================\n"
    )
    sys.exit(1)


async def wait():
    last = None
    for i in range(60):
        try:
            conn = await asyncpg.connect(url, timeout=5)
            await conn.close()
            print("==> PostgreSQL tayyor.")
            return
        except asyncpg.PostgresError as e:
            # Parol / rol xatosi — kutish behuda, darrov tushunarli xabar bilan chiqamiz
            msg = str(e).lower()
            if (
                "password authentication failed" in msg
                or "no password supplied" in msg
                or "role" in msg and "does not exist" in msg
            ):
                die_password(str(e))
            # boshqa server xatolari (masalan "starting up") — qayta urinamiz
            last = e
            print(f"   ... ({i + 1}/60) {e}")
            await asyncio.sleep(2)
        except (OSError, asyncio.TimeoutError) as e:
            # server hali ko'tarilmagan / port yopiq — qayta urinamiz
            last = e
            print(f"   ... ({i + 1}/60) {e}")
            await asyncio.sleep(2)
    sys.stderr.write(f"XATO: PostgreSQL'ga ulanib bo'lmadi (oxirgi xato: {last})\n")
    sys.exit(1)


asyncio.run(wait())
PY

echo "==> Alembic migratsiyalar..."
if ! alembic upgrade head; then
  echo "XATO: migratsiya muvaffaqiyatsiz — yuqoridagi xatoga qarang." >&2
  exit 1
fi

echo "==> Super admin seed..."
python -m scripts.seed_superadmin || true

echo "==> Ilova ishga tushirilmoqda..."
exec "$@"
