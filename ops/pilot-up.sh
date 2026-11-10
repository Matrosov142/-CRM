#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=".env.pilot"
command -v openssl >/dev/null || { echo "Нужен openssl для генерации секретов"; exit 1; }

if [[ ! -f "$ENV_FILE" ]]; then
  DB_ADMIN_PASSWORD="$(openssl rand -hex 32)"
  DB_OWNER_PASSWORD="$(openssl rand -hex 32)"
  RUNTIME_DB_PASSWORD="$(openssl rand -hex 32)"
  JWT_SECRET="$(openssl rand -hex 48)"
  umask 077
  {
    printf 'DB_ADMIN_PASSWORD=%s\n' "$DB_ADMIN_PASSWORD"
    printf 'DB_OWNER_PASSWORD=%s\n' "$DB_OWNER_PASSWORD"
    printf 'RUNTIME_DB_PASSWORD=%s\n' "$RUNTIME_DB_PASSWORD"
    printf 'JWT_SECRET=%s\n' "$JWT_SECRET"
  } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Создан .env.pilot с уникальными секретами (права 600). Значения не выводятся."
elif ! grep -q '^DB_ADMIN_PASSWORD=' "$ENV_FILE"; then
  # Upgrade old pilot env files without deleting the existing database volume.
  DB_ADMIN_PASSWORD="$(openssl rand -hex 32)"
  umask 077
  printf 'DB_ADMIN_PASSWORD=%s\n' "$DB_ADMIN_PASSWORD" >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Добавлен отдельный пароль администратора БД; при старте будет выполнена миграция старых ролей."
fi

for key in DB_ADMIN_PASSWORD DB_OWNER_PASSWORD RUNTIME_DB_PASSWORD JWT_SECRET; do
  grep -q "^${key}=" "$ENV_FILE" || { echo "В $ENV_FILE отсутствует $key"; exit 1; }
done

docker compose --env-file "$ENV_FILE" -f compose.pilot.yml up -d --build
# Wait for one-shot bootstrap/migration jobs to finish, then remove their containers and environment metadata.
docker compose --env-file "$ENV_FILE" -f compose.pilot.yml wait db-bootstrap db-migrate >/dev/null
docker compose --env-file "$ENV_FILE" -f compose.pilot.yml rm -f db-bootstrap db-migrate >/dev/null
echo "Пилот запущен. Проверка: curl -fsS http://127.0.0.1:18080/api/v1/health/ready"
echo "Создать первого директора: см. docs/PILOT_RUNBOOK_RU.md (одноразовый контейнер с временной передачей DB_ADMIN_PASSWORD)."
echo "Внешний доступ не настроен. Подключайте только через HTTPS reverse proxy/VPN."
