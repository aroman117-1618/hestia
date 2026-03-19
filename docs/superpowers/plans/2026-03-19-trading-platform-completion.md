# Trading Platform Completion (S27-S30) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Hestia's personal investment platform — finish crypto go-live, add Alpaca stock trading, multi-asset tax/intelligence, and Bayesian optimization.

**Architecture:** Phased de-risking: prove crypto live → read-only Alpaca → full Alpaca → optimization. Each phase validates before the next increases financial risk. Tax module extracted early (lowest risk window). CSV export as primary tax reporting, in-house wash sale as PoC only.

**Tech Stack:** Python 3.12/FastAPI, alpaca-py SDK, Coinbase SDK, Optuna, pandas-ta, SQLite WAL, macOS Keychain

---

## File Map

### S27 — Crypto Go-Live Hardening
| Action | File | Purpose |
|--------|------|---------|
| Create | `hestia/trading/tax.py` | Extracted tax logic (lot matching, P&L calc, CSV export) |
| Create | `hestia/trading/product_info.py` | Exchange product metadata (min order size, increments) |
| Modify | `hestia/trading/database.py` | Remove tax logic (delegate to tax.py), add asset_class migration |
| Modify | `hestia/trading/manager.py` | Use new tax.py, add product validation |
| Modify | `hestia/trading/risk.py` | Remove dead breakers (SINGLE_TRADE, VOLATILITY, CONNECTIVITY) |
| Modify | `hestia/trading/bot_runner.py` | Wire Bollinger + DCA into factory |
| Modify | `hestia/trading/executor.py` | Partial fill handling |
| Create | `tests/test_trading_tax.py` | Tax module tests |
| Create | `tests/test_trading_product_info.py` | Product info tests |

### S28 — Alpaca + Stock Trading
| Action | File | Purpose |
|--------|------|---------|
| Create | `hestia/trading/exchange/alpaca.py` | AlpacaAdapter (read-only first, then full) |
| Create | `hestia/trading/market_hours.py` | US market hours scheduler + holiday calendar |
| Create | `hestia/trading/strategies/momentum.py` | SMA crossover for equities |
| Create | `hestia/trading/strategies/swing.py` | RSI + volume swing strategy |
| Modify | `hestia/trading/models.py` | AssetClass enum, asset_class fields |
| Modify | `hestia/trading/database.py` | asset_class column migrations |
| Modify | `hestia/trading/bot_runner.py` | Market hours gating in tick loop |
| Modify | `hestia/trading/manager.py` | Multi-exchange adapter selection |
| Modify | `hestia/trading/risk.py` | PDT rule enforcement |
| Modify | `hestia/config/trading.yaml` | alpaca: section |
| Create | `tests/test_trading_alpaca.py` | Alpaca adapter tests |
| Create | `tests/test_trading_market_hours.py` | Market hours + holiday tests |
| Create | `tests/test_trading_pdt.py` | PDT rule tests |
| Create | `tests/test_trading_stock_strategies.py` | Momentum + swing tests |

### S29 — Multi-Asset Intelligence
| Action | File | Purpose |
|--------|------|---------|
| Create | `hestia/trading/regime.py` | LLM regime detection (observe-only) |
| Create | `hestia/trading/coingecko.py` | Secondary price feed |
| Modify | `hestia/trading/tax.py` | Wash sale PoC, equity FIFO |
| Modify | `hestia/trading/risk.py` | Per-asset-class PnL tracking |
| Create | `tests/test_trading_regime.py` | Regime detection tests |

### S30 — Optimization + On-Chain
| Action | File | Purpose |
|--------|------|---------|
| Create | `hestia/trading/optimizer.py` | Optuna parameter tuning |
| Create | `hestia/trading/onchain.py` | CryptoQuant/Dune signals |
| Modify | `hestia/trading/backtest/engine.py` | Walk-forward validation enhancement |
| Create | `tests/test_trading_optimizer.py` | Optimizer + anti-overfit tests |

---

## Sprint 27: Crypto Go-Live Hardening (~7h)

### Task 1: Extract Tax Module from database.py

**Files:**
- Create: `hestia/trading/tax.py`
- Modify: `hestia/trading/manager.py:175-250` (only P&L math delegates to TaxLotTracker — transaction wrapper + DB calls stay in manager.py)
- Create: `tests/test_trading_tax.py`
- NOTE: `database.py` tax lot CRUD (`create_tax_lot_no_commit`, `update_tax_lot_no_commit`, `get_open_tax_lots`) stays in database.py. Only lot selection/matching logic moves to tax.py. The `BEGIN IMMEDIATE / COMMIT / ROLLBACK` wrapper in manager.py is NOT moved.

- [ ] **Step 1: Write failing test for TaxLotTracker**

```python
# tests/test_trading_tax.py
import pytest
from hestia.trading.tax import TaxLotTracker

def test_buy_creates_tax_lot():
    tracker = TaxLotTracker(method="hifo")
    lot = tracker.create_lot_from_buy(
        trade_id="t1", pair="BTC-USD", quantity=0.01,
        price=87000.0, fee=3.48, acquired_at="2026-03-19T12:00:00Z"
    )
    assert lot["quantity"] == 0.01
    assert lot["cost_basis"] == 873.48  # (0.01 * 87000) + 3.48 fee
    assert lot["cost_per_unit"] == 87348.0
    assert lot["method"] == "hifo"
    assert lot["status"] == "open"

def test_sell_consumes_hifo_lot():
    tracker = TaxLotTracker(method="hifo")
    lots = [
        {"id": "l1", "cost_per_unit": 85000.0, "remaining_quantity": 0.01, "cost_basis": 850.0, "status": "open"},
        {"id": "l2", "cost_per_unit": 90000.0, "remaining_quantity": 0.01, "cost_basis": 900.0, "status": "open"},
    ]
    result = tracker.match_lots_for_sell(lots, quantity=0.01, sell_price=88000.0)
    # HIFO: should consume l2 (highest cost) first
    assert result["consumed_lots"][0]["lot_id"] == "l2"
    assert result["realized_pnl"] == -20.0  # (88000 - 90000) * 0.01

def test_hifo_sorts_internally():
    """match_lots_for_sell sorts by method even if caller passes unsorted lots."""
    tracker = TaxLotTracker(method="hifo")
    lots = [
        {"id": "l1", "cost_per_unit": 85000.0, "remaining_quantity": 0.01, "cost_basis": 850.0, "status": "open"},
        {"id": "l2", "cost_per_unit": 90000.0, "remaining_quantity": 0.01, "cost_basis": 900.0, "status": "open"},
    ]
    # Passed in wrong order (lowest first) — HIFO should still pick l2
    result = tracker.match_lots_for_sell(lots, quantity=0.01, sell_price=88000.0)
    assert result["consumed_lots"][0]["lot_id"] == "l2"

def test_csv_export():
    tracker = TaxLotTracker(method="hifo")
    trades = [
        {"id": "t1", "side": "buy", "price": 87000.0, "quantity": 0.01, "fee": 3.48, "pair": "BTC-USD", "timestamp": "2026-03-19T12:00:00Z"},
        {"id": "t2", "side": "sell", "price": 88000.0, "quantity": 0.005, "fee": 2.64, "pair": "BTC-USD", "timestamp": "2026-03-20T12:00:00Z"},
    ]
    csv_str = tracker.export_trades_csv(trades)
    assert "Date,Type,Asset,Quantity,Price,Fee,Total,Exchange" in csv_str
    assert "BTC-USD" in csv_str
    lines = csv_str.strip().split("\n")
    assert len(lines) == 3  # header + 2 trades
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trading_tax.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.trading.tax'`

- [ ] **Step 3: Implement TaxLotTracker**

```python
# hestia/trading/tax.py
"""
Tax lot tracking — extracted from database.py for safe refactoring.

Handles HIFO/FIFO lot matching, P&L calculation, and CSV export.
Database operations remain in database.py — this module is pure logic.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

logger = get_logger()


class TaxLotTracker:
    """Pure-logic tax lot operations. No database access."""

    def __init__(self, method: str = "hifo") -> None:
        if method not in ("hifo", "fifo"):
            raise ValueError(f"Invalid method: {method}")
        self.method = method

    def create_lot_from_buy(
        self,
        trade_id: str,
        pair: str,
        quantity: float,
        price: float,
        fee: float,
        acquired_at: str,
        user_id: str = "user-default",
    ) -> Dict[str, Any]:
        """Create a tax lot dict from a buy trade. Cost basis includes fees."""
        cost_basis = (quantity * price) + fee
        cost_per_unit = cost_basis / quantity if quantity > 0 else 0.0
        return {
            "id": f"lot-{uuid.uuid4().hex[:12]}",
            "trade_id": trade_id,
            "pair": pair,
            "quantity": quantity,
            "remaining_quantity": quantity,
            "cost_basis": cost_basis,
            "cost_per_unit": cost_per_unit,
            "method": self.method,
            "status": "open",
            "acquired_at": acquired_at,
            "closed_at": None,
            "realized_pnl": 0.0,
            "user_id": user_id,
        }

    def match_lots_for_sell(
        self,
        open_lots: List[Dict[str, Any]],
        quantity: float,
        sell_price: float,
    ) -> Dict[str, Any]:
        """Match open lots against a sell. Returns consumed lots + P&L."""
        # Sort internally by method so callers cannot misuse ordering
        if self.method == "hifo":
            sorted_lots = sorted(open_lots, key=lambda l: l["cost_per_unit"], reverse=True)
        else:  # fifo
            sorted_lots = sorted(open_lots, key=lambda l: l.get("acquired_at", ""))
        remaining = quantity
        consumed = []
        total_pnl = 0.0

        for lot in sorted_lots:
            if remaining <= 0:
                break
            take = min(remaining, lot["remaining_quantity"])
            pnl = (sell_price - lot["cost_per_unit"]) * take
            consumed.append({
                "lot_id": lot["id"],
                "quantity_consumed": take,
                "pnl": pnl,
                "new_remaining": lot["remaining_quantity"] - take,
                "new_status": "closed" if take >= lot["remaining_quantity"] else "partial",
            })
            total_pnl += pnl
            remaining -= take

        return {
            "consumed_lots": consumed,
            "realized_pnl": total_pnl,
            "unfilled_quantity": max(0, remaining),
        }

    def export_trades_csv(self, trades: List[Dict[str, Any]]) -> str:
        """Export trades to CSV for TurboTax/tax software import."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Type", "Asset", "Quantity", "Price", "Fee", "Total", "Exchange"])
        for t in trades:
            total = t["price"] * t["quantity"]
            writer.writerow([
                t["timestamp"],
                t["side"].upper(),
                t["pair"],
                t["quantity"],
                t["price"],
                t.get("fee", 0.0),
                round(total, 2),
                t.get("exchange", "coinbase"),
            ])
        return output.getvalue()


# TaxReport class deferred to S29 — not needed until multi-asset tax summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trading_tax.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Wire TaxLotTracker into manager.py record_trade()**

Modify `hestia/trading/manager.py` — replace inline lot logic with `TaxLotTracker` calls. The database CRUD stays in `database.py`, but lot matching logic delegates to `tax.py`.

- [ ] **Step 6: Run full trading test suite**

Run: `python -m pytest tests/test_trading*.py -v`
Expected: All existing tests still pass (behavior unchanged)

- [ ] **Step 7: Commit**

```bash
git add hestia/trading/tax.py tests/test_trading_tax.py hestia/trading/manager.py
git commit -m "refactor(trading): extract tax lot logic into tax.py — CSV export + lot matching"
```

---

### Task 2: Product Metadata + Order Size Validation

**Files:**
- Create: `hestia/trading/product_info.py`
- Modify: `hestia/trading/executor.py:43-100`
- Create: `tests/test_trading_product_info.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_trading_product_info.py
import pytest
from hestia.trading.product_info import ProductInfo, validate_order_size

def test_btc_usd_minimum():
    info = ProductInfo(
        pair="BTC-USD",
        base_min_size=0.0001,
        base_increment=0.00000001,
        quote_increment=0.01,
    )
    assert info.min_quote_value(87000.0) == pytest.approx(8.70, rel=0.01)

def test_order_below_minimum_rejected():
    info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
    result = validate_order_size(info, quantity=0.00005, price=87000.0)
    assert result["valid"] is False
    assert "below minimum" in result["reason"].lower()

def test_order_above_minimum_accepted():
    info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
    result = validate_order_size(info, quantity=0.001, price=87000.0)
    assert result["valid"] is True
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement ProductInfo**

```python
# hestia/trading/product_info.py
"""Exchange product metadata — minimum order sizes, increments."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ProductInfo:
    """Product trading constraints from exchange."""
    pair: str = "BTC-USD"
    base_min_size: float = 0.0001      # Min base currency (e.g., 0.0001 BTC)
    base_increment: float = 0.00000001 # Smallest base increment
    quote_increment: float = 0.01      # Smallest quote increment (USD)
    base_max_size: float = 1000.0      # Max base currency per order

    def min_quote_value(self, price: float) -> float:
        """Minimum order value in quote currency at given price."""
        return self.base_min_size * price


def validate_order_size(
    info: ProductInfo,
    quantity: float,
    price: float,
) -> Dict[str, Any]:
    """Validate order against product constraints."""
    if quantity < info.base_min_size:
        return {
            "valid": False,
            "reason": f"Quantity {quantity} below minimum {info.base_min_size} for {info.pair}",
        }
    if quantity > info.base_max_size:
        return {
            "valid": False,
            "reason": f"Quantity {quantity} above maximum {info.base_max_size} for {info.pair}",
        }
    return {"valid": True, "reason": ""}
```

- [ ] **Step 4: Run tests — expect PASS**
- [ ] **Step 5: Wire into TradeExecutor.execute_signal() as pipeline step**

Add between risk validation and exchange submission in `executor.py`.

- [ ] **Step 6: Commit**

```bash
git add hestia/trading/product_info.py tests/test_trading_product_info.py hestia/trading/executor.py
git commit -m "feat(trading): product metadata validation — reject sub-minimum orders"
```

---

### Task 3: Wire Bollinger Breakout + Signal DCA into Factory

**Files:**
- Modify: `hestia/trading/bot_runner.py:40-49`
- Verify: `hestia/trading/strategies/` (check if implementations exist)

- [ ] **Step 1: Check if strategy files exist**

Run: `ls hestia/trading/strategies/`
If `bollinger.py` or `signal_dca.py` don't exist, they need to be created. If they do exist, just wire the factory.

- [ ] **Step 2: Write failing test in `tests/test_trading_golive.py`, class `TestStrategyFactory`**

```python
# Add to tests/test_trading_golive.py, inside existing TestStrategyFactory class
def test_create_bollinger_strategy(self):
    s = _create_strategy(StrategyType.BOLLINGER_BREAKOUT, {"pair": "BTC-USD"})
    assert s.strategy_type == "bollinger_breakout"

def test_create_signal_dca_strategy(self):
    s = _create_strategy(StrategyType.SIGNAL_DCA, {"pair": "BTC-USD"})
    assert s.strategy_type == "signal_dca"
```

- [ ] **Step 3: Add factory branches**

```python
# bot_runner.py:40-49 — add two elif branches
elif strategy_type == StrategyType.BOLLINGER_BREAKOUT:
    from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
    return BollingerBreakoutStrategy(config)
elif strategy_type == StrategyType.SIGNAL_DCA:
    from hestia.trading.strategies.signal_dca import SignalDCAStrategy
    return SignalDCAStrategy(config)
```

**NOTE:** Neither `hestia/trading/strategies/bollinger.py` nor `signal_dca.py` exist yet. Both must be created implementing `BaseStrategy` ABC: `name` property, `strategy_type` property, and `analyze(df: pd.DataFrame, portfolio_value: float) -> Signal`. See `strategies/mean_reversion.py` as reference. Config comes from `trading.yaml` sections `strategies.bollinger` and `strategies.signal_dca`.

- [ ] **Step 4: Run tests — expect PASS**
- [ ] **Step 5: Commit**

```bash
git add hestia/trading/bot_runner.py hestia/trading/strategies/
git commit -m "feat(trading): wire Bollinger breakout + signal DCA into strategy factory"
```

---

### Task 4: Dead Circuit Breaker Cleanup

**Files:**
- Modify: `hestia/trading/models.py:58-67`
- Modify: `hestia/trading/risk.py`

- [ ] **Step 1: Add unknown-key guard to `restore_state()` in risk.py**

Before removing enum values, add safety in `restore_state()` to skip unknown breaker keys:
```python
# In restore_state(), when reconstructing CircuitBreakerType from stored string:
try:
    breaker_type = CircuitBreakerType(key)
except ValueError:
    logger.warning(f"Skipping unknown breaker type from persisted state: {key}", component=LogComponent.TRADING)
    continue
```
This prevents server crash on restart if `risk_state` table has old breaker keys.

- [ ] **Step 2: Remove SINGLE_TRADE, VOLATILITY, CONNECTIVITY from CircuitBreakerType enum**

Also remove from `_IMPLEMENTED_BREAKERS` set if present.

- [ ] **Step 3: Update trading.yaml — remove the 3 dead breaker configs**

- [ ] **Step 4: Run tests — fix any assertions referencing removed breakers**

- [ ] **Step 4: Commit**

```bash
git add hestia/trading/models.py hestia/trading/risk.py hestia/config/trading.yaml
git commit -m "fix(trading): remove 3 dead circuit breakers (SINGLE_TRADE, VOLATILITY, CONNECTIVITY)"
```

---

### Task 5: Partial Fill Handling

**Files:**
- Modify: `hestia/trading/executor.py`
- Modify: `hestia/trading/models.py` (OrderResult already has `filled_quantity`)

- [ ] **Step 1: Identify the actual gap**

The current `executor.py` only acts on `result.is_filled` (which checks `status == "filled"`). Orders with `status == "partial"` are silently dropped — no fill recorded, no tax lot created. This is the real bug.

- [ ] **Step 2: Write failing test**

```python
def test_partial_fill_is_recorded():
    """When exchange returns status='partial', executor should still record the filled portion."""
    # Mock exchange that returns partial fill
    # executor.execute_signal() currently only processes is_filled (status=="filled")
    # It should also process status=="partial" using filled_quantity
    result = OrderResult(status="partial", quantity=0.01, filled_quantity=0.006, price=87000.0, filled_price=87010.0)
    assert result.is_open  # partial is still "open" per current code
    assert not result.is_filled
    # After fix: executor should treat partial fills as actionable
```

- [ ] **Step 3: Update executor to handle partial fills**

In `executor.py`, after exchange returns OrderResult, add a branch: if `result.status == "partial"`, record the fill using `result.filled_quantity` and `result.filled_price`. Add "partial_fill" to the decision trail metadata. The remaining unfilled quantity is logged but not resubmitted (that's a future enhancement).

- [ ] **Step 3: Run tests — expect PASS**
- [ ] **Step 4: Commit**

```bash
git add hestia/trading/executor.py
git commit -m "fix(trading): handle partial fills — record actual filled quantity"
```

---

### Task 6: Add CSV Trade Export API Endpoint

**Files:**
- Modify: `hestia/api/routes/trading.py`

- [ ] **Step 1: Add endpoint**

```python
@router.get("/v1/trading/export/csv")
async def export_trades_csv(
    year: Optional[int] = None,
    user_id: str = "user-default",
    token: str = Depends(get_device_token),  # AUTH REQUIRED — matches all other trading routes
):
    """Export all trades as CSV for tax software import."""
    from hestia.trading.tax import TaxLotTracker
    manager = await get_trading_manager()
    trades = await manager.get_trades(user_id=user_id, limit=10000)
    if year:
        trades = [t for t in trades if t["timestamp"].startswith(str(year))]
    tracker = TaxLotTracker()
    csv_content = tracker.export_trades_csv(trades)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(csv_content, media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=hestia-trades-{year or 'all'}.csv"})
```

- [ ] **Step 2: Write test for endpoint**

```python
# In test file for trading routes, or tests/test_trading_tax.py
@pytest.mark.asyncio
async def test_csv_export_endpoint(test_client, mock_auth):
    response = await test_client.get("/v1/trading/export/csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "Date,Type,Asset" in response.text
```

- [ ] **Step 3: Commit**

```bash
git add hestia/api/routes/trading.py
git commit -m "feat(trading): CSV trade export endpoint for tax software"
```

---

### Task 7: Database Migration — asset_class Column

**Files:**
- Modify: `hestia/trading/database.py:168-177`
- Modify: `hestia/trading/models.py`

- [ ] **Step 1: Add AssetClass enum to models.py**

```python
class AssetClass(str, Enum):
    CRYPTO = "crypto"
    US_EQUITY = "us_equity"
```

- [ ] **Step 2: Add migration in database.py _init_schema()**

```python
# After existing Sprint 26 migrations
for col_sql in [
    "ALTER TABLE bots ADD COLUMN asset_class TEXT DEFAULT 'crypto'",
    "ALTER TABLE trades ADD COLUMN asset_class TEXT DEFAULT 'crypto'",
    "ALTER TABLE tax_lots ADD COLUMN asset_class TEXT DEFAULT 'crypto'",
    "ALTER TABLE trades ADD COLUMN settlement_date TEXT DEFAULT NULL",
]:
    try:
        await self.connection.execute(col_sql)
    except aiosqlite.OperationalError:
        pass
```

- [ ] **Step 3: Add `settlement_date` to Trade dataclass in models.py**

```python
# In Trade dataclass, add field:
settlement_date: Optional[str] = None
```
Also update `to_dict()` and `from_dict()` to include `settlement_date`.

- [ ] **Step 4: Run full test suite**
- [ ] **Step 5: Commit**

```bash
git add hestia/trading/models.py hestia/trading/database.py
git commit -m "feat(trading): add asset_class + settlement_date columns — prepare for multi-asset"
```

---

### Task 8: Dependency Lockfile (S27 only — no new deps)

**NOTE:** `alpaca-py` deferred to S28B (Task 13) start. `optuna` deferred to S30 (Task 22) start. Adding deps before consumers exist risks compile conflicts that block all S27 work.

- [ ] **Step 1: Pin existing trading deps in requirements.in** (ensure coinbase-advanced-py, pandas-ta are locked)
- [ ] **Step 2: Recompile**

Run: `uv pip compile requirements.in --python-version 3.11 --output-file requirements.txt --no-emit-index-url`

- [ ] **Step 3: Commit**

```bash
git add requirements.in requirements.txt
git commit -m "deps: pin trading dependencies in lockfile"
```

---

## Sprint 28A: Strategy Wiring + Backtesting (~8h)

### Task 9: Implement Bollinger Breakout Strategy (if not exists)

**Files:**
- Create: `hestia/trading/strategies/bollinger.py`
- Create: `tests/test_trading_stock_strategies.py`

- [ ] **Step 1: Write failing test** — strategy returns BUY when price breaks above upper Bollinger band with volume confirmation
- [ ] **Step 2: Implement BollingerBreakoutStrategy** extending BaseStrategy
- [ ] **Step 3: Run tests — PASS**
- [ ] **Step 4: Commit**

### Task 10: Implement Signal DCA Strategy (if not exists)

**Files:**
- Create: `hestia/trading/strategies/signal_dca.py`

- [ ] **Step 1: Write failing test** — DCA buys on RSI dips below threshold, respects buy_interval_hours
- [ ] **Step 2: Implement SignalDCAStrategy**
- [ ] **Step 3: Run tests — PASS**
- [ ] **Step 4: Commit**

### Task 11: Backtest New Strategies on 90d Data

- [ ] **Step 1: Fetch 90d BTC-USD candles via data_loader**
- [ ] **Step 2: Run BacktestEngine on Bollinger + DCA**
- [ ] **Step 3: Log results (Sharpe, max drawdown, win rate)**
- [ ] **Step 4: Commit results to `docs/backtests/`**

---

## Sprint 28B: AlpacaAdapter (Read-Only) + Market Hours (~10h)

**Gate: 2 weeks live crypto clean**

### Task 12: Market Hours Scheduler

**Files:**
- Create: `hestia/trading/market_hours.py`
- Create: `tests/test_trading_market_hours.py`

- [ ] **Step 1: Write failing tests**

```python
from hestia.trading.market_hours import MarketHoursScheduler
from datetime import datetime

def test_regular_session_open():
    sched = MarketHoursScheduler()
    # Tuesday 10:30 AM ET = open
    dt = datetime(2026, 3, 24, 14, 30, 0)  # UTC
    assert sched.is_market_open(dt) is True

def test_weekend_closed():
    sched = MarketHoursScheduler()
    dt = datetime(2026, 3, 22, 14, 30, 0)  # Sunday UTC
    assert sched.is_market_open(dt) is False

def test_holiday_closed():
    sched = MarketHoursScheduler()
    # 2026-01-01 = New Year's Day
    dt = datetime(2026, 1, 1, 14, 30, 0)
    assert sched.is_market_open(dt) is False

def test_crypto_always_open():
    sched = MarketHoursScheduler()
    assert sched.is_market_open(datetime(2026, 3, 22, 3, 0, 0), asset_class="crypto") is True
```

- [ ] **Step 2: Implement MarketHoursScheduler** — US market hours (EST), holiday calendar (NYSE closures), pre/post market awareness
- [ ] **Step 3: Wire into BotRunner._tick()** — skip tick if market closed and asset_class == "us_equity"
- [ ] **Step 4: Run tests — PASS**
- [ ] **Step 5: Commit**

### Task 13: AlpacaAdapter (Read-Only)

**Files:**
- Create: `hestia/trading/exchange/alpaca.py`
- Create: `tests/test_trading_alpaca.py`

- [ ] **Step 1: Write failing tests** — `get_ticker()`, `get_balances()`, `get_account()`, `get_ohlcv()` (historical candles)
- [ ] **Step 2: Implement AlpacaAdapter** extending AbstractExchangeAdapter. Only data methods — `place_order()` raises NotImplementedError for now.
- [ ] **Step 3: Add `alpaca:` section to trading.yaml**
- [ ] **Step 4: Wire adapter selection in manager.py** — mode "alpaca_paper" / "alpaca_live"
- [ ] **Step 5: Run tests — PASS**
- [ ] **Step 6: Commit**

### Task 14: Stock Strategies (Momentum + Swing)

**Files:**
- Create: `hestia/trading/strategies/momentum.py`
- Create: `hestia/trading/strategies/swing.py`

- [ ] **Step 1: Write failing tests** — momentum: BUY on SMA-20 cross above SMA-50; swing: BUY on RSI<30 + volume spike
- [ ] **Step 2: Implement both strategies** extending BaseStrategy
- [ ] **Step 3: Wire into `_create_strategy()` factory** — add StrategyType.MOMENTUM and StrategyType.SWING to enum + factory
- [ ] **Step 4: Run tests — PASS**
- [ ] **Step 5: Commit**

### Task 15: Simulated Stock Signal Generation

- [ ] **Step 1: Fetch 90d AAPL + SPY data via AlpacaAdapter**
- [ ] **Step 2: Run momentum + swing strategies on historical data**
- [ ] **Step 3: Log hypothetical signals — validate market hours scheduler**
- [ ] **Step 4: Document findings in `docs/backtests/stock-strategies-simulation.md`**

---

## Sprint 29A: Full Alpaca + PDT (~10h)

**Gate: Simulation validated**

### Task 16: AlpacaAdapter Full Implementation

**Files:**
- Modify: `hestia/trading/exchange/alpaca.py`

- [ ] **Step 1: Implement `place_order()`, `cancel_order()`, `get_order()`, `get_open_orders()`**
- [ ] **Step 2: Write integration tests** (use Alpaca paper trading API)
- [ ] **Step 3: Commit**

### Task 17: PDT Rule Enforcement

**Files:**
- Modify: `hestia/trading/risk.py`
- Modify: `hestia/trading/database.py`
- Create: `tests/test_trading_pdt.py`

- [ ] **Step 1: Write failing tests**

```python
def test_pdt_blocks_4th_day_trade():
    """Account < $25K with 3 day trades in 5 rolling days → block 4th."""
    rm = RiskManager(config={"risk": {"pdt": {"enabled": True, "account_threshold": 25000}}})
    # Simulate 3 same-day round trips
    for i in range(3):
        rm.record_day_trade("2026-04-01")
    result = rm.check_pdt_compliance(portfolio_value=5000.0, trade_date="2026-04-02")
    assert result["allowed"] is False
    assert "PDT" in result["reason"]

def test_pdt_allows_above_25k():
    rm = RiskManager(config={"risk": {"pdt": {"enabled": True}}})
    for i in range(5):
        rm.record_day_trade("2026-04-01")
    result = rm.check_pdt_compliance(portfolio_value=30000.0, trade_date="2026-04-02")
    assert result["allowed"] is True  # Above $25K = exempt

def test_pdt_rolling_window():
    """Day trades older than 5 business days don't count."""
    rm = RiskManager(config={"risk": {"pdt": {"enabled": True}}})
    rm.record_day_trade("2026-03-20")  # > 5 business days ago
    rm.record_day_trade("2026-03-20")
    rm.record_day_trade("2026-03-20")
    result = rm.check_pdt_compliance(portfolio_value=5000.0, trade_date="2026-04-01")
    assert result["allowed"] is True  # Old trades expired from window
```

- [ ] **Step 2: Add day_trade tracking table** in database.py
- [ ] **Step 3: Implement `check_pdt_compliance()` and `record_day_trade()` in risk.py**
- [ ] **Step 4: Wire into executor pipeline** for us_equity trades only
- [ ] **Step 5: Run tests — PASS**
- [ ] **Step 6: Commit**

### Task 18: Alpaca Paper Soak Setup

- [ ] **Step 1: Create stock bot via API** — momentum on SPY, $100 paper capital
- [ ] **Step 2: Start bot** — verify market hours gating works (skips ticks outside 9:30-4 ET)
- [ ] **Step 3: Monitor for 1 week** — validate PDT counter, signal generation, market hours
- [ ] **Step 4: Document results**

---

## Sprint 29B: Equity Live + Regime Detection (~8h)

**Gate: Paper soak + PDT validated**

### Task 19: CoinGecko Secondary Price Feed

**Files:**
- Create: `hestia/trading/coingecko.py`

- [ ] **Step 1: Implement CoinGecko REST client** — `/api/v3/simple/price`
- [ ] **Step 2: Wire into PriceValidator** as secondary feed for crypto
- [ ] **Step 3: Commit**

### Task 20: LLM Regime Detection (Observe-Only)

**Files:**
- Create: `hestia/trading/regime.py`
- Create: `tests/test_trading_regime.py`

- [ ] **Step 1: Implement RegimeDetector** — calls cloud inference to classify market regime (trending/ranging/volatile)
- [ ] **Step 2: Observe-only mode** — log classification to trading database, do NOT gate strategy activation
- [ ] **Step 3: Wire into BotRunner** — call regime detector on each tick, log result
- [ ] **Step 4: Commit**

### Task 21: Equity Live ($100)

- [ ] **Step 1: Flip Alpaca config to live** (same API, different base URL)
- [ ] **Step 2: Create momentum bot** — SPY, $100, confirm PDT enforcement
- [ ] **Step 3: Monitor first week** — validate fills, settlement tracking, tax lot creation

---

## Sprint 30: Optimization + On-Chain (~18h)

**Gate: 30 days live equity**

### Task 22: Optuna Parameter Optimizer

**Files:**
- Create: `hestia/trading/optimizer.py`
- Create: `tests/test_trading_optimizer.py`

- [ ] **Step 1: Implement OptunaOptimizer** — wraps Optuna study with BacktestEngine as objective function
- [ ] **Step 2: Walk-forward validation** — 30d train / 7d validate rolling windows
- [ ] **Step 3: Anti-overfit guardrails** — min 90d data, parameter bounds, Sharpe >3.0 warning
- [ ] **Step 4: Per-asset-class optimization** (crypto params ≠ stock params)
- [ ] **Step 5: Commit**

### Task 23: Wash Sale PoC

**Files:**
- Modify: `hestia/trading/tax.py`

- [ ] **Step 1: Implement wash sale detector** — 31-day window, same-ticker matching for equities only
- [ ] **Step 2: PoC mode** — flag wash sales in tax lot metadata, do NOT adjust cost basis automatically
- [ ] **Step 3: Compare against CSV export** fed into TurboTax — validate detection accuracy
- [ ] **Step 4: Commit**

### Task 24: CryptoQuant On-Chain Signals

**Files:**
- Create: `hestia/trading/onchain.py`

- [ ] **Step 1: Implement CryptoQuant client** — exchange inflow/outflow for BTC
- [ ] **Step 2: Point-in-time ingestion** — timestamp when data was available, not event time
- [ ] **Step 3: Signal as regime overlay** — accumulation/distribution phase detection
- [ ] **Step 4: Observe-only** — log signals, do not gate trades
- [ ] **Step 5: Commit**

---

## Completion Checklist

- [ ] S27: Tax extracted, product validation, strategies wired, dead breakers removed, CSV export
- [ ] S28A: Bollinger + DCA strategies tested + backtested
- [ ] S28B: AlpacaAdapter read-only, market hours, stock strategies simulated
- [ ] S29A: AlpacaAdapter full, PDT enforced, Alpaca paper soak
- [ ] S29B: Equity live $100, CoinGecko feed, regime detection observe-only
- [ ] S30: Optuna optimizer, wash sale PoC, CryptoQuant signals
- [ ] All tests passing (target: 2800+ total)
- [ ] SPRINT.md + CLAUDE.md updated with new counts and architecture
