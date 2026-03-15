"""
Mail reader - Direct SQLite access to Apple Mail database.

Provides read-only access to emails via the Envelope Index database.
Note: Requires Full Disk Access permission in System Preferences.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

try:
    import aiosqlite
except ImportError:
    aiosqlite = None

from .models import Email, Mailbox

logger = logging.getLogger(__name__)


class MailError(Exception):
    """Mail operation error."""
    pass


class MailClient:
    """
    Read-only client for Apple Mail database.

    Uses direct SQLite access to the Envelope Index database.
    This requires Full Disk Access permission for the process.
    """

    # Apple Mail stores emails in this SQLite database
    DEFAULT_DB_PATH = "~/Library/Mail/V10/MailData/Envelope Index"

    # Apple's reference date is January 1, 2001
    APPLE_EPOCH = datetime(2001, 1, 1)

    def __init__(self, db_path: Optional[str] = None):
        if aiosqlite is None:
            raise MailError("aiosqlite not installed. Run: pip install aiosqlite")

        self.db_path = Path(db_path or self.DEFAULT_DB_PATH).expanduser()
        self._connection: Optional[aiosqlite.Connection] = None

    def _apple_timestamp_to_datetime(self, timestamp: Optional[float]) -> Optional[datetime]:
        """Convert Apple timestamp (seconds since 2001-01-01) to datetime."""
        if timestamp is None:
            return None
        return self.APPLE_EPOCH + timedelta(seconds=timestamp)

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._connection is None:
            if not self.db_path.exists():
                raise MailError(
                    f"Mail database not found: {self.db_path}. "
                    "Make sure Mail.app has been used and Full Disk Access is granted."
                )

            try:
                self._connection = await aiosqlite.connect(
                    str(self.db_path),
                    timeout=10.0,
                )
                self._connection.row_factory = aiosqlite.Row
            except Exception as e:
                raise MailError(f"Failed to connect to Mail database: {e}")

        return self._connection

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def list_mailboxes(self) -> List[Mailbox]:
        """List all mailboxes."""
        conn = await self._get_connection()

        query = """
            SELECT
                ROWID as id,
                url,
                COALESCE(unread_count, 0) as unread_count
            FROM mailboxes
            WHERE url IS NOT NULL
            ORDER BY url
        """

        try:
            cursor = await conn.execute(query)
            rows = await cursor.fetchall()

            mailboxes = []
            for row in rows:
                url = row["url"] or ""
                # Extract name from URL (e.g., "imap://..." -> folder name)
                name = url.split("/")[-1] if "/" in url else url

                mailboxes.append(Mailbox(
                    id=str(row["id"]),
                    name=name,
                    url=url,
                    unread_count=row["unread_count"],
                ))

            return mailboxes
        except Exception as e:
            raise MailError(f"Failed to list mailboxes: {e}")

    async def search_emails(
        self,
        query: str,
        limit: int = 50,
        mailbox: Optional[str] = None,
    ) -> List[Email]:
        """
        Search emails by subject or sender.

        Args:
            query: Search query (matches subject or sender)
            limit: Maximum results to return
            mailbox: Filter by mailbox name (optional)
        """
        conn = await self._get_connection()

        sql = """
            SELECT
                m.ROWID as rowid,
                m.message_id,
                m.subject,
                m.sender,
                m.date_sent,
                m.date_received,
                NULL as snippet,
                m.read as is_read,
                m.flagged as is_flagged,
                a.address as sender_email,
                mb.url as mailbox_url
            FROM messages m
            LEFT JOIN addresses a ON m.sender = a.ROWID
            LEFT JOIN mailboxes mb ON m.mailbox = mb.ROWID
            WHERE (m.subject LIKE ? OR a.address LIKE ? OR a.comment LIKE ?)
        """

        params = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if mailbox:
            sql += " AND mb.url LIKE ?"
            params.append(f"%{mailbox}%")

        sql += " ORDER BY m.date_received DESC LIMIT ?"
        params.append(limit)

        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()

            return [self._row_to_email(row) for row in rows]
        except Exception as e:
            raise MailError(f"Failed to search emails: {e}")

    async def get_recent_emails(
        self,
        hours: int = 24,
        limit: int = 100,
        unread_only: bool = False,
    ) -> List[Email]:
        """
        Get recent emails.

        Args:
            hours: How many hours back to look
            limit: Maximum results
            unread_only: Only return unread emails
        """
        conn = await self._get_connection()

        # Calculate cutoff in Apple timestamp format
        cutoff = datetime.now() - timedelta(hours=hours)
        apple_cutoff = (cutoff - self.APPLE_EPOCH).total_seconds()

        sql = """
            SELECT
                m.ROWID as rowid,
                m.message_id,
                m.subject,
                m.sender,
                m.date_sent,
                m.date_received,
                NULL as snippet,
                m.read as is_read,
                m.flagged as is_flagged,
                a.address as sender_email,
                a.comment as sender_name,
                mb.url as mailbox_url
            FROM messages m
            LEFT JOIN addresses a ON m.sender = a.ROWID
            LEFT JOIN mailboxes mb ON m.mailbox = mb.ROWID
            WHERE m.date_received > ?
        """

        params = [apple_cutoff]

        if unread_only:
            sql += " AND m.read = 0"

        sql += " ORDER BY m.date_received DESC LIMIT ?"
        params.append(limit)

        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()

            return [self._row_to_email(row) for row in rows]
        except Exception as e:
            raise MailError(f"Failed to get recent emails: {e}")

    async def get_email(self, message_id: str) -> Optional[Email]:
        """Get email by message ID."""
        conn = await self._get_connection()

        sql = """
            SELECT
                m.ROWID as rowid,
                m.message_id,
                m.subject,
                m.sender,
                m.date_sent,
                m.date_received,
                NULL as snippet,
                m.read as is_read,
                m.flagged as is_flagged,
                a.address as sender_email,
                a.comment as sender_name,
                mb.url as mailbox_url
            FROM messages m
            LEFT JOIN addresses a ON m.sender = a.ROWID
            LEFT JOIN mailboxes mb ON m.mailbox = mb.ROWID
            WHERE m.message_id = ?
        """

        try:
            cursor = await conn.execute(sql, [message_id])
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_email(row)
        except Exception as e:
            raise MailError(f"Failed to get email: {e}")

    async def get_unread_count(self, mailbox: Optional[str] = None) -> int:
        """Get count of unread emails."""
        conn = await self._get_connection()

        if mailbox:
            sql = """
                SELECT COUNT(*) as count
                FROM messages m
                JOIN mailboxes mb ON m.mailbox = mb.ROWID
                WHERE m.read = 0 AND mb.url LIKE ?
            """
            params = [f"%{mailbox}%"]
        else:
            sql = "SELECT COUNT(*) as count FROM messages WHERE read = 0"
            params = []

        try:
            cursor = await conn.execute(sql, params)
            row = await cursor.fetchone()
            return row["count"] if row else 0
        except Exception as e:
            raise MailError(f"Failed to get unread count: {e}")

    async def get_flagged_emails(self, limit: int = 50) -> List[Email]:
        """Get flagged emails."""
        conn = await self._get_connection()

        sql = """
            SELECT
                m.ROWID as rowid,
                m.message_id,
                m.subject,
                m.sender,
                m.date_sent,
                m.date_received,
                NULL as snippet,
                m.read as is_read,
                m.flagged as is_flagged,
                a.address as sender_email,
                a.comment as sender_name,
                mb.url as mailbox_url
            FROM messages m
            LEFT JOIN addresses a ON m.sender = a.ROWID
            LEFT JOIN mailboxes mb ON m.mailbox = mb.ROWID
            WHERE m.flagged = 1
            ORDER BY m.date_received DESC
            LIMIT ?
        """

        try:
            cursor = await conn.execute(sql, [limit])
            rows = await cursor.fetchall()

            return [self._row_to_email(row) for row in rows]
        except Exception as e:
            raise MailError(f"Failed to get flagged emails: {e}")

    def _row_to_email(self, row) -> Email:
        """Convert database row to Email model."""
        # Extract mailbox name from URL
        mailbox_url = row["mailbox_url"] or ""
        mailbox_name = mailbox_url.split("/")[-1] if "/" in mailbox_url else mailbox_url

        # Get sender info
        sender_email = row["sender_email"] or ""
        sender_name = row.get("sender_name", "") or sender_email

        return Email(
            message_id=row["message_id"] or str(row["rowid"]),
            subject=row["subject"] or "(no subject)",
            sender=sender_name,
            sender_email=sender_email,
            recipients=[],  # Would need additional query
            date=self._apple_timestamp_to_datetime(row["date_received"]),
            snippet=row["snippet"],
            body=None,  # Full body requires separate file access
            mailbox=mailbox_name,
            is_read=bool(row["is_read"]),
            is_flagged=bool(row["is_flagged"]),
            has_attachments=False,  # Would need additional query
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self._get_connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
