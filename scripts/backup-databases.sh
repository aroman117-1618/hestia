#!/bin/bash
# backup-databases.sh — Nightly SQLite + ChromaDB backup to external storage
# Scheduled: nightly 3:30am via crontab (after Hestia's 3am scheduled tasks)
# Uses sqlite3 .backup for safe concurrent access
# Gracefully skips if external drive not mounted

set -euo pipefail

MOUNT="/Volumes/HestiaStorage"
BACKUP_BASE="${MOUNT}/backups"
DATA_DIR="${HOME}/hestia/data"
CHROMADB_DIR="${DATA_DIR}/chromadb"
CREDENTIALS_DIR="${DATA_DIR}/credentials"
RETENTION_DAYS=30

DATE=$(date +%Y-%m-%d)
DAILY_DIR="${BACKUP_BASE}/daily/${DATE}"

# Check external drive is mounted
if [ ! -d "$MOUNT" ]; then
    echo "$(date -Iseconds) [backup-db] External drive not mounted at ${MOUNT} — skipping"
    exit 0
fi

echo "$(date -Iseconds) [backup-db] Starting backup to ${DAILY_DIR}"

# Create today's backup directory
mkdir -p "$DAILY_DIR"

# Backup each SQLite database using .backup command (safe for concurrent access)
db_count=0
for db in "$DATA_DIR"/*.db; do
    if [ -f "$db" ]; then
        dbname=$(basename "$db")
        sqlite3 "$db" ".backup '${DAILY_DIR}/${dbname}'"
        db_count=$((db_count + 1))
    fi
done
echo "$(date -Iseconds) [backup-db] Backed up ${db_count} SQLite databases"

# Rsync ChromaDB directory
if [ -d "$CHROMADB_DIR" ]; then
    mkdir -p "${BACKUP_BASE}/chromadb"
    rsync -a --delete "$CHROMADB_DIR/" "${BACKUP_BASE}/chromadb/"
    echo "$(date -Iseconds) [backup-db] Synced ChromaDB"
fi

# Rsync credentials directory
if [ -d "$CREDENTIALS_DIR" ]; then
    mkdir -p "${DAILY_DIR}/credentials"
    rsync -a "$CREDENTIALS_DIR/" "${DAILY_DIR}/credentials/"
    echo "$(date -Iseconds) [backup-db] Synced credentials"
fi

# Clean up backups older than retention period
find "${BACKUP_BASE}/daily" -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -exec rm -rf {} + 2>/dev/null || true
echo "$(date -Iseconds) [backup-db] Cleaned backups older than ${RETENTION_DAYS} days"

echo "$(date -Iseconds) [backup-db] Complete"
