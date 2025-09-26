#!/bin/bash
set -e

BACKUP_PATH="/docker-entrypoint-initdb.d/dump.sql"

if [ ! -f "$BACKUP_PATH" ]; then
  echo "Downloading DB dump..."
  curl -L "https://drive.google.com/uc?export=download&id=19srXpFyhkyUqAUPct1g-gDDiwejXvV0T" \
       -o "$BACKUP_PATH"
fi

echo "Restoring database..."
export PGPASSWORD="${POSTGRES_PASSWORD}"
psql -U "${POSTGRES_USER}" \
     -d "${POSTGRES_DB}" \
     -f "$BACKUP_PATH"
