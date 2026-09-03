#!/usr/bin/env bash
# Sentinel — yangi versiyaga o'tish (git pull + qayta build). Ma'lumotlar saqlanadi.
set -euo pipefail
cd "$(dirname "$0")/.."

DC="docker compose"; docker compose version >/dev/null 2>&1 || DC="docker-compose"

git pull --ff-only
$DC -f docker-compose.prod.yml --env-file .env.prod up -d --build
echo "==> Yangilandi. Migratsiyalar konteyner startida avtomatik qo'llandi."
