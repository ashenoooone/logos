#!/usr/bin/env bash
# Локальная разработка: mailpit в Docker, backend (uvicorn --reload) и frontend (vite) на хосте.
# Ctrl+C останавливает оба процесса. Тестовый админ admin/admin — миграцией 0008
# при первом запуске; отключить: LOGOS_DEV_ADMIN=0 scripts/dev.sh
# Демо-данные (менеджеры, диалоги, бот) — миграцией 0009 на пустой базе;
# отключить: LOGOS_DEMO_SEED=0 scripts/dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]; then
  . "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  nvm use "$(cat frontend/.nvmrc)" >/dev/null
fi

# Python с python.org на macOS без CA-бандла не проверяет TLS (Bot API, SMTP);
# берём системный бандл, если свой не задан.
if [ -z "${SSL_CERT_FILE:-}" ] && [ -f /etc/ssl/cert.pem ]; then
  export SSL_CERT_FILE=/etc/ssl/cert.pem
fi

docker compose up -d mailpit
uv sync --locked
LOGOS_DEV_ADMIN="${LOGOS_DEV_ADMIN:-1}" LOGOS_DEMO_SEED="${LOGOS_DEMO_SEED:-1}" \
  uv run alembic upgrade head
(cd frontend && pnpm install --frozen-lockfile)

# Vite-прокси подменяет Host на адрес бэкенда, поэтому origin фронта разрешаем явно.
export LOGOS_ALLOWED_ORIGINS="${LOGOS_ALLOWED_ORIGINS:-http://localhost:5173}"

trap 'kill 0' EXIT
uv run uvicorn logos_backend.app:app --host 127.0.0.1 --port 8000 --workers 1 --reload &
(cd frontend && pnpm dev) &

echo "Приложение: http://localhost:5173  Mailpit: http://localhost:8026"
wait
