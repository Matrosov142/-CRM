#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.pilot ]] || { echo "Нет .env.pilot"; exit 1; }
set -a; source .env.pilot; set +a
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR:-./backups}/$STAMP"
umask 077
mkdir -p "$OUT"
docker compose --env-file .env.pilot -f compose.pilot.yml exec -T db \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$OUT/database.dump"
docker compose --env-file .env.pilot -f compose.pilot.yml exec -T api \
  tar -czf - -C /var/lib/potok-crm documents > "$OUT/documents.tar.gz"
(
  cd "$OUT"
  sha256sum database.dump documents.tar.gz > SHA256SUMS
)
chmod -R go-rwx "$OUT"
echo "Резервная копия создана: $OUT"
