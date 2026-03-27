"""
Sentinel event store — append-only SQLite backend.

Zero-dependency constraint: stdlib only (sqlite3, datetime, json).
No imports from hestia.* and no pip packages permitted.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional


_CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    source      TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK(severity IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    event_type  TEXT NOT NULL,
    summary     TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}',
    action_taken TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0
)
"""

# Block ALL DELETEs — the store is append-only.
_CREATE_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS trg_block_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'DELETE is not permitted on the events table (append-only)');
END
"""

# Block UPDATEs on every column except acknowledged.
# Strategy: the trigger fires when acknowledged is NOT the only thing changing.
# We detect this by checking whether any non-acknowledged column differs between
# NEW and OLD.  If so, we abort.
_CREATE_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS trg_block_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'UPDATE is not permitted on events except to set acknowledged=1')
    WHERE
        NEW.event_id      IS NOT OLD.event_id    OR
        NEW.timestamp     IS NOT OLD.timestamp   OR
        NEW.source        IS NOT OLD.source      OR
        NEW.severity      IS NOT OLD.severity    OR
        NEW.event_type    IS NOT OLD.event_type  OR
        NEW.summary       IS NOT OLD.summary     OR
        NEW.details       IS NOT OLD.details     OR
        NEW.action_taken  IS NOT OLD.action_taken;
END
"""


class SentinelStore:
    """Append-only SQLite event store following Atlas-compatible schema."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create the events table and append-only enforcement triggers."""
        with self._connect() as conn:
            conn.execute(_CREATE_EVENTS_TABLE)
            conn.execute(_CREATE_DELETE_TRIGGER)
            conn.execute(_CREATE_UPDATE_TRIGGER)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def insert_event(
        self,
        event_id: str,
        source: str,
        severity: str,
        event_type: str,
        summary: str,
        details: str = "{}",
        action_taken: Optional[str] = None,
    ) -> None:
        """Insert a new event.  Timestamp is auto-generated as ISO 8601 UTC."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events
                    (event_id, timestamp, source, severity, event_type,
                     summary, details, action_taken, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (event_id, timestamp, source, severity, event_type,
                 summary, details, action_taken),
            )

    def acknowledge_event(self, event_id: str) -> None:
        """Set acknowledged=1 for the given event.  The only permitted UPDATE."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE events SET acknowledged = 1 WHERE event_id = ?",
                (event_id,),
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_recent_events(self, limit: int = 50) -> list[dict]:
        """Return the most recent events, ordered by timestamp DESC."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            return self._rows_to_dicts(cursor)

    def get_unacknowledged_events(self) -> list[dict]:
        """Return all events where acknowledged=0, ordered by timestamp DESC."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM events WHERE acknowledged = 0 ORDER BY timestamp DESC"
            )
            return self._rows_to_dicts(cursor)

    def get_events_by_severity(self, severity: str, limit: int = 50) -> list[dict]:
        """Return events filtered by severity, ordered by timestamp DESC."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM events WHERE severity = ? ORDER BY timestamp DESC LIMIT ?",
                (severity, limit),
            )
            return self._rows_to_dicts(cursor)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
        return [dict(row) for row in cursor.fetchall()]
