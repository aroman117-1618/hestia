"""
SQLite persistence for cloud provider configuration and usage tracking.

Stores provider configs and usage records in ~/hestia/data/cloud.db.
Follows the pattern established in hestia/tasks/database.py.
"""

import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import (
    CloudProvider,
    CloudProviderState,
    ProviderConfig,
    CloudUsageRecord,
)


SCHEMA_VERSION = 1


class CloudDatabase:
    """
    SQLite database for cloud provider persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "cloud.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

        self.logger.info(
            f"Cloud database connected: {self.db_path}",
            component=LogComponent.API,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS cloud_providers (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL DEFAULT 'disabled',
                credential_key TEXT NOT NULL,
                active_model_id TEXT,
                available_models TEXT,
                base_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_health_check TEXT,
                health_status TEXT DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS cloud_usage (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model_id TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                duration_ms REAL NOT NULL,
                request_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_provider
                ON cloud_usage(provider);
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                ON cloud_usage(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_usage_request
                ON cloud_usage(request_id);
        """)

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> "CloudDatabase":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active connection."""
        if self._connection is None:
            raise RuntimeError("Cloud database not connected")
        return self._connection

    # ── Provider CRUD ──────────────────────────────────────────────────

    async def store_provider(self, config: ProviderConfig) -> None:
        """Store a provider configuration."""
        row = config.to_sqlite_row()
        await self.connection.execute(
            """INSERT OR REPLACE INTO cloud_providers
            (id, provider, state, credential_key, active_model_id,
             available_models, base_url, created_at, updated_at,
             last_health_check, health_status)
            VALUES (:id, :provider, :state, :credential_key, :active_model_id,
                    :available_models, :base_url, :created_at, :updated_at,
                    :last_health_check, :health_status)""",
            row,
        )
        await self.connection.commit()

    async def get_provider(self, provider: CloudProvider) -> Optional[ProviderConfig]:
        """Get a provider configuration by provider type."""
        cursor = await self.connection.execute(
            "SELECT * FROM cloud_providers WHERE provider = ?",
            (provider.value,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ProviderConfig.from_sqlite_row(dict(row))

    async def update_provider(self, config: ProviderConfig) -> None:
        """Update an existing provider configuration."""
        config.updated_at = datetime.now(timezone.utc)
        row = config.to_sqlite_row()
        await self.connection.execute(
            """UPDATE cloud_providers SET
            state = :state,
            credential_key = :credential_key,
            active_model_id = :active_model_id,
            available_models = :available_models,
            base_url = :base_url,
            updated_at = :updated_at,
            last_health_check = :last_health_check,
            health_status = :health_status
            WHERE provider = :provider""",
            row,
        )
        await self.connection.commit()

    async def delete_provider(self, provider: CloudProvider) -> bool:
        """Delete a provider configuration. Returns True if deleted."""
        cursor = await self.connection.execute(
            "DELETE FROM cloud_providers WHERE provider = ?",
            (provider.value,),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def list_providers(self) -> List[ProviderConfig]:
        """List all provider configurations."""
        cursor = await self.connection.execute(
            "SELECT * FROM cloud_providers ORDER BY created_at",
        )
        rows = await cursor.fetchall()
        return [ProviderConfig.from_sqlite_row(dict(row)) for row in rows]

    # ── Usage Tracking ─────────────────────────────────────────────────

    async def store_usage(self, record: CloudUsageRecord) -> None:
        """Store a usage record."""
        row = record.to_sqlite_row()
        await self.connection.execute(
            """INSERT INTO cloud_usage
            (id, provider, model_id, tokens_in, tokens_out, cost_usd,
             duration_ms, request_id, mode, timestamp)
            VALUES (:id, :provider, :model_id, :tokens_in, :tokens_out,
                    :cost_usd, :duration_ms, :request_id, :mode, :timestamp)""",
            row,
        )
        await self.connection.commit()

    async def get_usage_summary(
        self,
        days: int = 30,
        provider: Optional[CloudProvider] = None,
    ) -> Dict[str, Any]:
        """Get usage summary for a time period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        params: List[Any] = [cutoff_str]
        where_clause = "WHERE timestamp >= ?"
        if provider:
            where_clause += " AND provider = ?"
            params.append(provider.value)

        # Aggregate by provider and model
        cursor = await self.connection.execute(
            f"""SELECT provider, model_id,
                COUNT(*) as total_requests,
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                SUM(cost_usd) as total_cost_usd
            FROM cloud_usage
            {where_clause}
            GROUP BY provider, model_id
            ORDER BY total_cost_usd DESC""",
            params,
        )
        rows = await cursor.fetchall()

        by_provider = []
        total_cost = 0.0
        total_requests = 0
        for row in rows:
            entry = dict(row)
            by_provider.append(entry)
            total_cost += entry["total_cost_usd"] or 0.0
            total_requests += entry["total_requests"] or 0

        return {
            "period_days": days,
            "total_cost_usd": round(total_cost, 6),
            "total_requests": total_requests,
            "by_provider": by_provider,
        }

    async def get_usage_records(
        self,
        limit: int = 100,
        provider: Optional[CloudProvider] = None,
    ) -> List[CloudUsageRecord]:
        """Get recent usage records."""
        params: List[Any] = []
        where_clause = ""
        if provider:
            where_clause = "WHERE provider = ?"
            params.append(provider.value)

        params.append(limit)
        cursor = await self.connection.execute(
            f"""SELECT * FROM cloud_usage
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?""",
            params,
        )
        rows = await cursor.fetchall()
        return [CloudUsageRecord.from_sqlite_row(dict(row)) for row in rows]


# Module-level singleton
_cloud_database: Optional[CloudDatabase] = None


async def get_cloud_database() -> CloudDatabase:
    """Get or create the cloud database singleton."""
    global _cloud_database
    if _cloud_database is None:
        _cloud_database = CloudDatabase()
        await _cloud_database.connect()
    return _cloud_database
