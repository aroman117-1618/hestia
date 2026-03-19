# Sprint 26: Trading Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the trading module's monitoring dashboard with live data — SSE streaming, decision trail persistence, confidence scoring, watchlist, macOS UI wiring, and push/Discord alerting.

**Architecture:** Backend-first approach. Tasks 1-4 build the backend (decision trails, scoring, SSE event bus, REST endpoints for positions/portfolio, watchlist). Task 5 wires the macOS UI. Task 6 adds alerting. Each task is independently testable and committable.

**Tech Stack:** Python/FastAPI (SSE via StreamingResponse), SQLite (ALTER TABLE + new table), SwiftUI/macOS (ObservableObject ViewModel), asyncio.Queue (event bus), aiohttp (Discord webhook).

**Second Opinion:** Approved with conditions — see `docs/plans/sprint-26-trading-dashboard-second-opinion-2026-03-18.md`. Key conditions incorporated: REST endpoints for positions/portfolio, rename satisfaction→confidence, critical event priority channel, Keychain for Discord webhook, SSE cleanup in finally block.

**Plan Review Fixes (post-audit):**
1. Server shutdown: Add `close_trading_manager()` function, not raw `_instance` import
2. Event bus: Remove orphaned `asyncio.Lock` (single-caller publish, no concurrent access)
3. Route layer: Add `get_trade_by_id()` and `update_trade_metadata()` to TradingDatabase — no direct `db.connection` access from routes
4. Manager: Add `@property def exchange` (public) — routes use `manager.exchange` not `manager._exchange`
5. WatchlistItemResponse: Add `model_config = ConfigDict(extra="ignore")` for Pydantic v2
6. ALTER TABLE: Use `except aiosqlite.OperationalError` not bare `except Exception`
7. SSE: Use `asyncio.get_running_loop().time()` not deprecated `get_event_loop().time()`
8. Imports: Move `uuid`/`datetime` to top-level in routes, add `from typing import Optional` to scoring.py

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `hestia/trading/database.py` | Modify | ALTER TABLE for decision_trail + confidence_score, new watchlist table |
| `hestia/trading/models.py` | Modify | Add WatchlistItem dataclass, ConfidenceScore helpers |
| `hestia/trading/executor.py` | Modify | Persist decision trail, compute confidence score, publish events |
| `hestia/trading/manager.py` | Modify | Add watchlist CRUD, positions/portfolio methods, event bus wiring |
| `hestia/trading/scoring.py` | Create | ConfidenceScorer — composite pre-execution confidence metric |
| `hestia/trading/event_bus.py` | Create | TradingEventBus — asyncio.Queue pub/sub with priority channel |
| `hestia/api/routes/trading.py` | Modify | Add SSE stream, trail, positions, portfolio, watchlist, feedback endpoints |
| `hestia/api/schemas/trading.py` | Modify | Add new request/response schemas |
| `hestia/trading/alerts.py` | Create | DiscordAlerter + push notification integration |
| `hestia/api/server.py` | Modify | Add TradingManager to startup/shutdown lifecycle |
| `HestiaApp/macOS/ViewModels/MacTradingViewModel.swift` | Create | ViewModel for trading data + SSE subscription |
| `HestiaApp/macOS/Views/Command/TradingMonitorView.swift` | Modify | Replace mock data with ViewModel bindings |
| `HestiaApp/macOS/Services/APIClient+Trading.swift` | Create | APIClient extensions for trading endpoints |
| `HestiaApp/macOS/Models/TradingModels.swift` | Create | Swift models matching backend schemas |
| `tests/test_trading_dashboard.py` | Create | Tests for scoring, event bus, new endpoints |

---

## Task 1: Database Schema + Decision Trail Persistence (~3h)

**Files:**
- Modify: `hestia/trading/database.py` (_init_schema + new methods)
- Modify: `hestia/trading/executor.py` (persist trail after execution)
- Modify: `hestia/trading/manager.py` (record_trade accepts trail + score)
- Create: `tests/test_trading_dashboard.py`

- [ ] **Step 1: Write failing tests for schema changes**

```python
# tests/test_trading_dashboard.py
"""Tests for Sprint 26 — trading dashboard features."""
import asyncio
import json
import pytest
import pytest_asyncio
from pathlib import Path

from hestia.trading.database import TradingDatabase


class TestDecisionTrailSchema:
    @pytest_asyncio.fixture
    async def db(self, tmp_path):
        db = TradingDatabase(tmp_path / "test_trading.db")
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_trade_with_decision_trail(self, db):
        """Trades table should accept decision_trail JSON column."""
        trade_data = {
            "id": "t1", "bot_id": "b1", "side": "buy", "order_type": "limit",
            "price": 65000.0, "quantity": 0.001, "fee": 0.26,
            "pair": "BTC-USD", "timestamp": "2026-03-18T12:00:00Z",
            "user_id": "user-default",
            "decision_trail": json.dumps([
                {"step": "risk_validation", "result": {"approved": True}},
                {"step": "price_validation", "result": {"valid": True}},
            ]),
            "confidence_score": 0.82,
        }
        # Need a bot first (FK constraint)
        await db.create_bot({
            "id": "b1", "name": "test", "strategy": "grid",
            "pair": "BTC-USD", "status": "running",
            "capital_allocated": 250.0, "config": {},
            "created_at": "2026-03-18T12:00:00Z",
            "updated_at": "2026-03-18T12:00:00Z",
            "user_id": "user-default",
        })
        result = await db.record_trade(trade_data)
        assert result["decision_trail"] is not None

        # Retrieve and verify
        trades = await db.get_trades(user_id="user-default", limit=1)
        assert len(trades) == 1
        trail = json.loads(trades[0].get("decision_trail", "[]"))
        assert len(trail) == 2
        assert trades[0].get("confidence_score") == 0.82

    @pytest.mark.asyncio
    async def test_watchlist_crud(self, db):
        """Watchlist table should support CRUD operations."""
        item = {
            "id": "w1", "pair": "ETH-USD", "notes": "Watching for breakout",
            "price_alerts": json.dumps({"above": 4000, "below": 3000}),
            "added_at": "2026-03-18T12:00:00Z",
            "user_id": "user-default",
        }
        await db.create_watchlist_item(item)
        items = await db.get_watchlist("user-default")
        assert len(items) == 1
        assert items[0]["pair"] == "ETH-USD"

        await db.delete_watchlist_item("w1")
        items = await db.get_watchlist("user-default")
        assert len(items) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trading_dashboard.py -v --timeout=30`
Expected: FAIL — missing columns and methods

- [ ] **Step 3: Add ALTER TABLE migration + watchlist table to database.py**

In `hestia/trading/database.py`, add to `_init_schema()` after existing CREATE TABLE statements:

```python
# Sprint 26: decision trail + confidence score columns
try:
    await self.connection.execute(
        "ALTER TABLE trades ADD COLUMN decision_trail TEXT DEFAULT '[]'"
    )
except Exception:
    pass  # Column already exists

try:
    await self.connection.execute(
        "ALTER TABLE trades ADD COLUMN confidence_score REAL DEFAULT NULL"
    )
except Exception:
    pass  # Column already exists

# Watchlist table
await self.connection.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        id TEXT PRIMARY KEY,
        pair TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        price_alerts TEXT NOT NULL DEFAULT '{}',
        added_at TEXT NOT NULL,
        user_id TEXT NOT NULL DEFAULT 'user-default'
    )
""")
await self.connection.execute(
    "CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist(user_id)"
)
```

- [ ] **Step 4: Add watchlist CRUD methods to TradingDatabase**

```python
async def create_watchlist_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
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
    cursor = await self.connection.execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [self._watchlist_row_to_dict(r) for r in rows]

async def update_watchlist_item(self, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sets, values = [], []
    for key in ("pair", "notes", "price_alerts"):
        if key in updates:
            sets.append(f"{key} = ?")
            values.append(updates[key] if key != "price_alerts" else json.dumps(updates[key]))
    if not sets:
        return None
    values.append(item_id)
    await self.connection.execute(
        f"UPDATE watchlist SET {', '.join(sets)} WHERE id = ?", values
    )
    await self.connection.commit()
    cursor = await self.connection.execute("SELECT * FROM watchlist WHERE id = ?", (item_id,))
    row = await cursor.fetchone()
    return self._watchlist_row_to_dict(row) if row else None

async def delete_watchlist_item(self, item_id: str) -> bool:
    cursor = await self.connection.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
    await self.connection.commit()
    return cursor.rowcount > 0

@staticmethod
def _watchlist_row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    d["price_alerts"] = json.loads(d.get("price_alerts", "{}"))
    return d
```

- [ ] **Step 5: Update record_trade to handle new columns**

In `database.py`, modify `record_trade()` INSERT to include new columns:

```python
async def record_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
    await self.connection.execute(
        """INSERT INTO trades (id, bot_id, side, order_type, price, quantity,
           fee, fee_currency, pair, tax_lot_id, exchange_order_id,
           timestamp, metadata, user_id, decision_trail, confidence_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade_data["id"], trade_data["bot_id"], trade_data["side"],
            trade_data.get("order_type", "limit"), trade_data["price"],
            trade_data["quantity"], trade_data.get("fee", 0.0),
            trade_data.get("fee_currency", "USD"),
            trade_data.get("pair", "BTC-USD"), trade_data.get("tax_lot_id"),
            trade_data.get("exchange_order_id"), trade_data["timestamp"],
            json.dumps(trade_data.get("metadata", {})),
            trade_data.get("user_id", "user-default"),
            trade_data.get("decision_trail", "[]"),
            trade_data.get("confidence_score"),
        ),
    )
    await self.connection.commit()
    return trade_data
```

Update `_trade_row_to_dict` to include new columns:

```python
@staticmethod
def _trade_row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    d["metadata"] = json.loads(d.get("metadata", "{}"))
    d["decision_trail"] = json.loads(d.get("decision_trail", "[]"))
    return d
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_trading_dashboard.py -v --timeout=30`
Expected: All pass

- [ ] **Step 7: Run full trading test suite for regressions**

Run: `python -m pytest tests/test_trading*.py -v --timeout=30`
Expected: 241+ tests pass (existing tests unaffected — new columns have defaults)

- [ ] **Step 8: Commit**

```bash
git add hestia/trading/database.py tests/test_trading_dashboard.py
git commit -m "feat(trading): decision trail + confidence score columns, watchlist table"
```

---

## Task 2: Confidence Scorer + Executor Integration (~2h)

**Files:**
- Create: `hestia/trading/scoring.py`
- Modify: `hestia/trading/executor.py` (compute score, persist trail)
- Modify: `hestia/trading/manager.py` (pass trail/score through record_trade)
- Test: `tests/test_trading_dashboard.py` (extend)

- [ ] **Step 1: Write failing tests for ConfidenceScorer**

Append to `tests/test_trading_dashboard.py`:

```python
from hestia.trading.scoring import ConfidenceScorer


class TestConfidenceScorer:
    def test_perfect_trade(self):
        score = ConfidenceScorer.compute(
            signal_confidence=0.9,
            requested_quantity=0.001,
            adjusted_quantity=0.001,  # No reduction
            expected_price=65000.0,
            filled_price=65000.0,     # No slippage
            volume_confirmed=True,
            trend_aligned=True,
        )
        assert score >= 0.85

    def test_risk_adjusted_trade(self):
        score = ConfidenceScorer.compute(
            signal_confidence=0.8,
            requested_quantity=0.01,
            adjusted_quantity=0.005,  # 50% reduction by risk
            expected_price=65000.0,
            filled_price=65050.0,     # Slight slippage
            volume_confirmed=True,
            trend_aligned=False,
        )
        assert 0.4 < score < 0.7

    def test_poor_execution(self):
        score = ConfidenceScorer.compute(
            signal_confidence=0.5,
            requested_quantity=0.01,
            adjusted_quantity=0.002,  # 80% reduction
            expected_price=65000.0,
            filled_price=66000.0,     # Large slippage
            volume_confirmed=False,
            trend_aligned=False,
        )
        assert score < 0.4

    def test_clamped_0_to_1(self):
        score = ConfidenceScorer.compute(
            signal_confidence=1.0,
            requested_quantity=0.001,
            adjusted_quantity=0.001,
            expected_price=65000.0,
            filled_price=65000.0,
            volume_confirmed=True,
            trend_aligned=True,
        )
        assert 0.0 <= score <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement ConfidenceScorer**

```python
# hestia/trading/scoring.py
"""Confidence scoring — composite pre-execution quality metric.

Formula: 0.30 * signal_confidence
       + 0.25 * risk_efficiency    (adjusted_qty / requested_qty)
       + 0.25 * execution_quality  (1 - abs(slippage_pct))
       + 0.20 * timing_alignment   (volume_confirmed * trend_aligned)

Renamed from "satisfaction" per second-opinion review — this is a
pre-execution confidence metric, not a post-hoc satisfaction measure.
Outcome-based scoring (P&L, MAE) deferred to Sprint 27.
"""


class ConfidenceScorer:
    """Compute composite confidence score for a trade execution."""

    WEIGHT_SIGNAL = 0.30
    WEIGHT_RISK = 0.25
    WEIGHT_EXECUTION = 0.25
    WEIGHT_TIMING = 0.20

    @staticmethod
    def compute(
        signal_confidence: float = 0.5,
        requested_quantity: float = 0.0,
        adjusted_quantity: float = 0.0,
        expected_price: float = 0.0,
        filled_price: float = 0.0,
        volume_confirmed: bool = False,
        trend_aligned: bool = False,
    ) -> float:
        # Signal confidence (0-1)
        sig = max(0.0, min(1.0, signal_confidence))

        # Risk efficiency: how much of requested size survived risk checks
        risk_eff = (adjusted_quantity / requested_quantity) if requested_quantity > 0 else 0.0
        risk_eff = max(0.0, min(1.0, risk_eff))

        # Execution quality: 1 - slippage percentage (clamped)
        if expected_price > 0:
            slippage_pct = abs(filled_price - expected_price) / expected_price
            exec_qual = max(0.0, 1.0 - slippage_pct * 20)  # 5% slippage = 0.0
        else:
            exec_qual = 0.5  # Unknown

        # Timing alignment: both volume and trend must confirm
        timing = 0.0
        if volume_confirmed:
            timing += 0.5
        if trend_aligned:
            timing += 0.5

        score = (
            ConfidenceScorer.WEIGHT_SIGNAL * sig
            + ConfidenceScorer.WEIGHT_RISK * risk_eff
            + ConfidenceScorer.WEIGHT_EXECUTION * exec_qual
            + ConfidenceScorer.WEIGHT_TIMING * timing
        )
        return max(0.0, min(1.0, round(score, 4)))
```

- [ ] **Step 4: Run scoring tests**

Run: `python -m pytest tests/test_trading_dashboard.py::TestConfidenceScorer -v`
Expected: All pass

- [ ] **Step 5: Wire scoring + trail persistence into TradeExecutor**

In `hestia/trading/executor.py`, after a successful fill (inside `if result.is_filled:`), add:

```python
from hestia.trading.scoring import ConfidenceScorer

# Compute confidence score
confidence_score = ConfidenceScorer.compute(
    signal_confidence=signal.confidence,
    requested_quantity=signal.quantity,
    adjusted_quantity=quantity,
    expected_price=signal.price,
    filled_price=result.filled_price,
    volume_confirmed=signal.metadata.get("volume_confirmed", False),
    trend_aligned=signal.metadata.get("trend_aligned", False),
)
audit["confidence_score"] = confidence_score
```

Store the audit dict as `decision_trail` in the fill dict so the caller can persist it.

- [ ] **Step 6: Run all trading tests**

Run: `python -m pytest tests/test_trading*.py -v --timeout=30`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add hestia/trading/scoring.py hestia/trading/executor.py tests/test_trading_dashboard.py
git commit -m "feat(trading): confidence scorer + decision trail in executor pipeline"
```

---

## Task 3: TradingEventBus + SSE Streaming Endpoint (~4.5h)

**Files:**
- Create: `hestia/trading/event_bus.py`
- Modify: `hestia/api/routes/trading.py` (add SSE endpoint)
- Modify: `hestia/api/schemas/trading.py` (add new schemas)
- Modify: `hestia/api/server.py` (add TradingManager to lifecycle)
- Test: `tests/test_trading_dashboard.py` (extend)

- [ ] **Step 1: Write failing tests for TradingEventBus**

```python
from hestia.trading.event_bus import TradingEventBus, TradingEvent


class TestTradingEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_receive(self):
        bus = TradingEventBus(max_queue_size=10)
        queue = bus.subscribe()
        bus.publish(TradingEvent(event_type="trade", data={"pair": "BTC-USD"}))
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event.event_type == "trade"
        bus.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_bounded_queue_drops_oldest(self):
        bus = TradingEventBus(max_queue_size=3)
        queue = bus.subscribe()
        for i in range(5):
            bus.publish(TradingEvent(event_type="trade", data={"i": i}))
        # Queue should have last 3 events (0 and 1 dropped)
        events = []
        while not queue.empty():
            events.append(await queue.get())
        assert len(events) == 3
        assert events[0].data["i"] == 2

    @pytest.mark.asyncio
    async def test_critical_events_always_delivered(self):
        bus = TradingEventBus(max_queue_size=2)
        queue = bus.subscribe()
        # Fill queue
        bus.publish(TradingEvent(event_type="trade", data={"i": 0}))
        bus.publish(TradingEvent(event_type="trade", data={"i": 1}))
        # Critical event should still get through
        bus.publish(TradingEvent(event_type="kill_switch", data={"active": True}, priority=True))
        events = []
        while not queue.empty():
            events.append(await queue.get())
        assert any(e.event_type == "kill_switch" for e in events)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self):
        bus = TradingEventBus()
        queue = bus.subscribe()
        assert bus.subscriber_count == 1
        bus.unsubscribe(queue)
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_sequence_numbers(self):
        bus = TradingEventBus()
        queue = bus.subscribe()
        bus.publish(TradingEvent(event_type="trade", data={}))
        bus.publish(TradingEvent(event_type="trade", data={}))
        e1 = await asyncio.wait_for(queue.get(), timeout=1.0)
        e2 = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert e2.sequence == e1.sequence + 1
        bus.unsubscribe(queue)
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement TradingEventBus**

```python
# hestia/trading/event_bus.py
"""Trading event bus — asyncio.Queue-based pub/sub for SSE streaming.

Each SSE client subscribes and gets its own bounded queue.
Critical events (kill_switch, risk_alert) bypass the bounded queue
to ensure delivery even under backpressure.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from hestia.logging import get_logger, LogComponent

logger = get_logger()

# Critical event types that bypass bounded queue
CRITICAL_EVENT_TYPES = {"kill_switch", "risk_alert"}


@dataclass
class TradingEvent:
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: bool = False
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = {
            "type": self.event_type,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            **self.data,
        }
        return f"id: {self.sequence}\nevent: {self.event_type}\ndata: {json.dumps(payload)}\n\n"


class TradingEventBus:
    def __init__(self, max_queue_size: int = 100) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._max_queue_size = max_queue_size
        self._sequence = 0
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=0)  # Unbounded — we manage size manually
        self._subscribers.add(queue)
        logger.debug(
            f"SSE subscriber added (total: {len(self._subscribers)})",
            component=LogComponent.TRADING,
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
        logger.debug(
            f"SSE subscriber removed (total: {len(self._subscribers)})",
            component=LogComponent.TRADING,
        )

    def publish(self, event: TradingEvent) -> None:
        self._sequence += 1
        event.sequence = self._sequence
        is_critical = event.event_type in CRITICAL_EVENT_TYPES or event.priority

        for queue in list(self._subscribers):
            if is_critical:
                # Critical events always delivered — no size limit
                queue.put_nowait(event)
            else:
                # Bounded: drop oldest if full
                if queue.qsize() >= self._max_queue_size:
                    try:
                        queue.get_nowait()  # Drop oldest
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def current_sequence(self) -> int:
        return self._sequence
```

- [ ] **Step 4: Run event bus tests**

Run: `python -m pytest tests/test_trading_dashboard.py::TestTradingEventBus -v`
Expected: All pass

- [ ] **Step 5: Add SSE streaming endpoint to routes**

In `hestia/api/routes/trading.py`, add:

```python
import asyncio
import json
from fastapi.responses import StreamingResponse
from hestia.trading.event_bus import TradingEventBus, TradingEvent

# Module-level event bus singleton
_event_bus: Optional[TradingEventBus] = None

def get_event_bus() -> TradingEventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = TradingEventBus(max_queue_size=100)
    return _event_bus


@router.get(
    "/stream",
    summary="SSE streaming for real-time trading updates",
    description="Long-lived SSE connection. Events: heartbeat, trade, position_update, risk_alert, portfolio_snapshot, kill_switch.",
)
async def trading_stream(
    device_id: str = Depends(get_device_token),
) -> StreamingResponse:
    bus = get_event_bus()

    async def event_generator():
        queue = bus.subscribe()
        try:
            # Send initial snapshot
            manager = await get_trading_manager()
            snapshot = await _build_portfolio_snapshot(manager)
            yield TradingEvent(
                event_type="portfolio_snapshot", data=snapshot
            ).to_sse()

            heartbeat_interval = 15
            last_heartbeat = asyncio.get_event_loop().time()

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    # Heartbeat
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield TradingEvent(event_type="heartbeat", data={}).to_sse()
                        last_heartbeat = now
        except asyncio.CancelledError:
            pass
        finally:
            bus.unsubscribe(queue)
            logger.debug("SSE client disconnected", component=LogComponent.TRADING)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _build_portfolio_snapshot(manager) -> Dict[str, Any]:
    """Build a full portfolio snapshot for SSE initial state."""
    risk_status = manager.get_risk_status()
    return {
        "risk": risk_status,
        "kill_switch_active": risk_status["kill_switch"]["active"],
    }
```

- [ ] **Step 6: Add positions + portfolio REST endpoints**

```python
@router.get(
    "/positions",
    summary="Get current open positions",
)
async def get_positions(
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        if not manager.exchange:
            return {"positions": {}, "total_exposure": 0.0}
        # Use position tracker if available, otherwise exchange balances
        balances = await manager.exchange.get_balances()
        positions = {}
        for currency, balance in balances.items():
            if currency != "USD" and balance.total > 0:
                ticker = await manager.exchange.get_ticker(f"{currency}-USD")
                positions[f"{currency}-USD"] = {
                    "currency": currency,
                    "quantity": balance.available,
                    "hold": balance.hold,
                    "price": ticker.get("price", 0.0),
                    "value": balance.total * ticker.get("price", 0.0),
                }
        total = sum(p["value"] for p in positions.values())
        return {"positions": positions, "total_exposure": total}
    except Exception as e:
        logger.error("Failed to get positions", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to get positions")


@router.get(
    "/portfolio",
    summary="Get portfolio overview",
)
async def get_portfolio(
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        if not manager.exchange:
            return {"total_value": 0.0, "cash": 0.0, "positions_value": 0.0, "daily_pnl": 0.0}
        balances = await manager.exchange.get_balances()
        cash = balances.get("USD", None)
        cash_value = (cash.available + cash.hold) if cash else 0.0

        positions_value = 0.0
        for currency, balance in balances.items():
            if currency != "USD" and balance.total > 0:
                ticker = await manager.exchange.get_ticker(f"{currency}-USD")
                positions_value += balance.total * ticker.get("price", 0.0)

        # Daily P&L from daily summary
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary = await manager.get_daily_summary(today)
        daily_pnl = summary["total_pnl"] if summary else 0.0

        return {
            "total_value": cash_value + positions_value,
            "cash": cash_value,
            "positions_value": positions_value,
            "daily_pnl": daily_pnl,
            "risk_status": manager.get_risk_status(),
        }
    except Exception as e:
        logger.error("Failed to get portfolio", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to get portfolio")
```

- [ ] **Step 7: Add TradingManager to server lifecycle**

In `hestia/api/server.py`, add to imports and startup/shutdown:

```python
from hestia.trading.manager import get_trading_manager
```

In the `lifespan` context manager, add to startup:
```python
# Trading manager (lazy init — only when first endpoint is called)
# No explicit startup needed, but register for shutdown
```

In shutdown, add:
```python
try:
    from hestia.trading.manager import _instance as _trading_instance
    if _trading_instance:
        await _trading_instance.close()
except Exception:
    pass
```

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/test_trading*.py tests/test_trading_dashboard.py -v --timeout=30`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add hestia/trading/event_bus.py hestia/api/routes/trading.py hestia/api/schemas/trading.py hestia/api/server.py tests/test_trading_dashboard.py
git commit -m "feat(trading): SSE event bus + streaming endpoint + positions/portfolio REST"
```

---

## Task 4: Watchlist Endpoints + Trade Trail/Feedback (~2h)

**Files:**
- Modify: `hestia/api/routes/trading.py` (watchlist CRUD + trail + feedback endpoints)
- Modify: `hestia/api/schemas/trading.py` (new schemas)
- Modify: `hestia/trading/manager.py` (watchlist delegation)
- Test: `tests/test_trading_dashboard.py` (extend)

- [ ] **Step 1: Add watchlist + trail + feedback schemas**

In `hestia/api/schemas/trading.py`:

```python
class WatchlistItemRequest(BaseModel):
    pair: str = Field(..., pattern=r"^[A-Z]{2,10}-[A-Z]{2,10}$")
    notes: str = Field(default="")
    price_alerts: Dict[str, Any] = Field(default_factory=dict)

class WatchlistItemResponse(BaseModel):
    id: str
    pair: str
    notes: str
    price_alerts: Dict[str, Any] = Field(default_factory=dict)
    added_at: str

class WatchlistResponse(BaseModel):
    items: List[WatchlistItemResponse]
    total: int

class TradeTrailResponse(BaseModel):
    trade_id: str
    decision_trail: List[Dict[str, Any]]
    confidence_score: Optional[float] = None

class TradeFeedbackRequest(BaseModel):
    rating: Literal["positive", "negative", "neutral"]
    note: str = Field(default="")
```

- [ ] **Step 2: Add endpoints**

```python
@router.get("/trades/{trade_id}/trail", response_model=TradeTrailResponse)
async def get_trade_trail(trade_id: str, device_id: str = Depends(get_device_token)):
    try:
        manager = await get_trading_manager()
        trades = await manager.get_trades(limit=1)  # Need to add get_trade_by_id
        # For now, search trades
        db = manager._database
        cursor = await db.connection.execute(
            "SELECT decision_trail, confidence_score FROM trades WHERE id = ?", (trade_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trade not found")
        return TradeTrailResponse(
            trade_id=trade_id,
            decision_trail=json.loads(row[0] or "[]"),
            confidence_score=row[1],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get trade trail", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to get trade trail")

# Watchlist CRUD
@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(device_id: str = Depends(get_device_token)):
    try:
        manager = await get_trading_manager()
        items = await manager._database.get_watchlist()
        return WatchlistResponse(
            items=[WatchlistItemResponse(**i) for i in items],
            total=len(items),
        )
    except Exception as e:
        logger.error("Failed to get watchlist", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to get watchlist")

@router.post("/watchlist", response_model=WatchlistItemResponse)
async def add_to_watchlist(request: WatchlistItemRequest, device_id: str = Depends(get_device_token)):
    import uuid
    from datetime import datetime, timezone
    try:
        manager = await get_trading_manager()
        item = {
            "id": str(uuid.uuid4()),
            "pair": request.pair,
            "notes": request.notes,
            "price_alerts": json.dumps(request.price_alerts),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        await manager._database.create_watchlist_item(item)
        item["price_alerts"] = request.price_alerts
        return WatchlistItemResponse(**item)
    except Exception as e:
        logger.error("Failed to add watchlist item", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to add to watchlist")

@router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(item_id: str, device_id: str = Depends(get_device_token)):
    try:
        manager = await get_trading_manager()
        success = await manager._database.delete_watchlist_item(item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Watchlist item not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove watchlist item", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to remove from watchlist")

@router.post("/trades/{trade_id}/feedback")
async def submit_trade_feedback(trade_id: str, request: TradeFeedbackRequest, device_id: str = Depends(get_device_token)):
    try:
        manager = await get_trading_manager()
        db = manager._database
        # Store feedback in trade metadata
        cursor = await db.connection.execute(
            "SELECT metadata FROM trades WHERE id = ?", (trade_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trade not found")
        metadata = json.loads(row[0] or "{}")
        metadata["user_feedback"] = {"rating": request.rating, "note": request.note}
        await db.connection.execute(
            "UPDATE trades SET metadata = ? WHERE id = ?",
            (json.dumps(metadata), trade_id),
        )
        await db.connection.commit()
        return {"success": True, "trade_id": trade_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit feedback", component=LogComponent.TRADING,
                     data={"error": sanitize_for_log(e)})
        raise HTTPException(status_code=500, detail="Failed to submit feedback")
```

- [ ] **Step 3: Run tests**
- [ ] **Step 4: Commit**

```bash
git add hestia/api/routes/trading.py hestia/api/schemas/trading.py hestia/trading/manager.py tests/test_trading_dashboard.py
git commit -m "feat(trading): watchlist CRUD, trade trail, feedback endpoints"
```

---

## Task 5: macOS Trading Tab Wiring (~6h)

**Files:**
- Create: `HestiaApp/macOS/Models/TradingModels.swift`
- Create: `HestiaApp/macOS/Services/APIClient+Trading.swift`
- Create: `HestiaApp/macOS/ViewModels/MacTradingViewModel.swift`
- Modify: `HestiaApp/macOS/Views/Command/TradingMonitorView.swift`

This task replaces all mock data in TradingMonitorView with live API data via a dedicated ViewModel. SSE subscription for real-time updates. REST-first architecture (load via REST, update via SSE deltas).

- [ ] **Step 1: Create TradingModels.swift**

Swift models matching backend Pydantic schemas. File: `HestiaApp/macOS/Models/TradingModels.swift`.

- [ ] **Step 2: Create APIClient+Trading.swift**

Extensions for: `getPortfolio()`, `getPositions()`, `getTrades(limit:)`, `getRiskStatus()`, `getWatchlist()`, `getTradeTrail(tradeId:)`, `activateKillSwitch(reason:)`, `deactivateKillSwitch()`, `submitTradeFeedback(tradeId:rating:note:)`.

- [ ] **Step 3: Create MacTradingViewModel.swift**

`@MainActor class MacTradingViewModel: ObservableObject` with:
- `@Published` properties: portfolio, positions, trades, riskStatus, watchlist, isLoading, errorMessage, killSwitchActive
- `loadAllData()` — parallel `async let` for all REST endpoints
- SSE subscription: `URLSession` with `text/event-stream` parsing, auto-reconnect
- Kill switch toggle method
- Periodic refresh (every 30s when SSE disconnected)

- [ ] **Step 4: Rewrite TradingMonitorView to use ViewModel**

Replace all mock data with `@ObservedObject var viewModel: MacTradingViewModel` bindings:
- Portfolio snapshot: `viewModel.portfolio.totalValue`, `.dailyPnl`
- Active positions: `ForEach(viewModel.positions)`
- Recent trades: `ForEach(viewModel.trades)` with expandable decision trail from `viewModel.getTradeTrail(id)`
- Risk status: `viewModel.riskStatus` traffic light + metrics
- Kill switch: `viewModel.toggleKillSwitch()`
- Watchlist: `viewModel.watchlist`

- [ ] **Step 5: Wire into ExternalActivityView**

Pass ViewModel to TradingMonitorView. Create ViewModel in ExternalActivityView or CommandView.

- [ ] **Step 6: Build and verify**

Run: `xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -destination 'platform=macOS' build`
Expected: BUILD SUCCEEDED

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/macOS/Models/TradingModels.swift HestiaApp/macOS/Services/APIClient+Trading.swift HestiaApp/macOS/ViewModels/MacTradingViewModel.swift HestiaApp/macOS/Views/Command/TradingMonitorView.swift
git commit -m "feat(macOS): wire Trading tab with live data + SSE streaming"
```

---

## Task 6: Alert System (~3h)

**Files:**
- Create: `hestia/trading/alerts.py`
- Modify: `hestia/trading/risk.py` (publish events on breaker trigger)
- Modify: `hestia/trading/executor.py` (publish trade events)
- Test: `tests/test_trading_dashboard.py` (extend)

- [ ] **Step 1: Implement DiscordAlerter**

```python
# hestia/trading/alerts.py
"""Trading alerts — Discord webhook + push notification integration.

Discord webhook URL stored in Keychain (not config file — per second-opinion).
Rate limiting: max 1 msg/min per event type, batch consolidation.
Fully optional — fails silent if webhook not configured.
"""
```

- [ ] **Step 2: Wire event publishing into RiskManager and TradeExecutor**

When a circuit breaker triggers, publish `risk_alert` event to the bus.
When a trade executes, publish `trade` event with trail + confidence score.
When kill switch changes, publish `kill_switch` event.

- [ ] **Step 3: Add push notification integration**

Use existing `NotificationManager.create_bump()` for:
- Circuit breaker trigger → High priority
- Kill switch → Critical priority (bypass quiet hours)
- Daily summary → Low priority scheduled

- [ ] **Step 4: Tests + commit**

```bash
git add hestia/trading/alerts.py hestia/trading/risk.py hestia/trading/executor.py tests/test_trading_dashboard.py
git commit -m "feat(trading): Discord + push alerts with rate limiting"
```

---

## Post-Implementation Checklist

- [ ] Update CLAUDE.md endpoint count (209 → ~221 after new endpoints)
- [ ] Update CLAUDE.md project structure (new files)
- [ ] Run @hestia-reviewer on all changed files
- [ ] Run @hestia-tester for full suite verification
- [ ] Run @hestia-build-validator for macOS build
- [ ] Update SPRINT.md with Sprint 26 completion
- [ ] Commit docs updates
