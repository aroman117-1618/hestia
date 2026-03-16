"""
Routing audit database — SQLite storage for agent routing decisions.

Stores every routing decision with confidence, agents invoked,
fallback status, and performance metrics. User-scoped for family scale.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase
from hestia.orchestration.agent_models import RoutingAuditEntry

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "routing_audit.db"

_instance: Optional["RoutingAuditDatabase"] = None


class RoutingAuditDatabase(BaseDatabase):
    """SQLite storage for routing audit entries."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("routing_audit", db_path or _DB_PATH)

    async def initialize(self) -> None:
        """Alias for connect() — backward compat."""
        await self.connect()

    async def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS routing_audit (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                intent TEXT NOT NULL,
                route_chosen TEXT NOT NULL,
                route_confidence REAL NOT NULL,
                actual_agents TEXT NOT NULL DEFAULT '[]',
                chain_collapsed INTEGER DEFAULT 0,
                fallback_triggered INTEGER DEFAULT 0,
                total_inference_calls INTEGER DEFAULT 1,
                total_duration_ms INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_routing_audit_user_ts
                ON routing_audit(user_id, timestamp DESC);
        """)
        await self._connection.commit()

    async def store(self, entry: RoutingAuditEntry) -> str:
        """Insert a routing audit entry. Returns entry ID."""
        assert self._connection is not None
        await self._connection.execute(
            """INSERT INTO routing_audit
               (id, user_id, request_id, timestamp, intent, route_chosen,
                route_confidence, actual_agents, chain_collapsed,
                fallback_triggered, total_inference_calls, total_duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.user_id,
                entry.request_id,
                entry.timestamp.isoformat(),
                entry.intent,
                entry.route_chosen,
                entry.route_confidence,
                json.dumps(entry.actual_agents),
                int(entry.chain_collapsed),
                int(entry.fallback_triggered),
                entry.total_inference_calls,
                entry.total_duration_ms,
            ),
        )
        await self._connection.commit()
        return entry.id

    async def get_recent(
        self, user_id: str, limit: int = 50, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent routing audit entries for a user."""
        assert self._connection is not None
        query = "SELECT * FROM routing_audit WHERE user_id = ?"
        params: List[Any] = [user_id]
        if days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                results.append(self._row_to_dict(row))
        return results

    async def get_route_stats(
        self, user_id: str, days: int = 30
    ) -> Dict[str, int]:
        """Get route distribution counts for a user."""
        assert self._connection is not None
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with self._connection.execute(
            """SELECT route_chosen, COUNT(*) as cnt
               FROM routing_audit
               WHERE user_id = ? AND timestamp >= ?
               GROUP BY route_chosen""",
            (user_id, cutoff),
        ) as cursor:
            stats = {}
            async for row in cursor:
                stats[row["route_chosen"]] = row["cnt"]
            return stats

    def _row_to_dict(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Convert a database row to dict."""
        agents = []
        try:
            agents = json.loads(row["actual_agents"])
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "request_id": row["request_id"],
            "timestamp": row["timestamp"],
            "intent": row["intent"],
            "route_chosen": row["route_chosen"],
            "route_confidence": row["route_confidence"],
            "actual_agents": agents,
            "chain_collapsed": bool(row["chain_collapsed"]),
            "fallback_triggered": bool(row["fallback_triggered"]),
            "total_inference_calls": row["total_inference_calls"],
            "total_duration_ms": row["total_duration_ms"],
        }


async def get_routing_audit_db(
    db_path: Optional[Path] = None,
) -> RoutingAuditDatabase:
    """Singleton factory for RoutingAuditDatabase."""
    global _instance
    if _instance is None:
        _instance = RoutingAuditDatabase(db_path)
        await _instance.initialize()
    return _instance


async def close_routing_audit_db() -> None:
    """Close the singleton routing audit database."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
