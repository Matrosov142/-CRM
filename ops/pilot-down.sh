#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env.pilot -f compose.pilot.yml down
echo "Контейнеры остановлены. Данные в именованных томах сохранены."
