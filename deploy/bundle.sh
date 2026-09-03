#!/usr/bin/env bash
# ============================================================
#  Air-gap bundle — internetli mashinada prod image'larni bitta arxivga yig'adi.
#  VM'da (internet/proksi shart emas):
#     gunzip -c sentinel-bundle.tgz | docker load
#     docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build
#  (HTTPS bilan: yuqoridagiga  -f docker-compose.tls.yml  qo'shing)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-sentinel-bundle.tgz}"

# compose faqat o'zgaruvchi interpolatsiyasi uchun POSTGRES_PASSWORD talab qiladi —
# build'ga ta'sir qilmaydi.
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-bundle-build-only}"

echo "==> Image'lar qurilmoqda (backend + web)..."
docker compose -f docker-compose.prod.yml build

echo "==> Base image'lar tortilmoqda..."
docker pull postgres:16-alpine
docker pull caddy:2-alpine      # HTTPS uchun; kerak bo'lmasa ham zarari yo'q

echo "==> Arxivlash: $OUT"
docker save sd-prod-backend sd-prod-web postgres:16-alpine caddy:2-alpine \
  | gzip > "$OUT"

echo "==> Tayyor: $OUT ($(du -h "$OUT" | cut -f1))"
echo "    VM'ga ko'chiring, so'ng:"
echo "      gunzip -c $OUT | docker load"
echo "      docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build"
