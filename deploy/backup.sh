#!/usr/bin/env bash
# Backup do banco + contratos em /root/backups/emg-crm. Agende no cron: 0 3 * * * bash /root/emg-crm/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=/root/backups/emg-crm; mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M)
docker compose exec -T db pg_dump -U emg emgcrm | gzip > "$DEST/db-$STAMP.sql.gz"
tar czf "$DEST/contratos-$STAMP.tar.gz" storage/contratos
ls -1t "$DEST" | tail -n +31 | xargs -r -I{} rm "$DEST/{}"
echo "backup ok: $STAMP"
