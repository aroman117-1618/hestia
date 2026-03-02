#!/bin/bash
#
# compress-logs.sh — Compress old logs and delete ancient compressed logs
#
# Policy:
#   - Gzip log files older than 7 days (keeps originals readable for a week)
#   - Delete compressed logs older than 90 days
#
# Designed to run daily via launchd (com.hestia.log-compressor.plist).
# Safe to run manually: idempotent (won't double-compress .gz files).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"

COMPRESS_AFTER_DAYS=7
DELETE_AFTER_DAYS=90

if [[ ! -d "$LOG_DIR" ]]; then
    exit 0
fi

# Compress rotated log files older than 7 days (skip already compressed)
find "$LOG_DIR" -name "*.log.*" -not -name "*.gz" -mtime +${COMPRESS_AFTER_DAYS} -type f | while read -r logfile; do
    gzip "$logfile" 2>/dev/null && echo "Compressed: $(basename "$logfile")"
done

# Delete compressed logs older than 90 days
find "$LOG_DIR" -name "*.gz" -mtime +${DELETE_AFTER_DAYS} -type f | while read -r gzfile; do
    rm "$gzfile" 2>/dev/null && echo "Deleted: $(basename "$gzfile")"
done
