#!/usr/bin/env bash
# Nightly off-box backup: pg_dump + the media tree, pushed via restic.
# Meant to run from a host crontab, e.g.:
#   0 3 * * * cd /opt/wedding && ./scripts/backup.sh >> /var/log/wedding-backup.log 2>&1
#
# One-time setup before the first run:
#   set RESTIC_REPOSITORY and RESTIC_PASSWORD (and any remote credentials
#   your repository type needs — b2/s3/etc, see restic docs) in .env.prod
#   restic init
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
source .env.prod
set +a

STAMP="$(date +%Y%m%d-%H%M%S)"
DUMP_DIR="$(mktemp -d)"
trap 'rm -rf "$DUMP_DIR"' EXIT

echo "[$STAMP] Dumping database..."
docker compose -f compose.prod.yaml exec -T db \
  pg_dump -U "${POSTGRES_USER:-wedding}" "${POSTGRES_DB:-wedding}" \
  > "$DUMP_DIR/db-$STAMP.sql"

echo "[$STAMP] Backing up database dump + media tree with restic..."
restic backup "$DUMP_DIR/db-$STAMP.sql" ./media --tag wedding

echo "[$STAMP] Pruning old snapshots (keeping 14 daily, 8 weekly, 6 monthly)..."
restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 6 --prune

echo "[$STAMP] Backup complete."
