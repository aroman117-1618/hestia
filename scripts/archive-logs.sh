#!/bin/bash
# archive-logs.sh — Move rotated logs older than 7 days to external storage, compress with gzip
# Scheduled: weekly Sunday 2am via crontab
# Gracefully skips if external drive not mounted

set -euo pipefail

MOUNT="/Volumes/HestiaStorage"
ARCHIVE_DIR="${MOUNT}/logs-archive"
LOG_DIR="${HOME}/hestia/logs"
AGE_DAYS=7

# Check external drive is mounted
if [ ! -d "$MOUNT" ]; then
    echo "$(date -Iseconds) [archive-logs] External drive not mounted at ${MOUNT} — skipping"
    exit 0
fi

# Ensure archive directory exists
mkdir -p "$ARCHIVE_DIR"

# Find rotated log files older than AGE_DAYS
# Pattern: hestia.log.YYYY-MM-DD or any .log.* rotated files
archived=0
find "$LOG_DIR" -name "*.log.*" -type f -mtime +"$AGE_DAYS" 2>/dev/null | while read -r logfile; do
    basename=$(basename "$logfile")
    # Skip if already compressed
    if [[ "$basename" == *.gz ]]; then
        mv "$logfile" "$ARCHIVE_DIR/"
    else
        gzip -c "$logfile" > "$ARCHIVE_DIR/${basename}.gz"
        rm "$logfile"
    fi
    archived=$((archived + 1))
done

echo "$(date -Iseconds) [archive-logs] Complete — archived files from ${LOG_DIR} to ${ARCHIVE_DIR}"
