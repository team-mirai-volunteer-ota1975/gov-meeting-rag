#!/bin/bash
set -e

BACKUP_PATH="/docker-entrypoint-initdb.d/backup.dump"

if [ ! -f "$BACKUP_PATH" ]; then
  echo "Downloading DB dump..."
  curl -L "https://drive.google.com/uc?export=download&id=12N_t4OKSwq3GUeZ2-zXpsT5Qk4IC5u7P" \
       -o "$BACKUP_PATH"
fi

echo "Restoring database..."
export PGPASSWORD="${POSTGRES_PASSWORD}"
pg_restore --clean --if-exists \
           -U "${POSTGRES_USER}" \
           -d "${POSTGRES_DB}" \
           "$BACKUP_PATH"