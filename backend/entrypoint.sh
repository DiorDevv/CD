#!/usr/bin/env bash
set -e

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
