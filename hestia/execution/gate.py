"""
External communication gate for approval-based access control.

Manages service whitelists and approval flows for tools that
require external communication.
"""

import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import GateDecision, GateRequest


class ExternalCommunicationGate:
    """
    Gate for controlling external communications.

    Tools that communicate externally (APIs, web requests, etc.)
    must pass through this gate. Users can approve services
    for future use or require per-request approval.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
    ):
        """
        Initialize the communication gate.

        Args:
            db_path: Path to SQLite database for persistence
        """
        self.db_path = db_path or Path.home() / "hestia" / "data" / "gate.db"
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Connect to the database and create tables if needed."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        # Create tables
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS service_whitelist (
                service TEXT PRIMARY KEY,
                approved_at DATETIME NOT NULL,
                approved_by TEXT DEFAULT 'user',
                scope TEXT DEFAULT 'all',
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS gate_decisions (
                id TEXT PRIMARY KEY,
                service TEXT NOT NULL,
                action TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                decided_at DATETIME NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_decisions_service
            ON gate_decisions(service);

            CREATE INDEX IF NOT EXISTS idx_decisions_time
            ON gate_decisions(decided_at);
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> "ExternalCommunicationGate":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()

    def _ensure_connected(self) -> None:
        """Raise error if not connected."""
        if self._connection is None:
            raise RuntimeError("Gate not connected. Call connect() first.")

    async def check_approval(
        self,
        service: str,
        action: str = "access",
    ) -> GateDecision:
        """
        Check if a service is approved for access.

        Args:
            service: Service identifier (e.g., "api.openweather.com")
            action: Action being performed (e.g., "read", "write")

        Returns:
            GateDecision indicating approval status
        """
        self._ensure_connected()

        # Check whitelist
        cursor = await self._connection.execute(
            "SELECT scope FROM service_whitelist WHERE service = ?",
            (service,)
        )
        row = await cursor.fetchone()

        if row:
            scope = row["scope"]
            # Check if action is within approved scope
            if scope == "all":
                return GateDecision.APPROVED
            elif scope == action:
                return GateDecision.APPROVED
            # scope doesn't match action - requires new approval
            return GateDecision.PENDING

        return GateDecision.PENDING

    async def add_to_whitelist(
        self,
        service: str,
        scope: str = "all",
        notes: Optional[str] = None,
    ) -> None:
        """
        Add a service to the whitelist.

        Args:
            service: Service identifier
            scope: Access scope ('all', 'read', 'write')
            notes: Optional notes about the approval
        """
        self._ensure_connected()

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO service_whitelist
            (service, approved_at, approved_by, scope, notes)
            VALUES (?, ?, 'user', ?, ?)
            """,
            (service, datetime.utcnow().isoformat(), scope, notes)
        )
        await self._connection.commit()

    async def remove_from_whitelist(self, service: str) -> bool:
        """
        Remove a service from the whitelist.

        Args:
            service: Service identifier

        Returns:
            True if service was removed, False if not found
        """
        self._ensure_connected()

        cursor = await self._connection.execute(
            "DELETE FROM service_whitelist WHERE service = ?",
            (service,)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def list_whitelist(self) -> List[dict]:
        """
        Get all whitelisted services.

        Returns:
            List of service entries with approval details
        """
        self._ensure_connected()

        cursor = await self._connection.execute(
            "SELECT * FROM service_whitelist ORDER BY approved_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def is_whitelisted(self, service: str) -> bool:
        """
        Check if a service is in the whitelist.

        Args:
            service: Service identifier

        Returns:
            True if whitelisted
        """
        decision = await self.check_approval(service)
        return decision == GateDecision.APPROVED

    async def record_decision(
        self,
        request: GateRequest,
        decision: GateDecision,
    ) -> None:
        """
        Record a gate decision for audit purposes.

        Args:
            request: The gate request
            decision: The decision made
        """
        self._ensure_connected()

        await self._connection.execute(
            """
            INSERT INTO gate_decisions
            (id, service, action, tool_name, decision, reason, decided_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id,
                request.service,
                request.action,
                request.tool_name,
                decision.value,
                request.reason,
                datetime.utcnow().isoformat(),
            )
        )
        await self._connection.commit()

    async def get_recent_decisions(
        self,
        limit: int = 50,
        service: Optional[str] = None,
    ) -> List[dict]:
        """
        Get recent gate decisions.

        Args:
            limit: Maximum number of decisions to return
            service: Filter by service (optional)

        Returns:
            List of decision records
        """
        self._ensure_connected()

        if service:
            cursor = await self._connection.execute(
                """
                SELECT * FROM gate_decisions
                WHERE service = ?
                ORDER BY decided_at DESC
                LIMIT ?
                """,
                (service, limit)
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT * FROM gate_decisions
                ORDER BY decided_at DESC
                LIMIT ?
                """,
                (limit,)
            )

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def request_approval(
        self,
        service: str,
        action: str,
        tool_name: str,
        reason: str,
        auto_approve: bool = False,
    ) -> GateDecision:
        """
        Request approval for a service.

        In v1.0, this either auto-approves or returns PENDING.
        Future versions may implement interactive approval.

        Args:
            service: Service identifier
            action: Action being requested
            tool_name: Tool requesting access
            reason: Why access is needed
            auto_approve: If True, automatically approve and whitelist

        Returns:
            GateDecision
        """
        request = GateRequest.create(
            service=service,
            action=action,
            tool_name=tool_name,
            reason=reason,
        )

        # Check existing approval
        decision = await self.check_approval(service, action)

        if decision == GateDecision.APPROVED:
            await self.record_decision(request, decision)
            return decision

        if auto_approve:
            # Auto-approve grants full access (scope="all")
            await self.add_to_whitelist(service, scope="all", notes=reason)
            decision = GateDecision.APPROVED
            await self.record_decision(request, decision)
            return decision

        # v1.0: Return PENDING - orchestration layer handles user interaction
        await self.record_decision(request, GateDecision.PENDING)
        return GateDecision.PENDING

    async def clear_whitelist(self) -> int:
        """
        Clear all whitelisted services.

        Returns:
            Number of services removed
        """
        self._ensure_connected()

        cursor = await self._connection.execute("DELETE FROM service_whitelist")
        count = cursor.rowcount
        await self._connection.commit()
        return count


# Module-level singleton
_gate: Optional[ExternalCommunicationGate] = None


async def get_communication_gate() -> ExternalCommunicationGate:
    """
    Get the global communication gate singleton.

    Returns:
        Connected ExternalCommunicationGate instance
    """
    global _gate
    if _gate is None:
        _gate = ExternalCommunicationGate()
        await _gate.connect()
    return _gate
