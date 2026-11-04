#!/usr/bin/env bash
# Поднимает mailpit + backend + frontend в Docker Compose.
# Тестовый админ admin/admin создаётся миграцией 0008 при первом запуске;
# отключить: LOGOS_DEV_ADMIN=0 scripts/up.sh
# Демо-данные (менеджеры, диалоги, бот) — миграцией 0009 на пустой базе;
# отключить: LOGOS_DEMO_SEED=0 scripts/up.sh
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose build
docker compose run --rm -e LOGOS_DEV_ADMIN="${LOGOS_DEV_ADMIN:-1}" \
  -e LOGOS_DEMO_SEED="${LOGOS_DEMO_SEED:-1}" \
  -e LOGOS_DEMO_BOT_TOKEN="${LOGOS_DEMO_BOT_TOKEN:-}" backend alembic upgrade head
docker compose up -d

echo "Приложение: http://localhost:8080"
echo "Mailpit:    http://localhost:8026"
