"""
Trading database — SQLite with WAL mode for concurrent access.

Tables: bots, trades, tax_lots, daily_summaries, reconciliation_log.
All tables are user_id-scoped for multi-device support.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent

logger = get_logger()

_DB_PATH = Path.home() / "hestia" / "data" / "trading.db"

# Module-level singleton
_instance: Optional["TradingDatabase"] = None


class TradingDatabase(BaseDatabase):
    """Trading database with WAL mode for concurrent WebSocket/REST access."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("trading", db_path or _DB_PATH)

    async def connect(self) -> None:
        """Open connection with WAL mode enabled."""
        await super().connect()
        # Enable WAL mode for concurrent reads during WebSocket events
        await self.connection.execute("PRAGMA journal_mode=WAL")
        # Enable memory-mapped I/O for performance
        await self.connection.execute("PRAGMA mmap_size=268435456")  # 256MB
        logger.info(
            "Trading database connected (WAL mode)",
            component=LogComponent.TRADING,
        )

    async def _init_schema(self) -> None:
        """Create tables and indexes."""
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS bots (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                strategy TEXT NOT NULL DEFAULT 'grid',
                pair TEXT NOT NULL DEFAULT 'BTC-USD',
                status TEXT NOT NULL DEFAULT 'created',
                capital_allocated REAL NOT NULL DEFAULT 0.0,
                config TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'user-default'
            );

            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                bot_id TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL DEFAULT 'limit',
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                fee REAL NOT NULL DEFAULT 0.0,
                fee_currency TEXT NOT NULL DEFAULT 'USD',
                pair TEXT NOT NULL DEFAULT 'BTC-USD',
                tax_lot_id TEXT,
                exchange_order_id TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                user_id TEXT NOT NULL DEFAULT 'user-default',
                FOREIGN KEY (bot_id) REFERENCES bots(id)
            );

            CREATE TABLE IF NOT EXISTS tax_lots (
                id TEXT PRIMARY KEY,
                trade_id TEXT NOT NULL,
                pair TEXT NOT NULL DEFAULT 'BTC-USD',
                quantity REAL NOT NULL,
                remaining_quantity REAL NOT NULL,
                cost_basis REAL NOT NULL,
                cost_per_unit REAL NOT NULL,
                method TEXT NOT NULL DEFAULT 'hifo',
                status TEXT NOT NULL DEFAULT 'open',
                acquired_at TEXT NOT NULL,
                closed_at TEXT,
                realized_pnl REAL NOT NULL DEFAULT 0.0,
                user_id TEXT NOT NULL DEFAULT 'user-default',
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            );

            CREATE TABLE IF NOT EXISTS daily_summaries (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                total_pnl REAL NOT NULL DEFAULT 0.0,
                realized_pnl REAL NOT NULL DEFAULT 0.0,
                unrealized_pnl REAL NOT NULL DEFAULT 0.0,
                total_trades INTEGER NOT NULL DEFAULT 0,
                winning_trades INTEGER NOT NULL DEFAULT 0,
                losing_trades INTEGER NOT NULL DEFAULT 0,
                total_fees REAL NOT NULL DEFAULT 0.0,
                total_volume REAL NOT NULL DEFAULT 0.0,
                positions TEXT NOT NULL DEFAULT '{}',
                strategy_attribution TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'user-default',
                UNIQUE(date, user_id)
            );

            CREATE TABLE IF NOT EXISTS risk_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reconciliation_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                local_balance REAL NOT NULL,
                exchange_balance REAL NOT NULL,
                discrepancy REAL NOT NULL,
                pair TEXT NOT NULL DEFAULT 'BTC-USD',
                resolved INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT ''
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_trades_bot_id ON trades(bot_id);
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
            CREATE INDEX IF NOT EXISTS idx_tax_lots_status ON tax_lots(status);
            CREATE INDEX IF NOT EXISTS idx_tax_lots_user_id ON tax_lots(user_id);
            CREATE INDEX IF NOT EXISTS idx_tax_lots_pair ON tax_lots(pair, status);
            CREATE INDEX IF NOT EXISTS idx_bots_user_id ON bots(user_id);
            CREATE INDEX IF NOT EXISTS idx_bots_status ON bots(status);
            CREATE INDEX IF NOT EXISTS idx_daily_summaries_date ON daily_summaries(date);
            CREATE INDEX IF NOT EXISTS idx_reconciliation_timestamp ON reconciliation_log(timestamp);

            -- Sprint 26: Watchlist
            CREATE TABLE IF NOT EXISTS watchlist (
                id TEXT PRIMARY KEY,
                pair TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                price_alerts TEXT NOT NULL DEFAULT '{}',
                added_at TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'user-default'
            );
            CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist(user_id);
        """)

        # Sprint 26: decision trail + confidence score columns (migration)
        import aiosqlite
        for col_sql in [
            "ALTER TABLE trades ADD COLUMN decision_trail TEXT DEFAULT '[]'",
            "ALTER TABLE trades ADD COLUMN confidence_score REAL DEFAULT NULL",
        ]:
            try:
                await self.connection.execute(col_sql)
            except aiosqlite.OperationalError:
                pass  # Column already exists

    # ── Bot CRUD ──────────────────────────────────────────────────

    async def create_bot(self, bot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new bot."""
        await self.connection.execute(
            """INSERT INTO bots (id, name, strategy, pair, status, capital_allocated,
               config, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bot_data["id"],
                bot_data.get("name", ""),
                bot_data["strategy"],
                bot_data.get("pair", "BTC-USD"),
                bot_data.get("status", "created"),
                bot_data.get("capital_allocated", 0.0),
                json.dumps(bot_data.get("config", {})),
                bot_data["created_at"],
                bot_data["updated_at"],
                bot_data.get("user_id", "user-default"),
            ),
        )
        await self.connection.commit()
        return bot_data

    async def get_bot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get a bot by ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM bots WHERE id = ?", (bot_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._bot_row_to_dict(row)

    async def list_bots(
        self, user_id: str = "user-default", status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List bots, optionally filtered by status."""
        if status:
            cursor = await self.connection.execute(
                "SELECT * FROM bots WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [self._bot_row_to_dict(r) for r in rows]

    async def update_bot(self, bot_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update bot fields."""
        sets = []
        values = []
        for key in ("name", "strategy", "pair", "status", "capital_allocated"):
            if key in updates:
                sets.append(f"{key} = ?")
                values.append(updates[key])
        if "config" in updates:
            sets.append("config = ?")
            values.append(json.dumps(updates["config"]))
        if not sets:
            return await self.get_bot(bot_id)
        sets.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(bot_id)
        await self.connection.execute(
            f"UPDATE bots SET {', '.join(sets)} WHERE id = ?", values
        )
        await self.connection.commit()
        return await self.get_bot(bot_id)

    async def delete_bot(self, bot_id: str) -> bool:
        """Delete a bot (soft-delete by setting status to 'stopped')."""
        cursor = await self.connection.execute(
            "UPDATE bots SET status = 'stopped', updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), bot_id),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    # ── Trade CRUD ────────────────────────────────────────────────

    async def record_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a completed trade."""
        await self.connection.execute(
            """INSERT INTO trades (id, bot_id, side, order_type, price, quantity,
               fee, fee_currency, pair, tax_lot_id, exchange_order_id,
               timestamp, metadata, user_id, decision_trail, confidence_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade_data["id"],
                trade_data["bot_id"],
                trade_data["side"],
                trade_data.get("order_type", "limit"),
                trade_data["price"],
                trade_data["quantity"],
                trade_data.get("fee", 0.0),
                trade_data.get("fee_currency", "USD"),
                trade_data.get("pair", "BTC-USD"),
                trade_data.get("tax_lot_id"),
                trade_data.get("exchange_order_id"),
                trade_data["timestamp"],
                json.dumps(trade_data.get("metadata", {})),
                trade_data.get("user_id", "user-default"),
                trade_data.get("decision_trail", "[]"),
                trade_data.get("confidence_score"),
            ),
        )
        await self.connection.commit()
        return trade_data

    async def record_trade_no_commit(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a trade WITHOUT committing — for use inside atomic transactions."""
        await self.connection.execute(
            """INSERT INTO trades (id, bot_id, side, order_type, price, quantity,
               fee, fee_currency, pair, tax_lot_id, exchange_order_id,
               timestamp, metadata, user_id, decision_trail, confidence_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade_data["id"],
                trade_data["bot_id"],
                trade_data["side"],
                trade_data.get("order_type", "limit"),
                trade_data["price"],
                trade_data["quantity"],
                trade_data.get("fee", 0.0),
                trade_data.get("fee_currency", "USD"),
                trade_data.get("pair", "BTC-USD"),
                trade_data.get("tax_lot_id"),
                trade_data.get("exchange_order_id"),
                trade_data["timestamp"],
                json.dumps(trade_data.get("metadata", {})),
                trade_data.get("user_id", "user-default"),
                trade_data.get("decision_trail", "[]"),
                trade_data.get("confidence_score"),
            ),
        )
        return trade_data

    async def get_trades(
        self,
        bot_id: Optional[str] = None,
        user_id: str = "user-default",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get trades, optionally filtered by bot."""
        if bot_id:
            cursor = await self.connection.execute(
                "SELECT * FROM trades WHERE bot_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (bot_id, user_id, limit, offset),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM trades WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            )
        rows = await cursor.fetchall()
        return [self._trade_row_to_dict(r) for r in rows]

    async def get_trade_count(self, bot_id: Optional[str] = None, user_id: str = "user-default") -> int:
        """Count trades."""
        if bot_id:
            cursor = await self.connection.execute(
                "SELECT COUNT(*) FROM trades WHERE bot_id = ? AND user_id = ?",
                (bot_id, user_id),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT COUNT(*) FROM trades WHERE user_id = ?", (user_id,)
            )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ── Tax Lot CRUD ──────────────────────────────────────────────

    async def create_tax_lot(self, lot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tax lot from a buy trade."""
        await self.create_tax_lot_no_commit(lot_data)
        await self.connection.commit()
        return lot_data

    async def create_tax_lot_no_commit(self, lot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a tax lot WITHOUT committing — for use inside atomic transactions."""
        await self.connection.execute(
            """INSERT INTO tax_lots (id, trade_id, pair, quantity, remaining_quantity,
               cost_basis, cost_per_unit, method, status, acquired_at, closed_at,
               realized_pnl, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lot_data["id"],
                lot_data["trade_id"],
                lot_data.get("pair", "BTC-USD"),
                lot_data["quantity"],
                lot_data["remaining_quantity"],
                lot_data["cost_basis"],
                lot_data["cost_per_unit"],
                lot_data.get("method", "hifo"),
                lot_data.get("status", "open"),
                lot_data["acquired_at"],
                lot_data.get("closed_at"),
                lot_data.get("realized_pnl", 0.0),
                lot_data.get("user_id", "user-default"),
            ),
        )
        return lot_data

    async def get_open_tax_lots(
        self,
        pair: str = "BTC-USD",
        method: str = "hifo",
        user_id: str = "user-default",
    ) -> List[Dict[str, Any]]:
        """Get open tax lots ordered by method (HIFO = highest cost first, FIFO = oldest first)."""
        if method not in ("hifo", "fifo"):
            raise ValueError(f"Invalid tax lot method: {method}. Must be 'hifo' or 'fifo'.")
        if method == "hifo":
            order = "cost_per_unit DESC"
        else:
            order = "acquired_at ASC"
        cursor = await self.connection.execute(
            f"""SELECT * FROM tax_lots
                WHERE pair = ? AND status IN ('open', 'partial') AND user_id = ?
                ORDER BY {order}""",
            (pair, user_id),
        )
        rows = await cursor.fetchall()
        return [self._tax_lot_row_to_dict(r) for r in rows]

    async def update_tax_lot(self, lot_id: str, updates: Dict[str, Any]) -> None:
        """Update a tax lot (remaining_quantity, status, realized_pnl, closed_at)."""
        await self.update_tax_lot_no_commit(lot_id, updates)
        await self.connection.commit()

    async def update_tax_lot_no_commit(self, lot_id: str, updates: Dict[str, Any]) -> None:
        """Update a tax lot WITHOUT committing — for use inside atomic transactions."""
        sets = []
        values = []
        for key in ("remaining_quantity", "status", "realized_pnl", "closed_at"):
            if key in updates:
                sets.append(f"{key} = ?")
                values.append(updates[key])
        if sets:
            values.append(lot_id)
            await self.connection.execute(
                f"UPDATE tax_lots SET {', '.join(sets)} WHERE id = ?", values
            )

    async def get_tax_lots(
        self, user_id: str = "user-default", status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all tax lots."""
        if status:
            cursor = await self.connection.execute(
                "SELECT * FROM tax_lots WHERE user_id = ? AND status = ? ORDER BY acquired_at DESC",
                (user_id, status),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM tax_lots WHERE user_id = ? ORDER BY acquired_at DESC",
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [self._tax_lot_row_to_dict(r) for r in rows]

    # ── Daily Summary ─────────────────────────────────────────────

    async def upsert_daily_summary(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a daily summary."""
        await self.connection.execute(
            """INSERT INTO daily_summaries (id, date, total_pnl, realized_pnl,
               unrealized_pnl, total_trades, winning_trades, losing_trades,
               total_fees, total_volume, positions, strategy_attribution,
               created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date, user_id) DO UPDATE SET
               total_pnl = excluded.total_pnl,
               realized_pnl = excluded.realized_pnl,
               unrealized_pnl = excluded.unrealized_pnl,
               total_trades = excluded.total_trades,
               winning_trades = excluded.winning_trades,
               losing_trades = excluded.losing_trades,
               total_fees = excluded.total_fees,
               total_volume = excluded.total_volume,
               positions = excluded.positions,
               strategy_attribution = excluded.strategy_attribution""",
            (
                summary_data["id"],
                summary_data["date"],
                summary_data.get("total_pnl", 0.0),
                summary_data.get("realized_pnl", 0.0),
                summary_data.get("unrealized_pnl", 0.0),
                summary_data.get("total_trades", 0),
                summary_data.get("winning_trades", 0),
                summary_data.get("losing_trades", 0),
                summary_data.get("total_fees", 0.0),
                summary_data.get("total_volume", 0.0),
                json.dumps(summary_data.get("positions", {})),
                json.dumps(summary_data.get("strategy_attribution", {})),
                summary_data.get("created_at", datetime.now(timezone.utc).isoformat()),
                summary_data.get("user_id", "user-default"),
            ),
        )
        await self.connection.commit()
        return summary_data

    async def get_daily_summary(
        self, date: str, user_id: str = "user-default"
    ) -> Optional[Dict[str, Any]]:
        """Get daily summary for a specific date."""
        cursor = await self.connection.execute(
            "SELECT * FROM daily_summaries WHERE date = ? AND user_id = ?",
            (date, user_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._summary_row_to_dict(row)

    async def get_daily_summaries(
        self, user_id: str = "user-default", limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Get recent daily summaries."""
        cursor = await self.connection.execute(
            "SELECT * FROM daily_summaries WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [self._summary_row_to_dict(r) for r in rows]

    # ── Reconciliation Log ────────────────────────────────────────

    async def log_reconciliation(self, result_data: Dict[str, Any]) -> None:
        """Log a reconciliation check result."""
        await self.connection.execute(
            """INSERT INTO reconciliation_log (id, timestamp, local_balance,
               exchange_balance, discrepancy, pair, resolved, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_data["id"],
                result_data["timestamp"],
                result_data["local_balance"],
                result_data["exchange_balance"],
                result_data["discrepancy"],
                result_data.get("pair", "BTC-USD"),
                1 if result_data.get("resolved", False) else 0,
                result_data.get("notes", ""),
            ),
        )
        await self.connection.commit()

    async def get_recent_reconciliations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent reconciliation results."""
        cursor = await self.connection.execute(
            "SELECT * FROM reconciliation_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Risk State Persistence ─────────────────────────────────────

    async def save_risk_state(self, key: str, value: str) -> None:
        """Save a risk state key-value pair (kill switch, breakers, tracking)."""
        await self.connection.execute(
            """INSERT INTO risk_state (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, value, datetime.now(timezone.utc).isoformat()),
        )
        await self.connection.commit()

    async def load_risk_state(self, key: str) -> Optional[str]:
        """Load a risk state value by key."""
        cursor = await self.connection.execute(
            "SELECT value FROM risk_state WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def load_all_risk_state(self) -> Dict[str, str]:
        """Load all risk state key-value pairs."""
        cursor = await self.connection.execute("SELECT key, value FROM risk_state")
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    # ── Watchlist CRUD (Sprint 26) ────────────────────────────────

    async def create_watchlist_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Add an item to the watchlist."""
        await self.connection.execute(
            """INSERT INTO watchlist (id, pair, notes, price_alerts, added_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item["id"], item["pair"], item.get("notes", ""),
             item.get("price_alerts", "{}"), item["added_at"],
             item.get("user_id", "user-default")),
        )
        await self.connection.commit()
        return item

    async def get_watchlist(self, user_id: str = "user-default") -> List[Dict[str, Any]]:
        """Get all watchlist items for a user."""
        cursor = await self.connection.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._watchlist_row_to_dict(r) for r in rows]

    async def update_watchlist_item(
        self, item_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a watchlist item."""
        sets, values = [], []
        for key in ("pair", "notes"):
            if key in updates:
                sets.append(f"{key} = ?")
                values.append(updates[key])
        if "price_alerts" in updates:
            sets.append("price_alerts = ?")
            values.append(json.dumps(updates["price_alerts"]))
        if not sets:
            return None
        values.append(item_id)
        await self.connection.execute(
            f"UPDATE watchlist SET {', '.join(sets)} WHERE id = ?", values
        )
        await self.connection.commit()
        cursor = await self.connection.execute(
            "SELECT * FROM watchlist WHERE id = ?", (item_id,)
        )
        row = await cursor.fetchone()
        return self._watchlist_row_to_dict(row) if row else None

    async def delete_watchlist_item(self, item_id: str) -> bool:
        """Remove a watchlist item."""
        cursor = await self.connection.execute(
            "DELETE FROM watchlist WHERE id = ?", (item_id,)
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _watchlist_row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
        d = dict(row)
        d["price_alerts"] = json.loads(d.get("price_alerts", "{}"))
        return d

    # ── Row converters ────────────────────────────────────────────

    @staticmethod
    def _bot_row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
        d = dict(row)
        d["config"] = json.loads(d.get("config", "{}"))
        return d

    @staticmethod
    def _trade_row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        d["decision_trail"] = json.loads(d.get("decision_trail", "[]"))
        return d

    # ── Trade Helpers (Sprint 26) ────────────────────────────────

    async def get_trade_by_id(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get a single trade by ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        )
        row = await cursor.fetchone()
        return self._trade_row_to_dict(row) if row else None

    async def update_trade_metadata(self, trade_id: str, metadata: Dict[str, Any]) -> bool:
        """Update a trade's metadata JSON."""
        cursor = await self.connection.execute(
            "UPDATE trades SET metadata = ? WHERE id = ?",
            (json.dumps(metadata), trade_id),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _tax_lot_row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
        return dict(row)

    @staticmethod
    def _summary_row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
        d = dict(row)
        d["positions"] = json.loads(d.get("positions", "{}"))
        d["strategy_attribution"] = json.loads(d.get("strategy_attribution", "{}"))
        return d


async def get_trading_database(db_path: Optional[Path] = None) -> TradingDatabase:
    """Singleton factory for TradingDatabase."""
    global _instance
    if _instance is None:
        _instance = TradingDatabase(db_path)
        await _instance.connect()
        logger.info(
            "Trading database initialized",
            component=LogComponent.TRADING,
        )
    return _instance
