"""
File audit database — SQLite storage for file operation audit trail.

Extends BaseDatabase. Every query is scoped by user_id for multi-user
readiness.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger

logger = get_logger()

_instance: Optional["FileAuditDatabase"] = None
_DB_PATH = Path.home() / "hestia" / "data" / "file_audit.db"


class FileAuditDatabase(BaseDatabase):
    """Async SQLite database for file operation audit logs."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("file_audit", db_path=db_path or _DB_PATH)

    async def _init_schema(self) -> None:
        """Create file_audit table and indexes."""
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS file_audit (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                path TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                destination_path TEXT,
                metadata TEXT DEFAULT '{}'
            )
        """)
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_audit_user_ts
            ON file_audit(user_id, timestamp DESC)
        """)
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_audit_operation
            ON file_audit(operation, timestamp DESC)
        """)
        await self.connection.commit()

    async def log_operation(
        self,
        user_id: str,
        device_id: str,
        operation: str,
        path: str,
        result: str,
        destination_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Insert an audit log entry.

        Returns:
            The generated UUID for this log entry.
        """
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {})

        await self.connection.execute(
            """
            INSERT INTO file_audit
                (id, user_id, device_id, operation, path, result,
                 timestamp, destination_path, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                user_id,
                device_id,
                operation,
                path,
                result,
                timestamp,
                destination_path,
                metadata_json,
            ),
        )
        await self.connection.commit()
        return entry_id

    async def get_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        operation: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get audit logs for a user, newest first.

        Args:
            user_id: Scope results to this user.
            limit: Max entries to return.
            offset: Number of entries to skip.
            operation: Optional filter by operation type.

        Returns:
            List of log dicts.
        """
        if operation:
            cursor = await self.connection.execute(
                """
                SELECT id, user_id, device_id, operation, path, result,
                       timestamp, destination_path, metadata
                FROM file_audit
                WHERE user_id = ? AND operation = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, operation, limit, offset),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT id, user_id, device_id, operation, path, result,
                       timestamp, destination_path, metadata
                FROM file_audit
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )

        rows = await cursor.fetchall()
        results = []
        for row in rows:
            entry = dict(row)
            # Parse metadata JSON back to dict
            if isinstance(entry.get("metadata"), str):
                try:
                    entry["metadata"] = json.loads(entry["metadata"])
                except (json.JSONDecodeError, TypeError):
                    entry["metadata"] = {}
            results.append(entry)
        return results

    async def cleanup_old_entries(self, retention_days: int = 90) -> int:
        """
        Delete audit entries older than the retention period.

        Args:
            retention_days: Number of days to retain. Default 90.

        Returns:
            Number of entries deleted.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        ).isoformat()

        cursor = await self.connection.execute(
            "DELETE FROM file_audit WHERE timestamp < ?",
            (cutoff,),
        )
        await self.connection.commit()
        return cursor.rowcount


async def get_file_audit_database(
    db_path: Optional[Path] = None,
) -> FileAuditDatabase:
    """Get or create the singleton FileAuditDatabase instance."""
    global _instance
    if _instance is None:
        _instance = FileAuditDatabase(db_path)
        await _instance.connect()
    return _instance


async def close_file_audit_database() -> None:
    """Close and discard the singleton FileAuditDatabase instance."""
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
