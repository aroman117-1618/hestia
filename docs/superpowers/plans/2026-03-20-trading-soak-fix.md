# Trading Soak Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the non-functional paper soak by wiring Coinbase public market data into PaperAdapter, then add minimal monitoring (ntfy.sh on watchdog + recovery playbook).

**Architecture:** Add an optional `market_data_source` callable to PaperAdapter via dependency injection. TradingManager wires DataLoader.fetch_from_coinbase (public API, no auth) when mode=paper. Internal health checks added to bot_service as asyncio task. Watchdog gets ntfy.sh alerting via env var.

**Tech Stack:** Python 3.12, asyncio, coinbase-advanced-py (public API), ntfy.sh (push alerts), launchd (Mac Mini services)

**Spec:** `docs/superpowers/specs/2026-03-20-trading-soak-fix-design.md`
**Second Opinion:** `docs/plans/trading-soak-fix-second-opinion-2026-03-20.md`

---

## Phase A: Core Fix (get the soak producing trades)

### Task 1: PaperAdapter — add market_data_source parameter

**Files:**
- Modify: `hestia/trading/exchange/paper.py:38-63` (\_\_init\_\_), `:206-224` (get_ticker, get_candles)
- Test: `tests/test_trading_adapter.py`

- [ ] **Step 1: Write failing tests for market_data_source**

Add to `tests/test_trading_adapter.py` after the existing `TestABCInterface` class:

```python
class TestMarketDataSource:
    """Tests for PaperAdapter with injected market data source."""

    @pytest.mark.asyncio
    async def test_get_candles_with_source(self):
        """When market_data_source is set, get_candles delegates to it."""
        import pandas as pd
        from datetime import datetime, timezone

        fake_df = pd.DataFrame([{
            "timestamp": datetime.now(timezone.utc),
            "open": 84000.0, "high": 84500.0,
            "low": 83500.0, "close": 84200.0,
            "volume": 100.0,
        }])

        async def mock_source(pair, granularity="1h", days=7):
            return fake_df

        adapter = PaperAdapter(market_data_source=mock_source)
        await adapter.connect()
        result = await adapter.get_candles("BTC-USD")
        assert result is not None
        assert len(result) == 1
        assert float(result.iloc[0]["close"]) == 84200.0
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_get_candles_without_source(self):
        """When no market_data_source, get_candles returns None (backward compat)."""
        adapter = PaperAdapter()
        await adapter.connect()
        result = await adapter.get_candles("BTC-USD")
        assert result is None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_get_candles_source_failure_returns_none(self):
        """When market_data_source raises, get_candles returns None gracefully."""
        async def failing_source(pair, granularity="1h", days=7):
            raise ConnectionError("API down")

        adapter = PaperAdapter(market_data_source=failing_source)
        await adapter.connect()
        result = await adapter.get_candles("BTC-USD")
        assert result is None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_get_ticker_updates_price_from_source(self):
        """get_ticker uses last candle close to update _current_prices."""
        import pandas as pd
        from datetime import datetime, timezone

        fake_df = pd.DataFrame([{
            "timestamp": datetime.now(timezone.utc),
            "open": 84000.0, "high": 84500.0,
            "low": 83500.0, "close": 84200.0,
            "volume": 100.0,
        }])

        async def mock_source(pair, granularity="1h", days=7):
            return fake_df

        adapter = PaperAdapter(market_data_source=mock_source)
        await adapter.connect()
        ticker = await adapter.get_ticker("BTC-USD")
        assert ticker["price"] == 84200.0
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_get_ticker_fallback_without_source(self):
        """Without market_data_source, get_ticker uses hardcoded defaults."""
        adapter = PaperAdapter()
        await adapter.connect()
        ticker = await adapter.get_ticker("BTC-USD")
        assert ticker["price"] == 65000.0  # hardcoded default
        await adapter.disconnect()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trading_adapter.py::TestMarketDataSource -v`
Expected: FAIL — `PaperAdapter() got an unexpected keyword argument 'market_data_source'`

- [ ] **Step 3: Implement PaperAdapter changes**

In `hestia/trading/exchange/paper.py`:

Update imports (add `Callable` to typing):
```python
from typing import Any, Callable, Dict, List, Optional
```

Update `__init__` to accept `market_data_source`:
```python
def __init__(
    self,
    initial_balance_usd: float = 250.0,
    maker_fee: float = DEFAULT_MAKER_FEE,
    taker_fee: float = DEFAULT_TAKER_FEE,
    slippage: float = DEFAULT_SLIPPAGE,
    market_data_source: Optional[Callable] = None,
) -> None:
    self._connected = False
    self._maker_fee = maker_fee
    self._taker_fee = taker_fee
    self._slippage = slippage
    self._market_data_source = market_data_source

    # Virtual balances
    self._balances: Dict[str, AccountBalance] = {
        "USD": AccountBalance(currency="USD", available=initial_balance_usd),
    }

    # Order tracking
    self._orders: Dict[str, OrderResult] = {}
    self._open_orders: Dict[str, OrderRequest] = {}

    # Simulated price (set externally or default)
    self._current_prices: Dict[str, float] = {
        "BTC-USD": 65000.0,
        "ETH-USD": 3500.0,
    }
```

Replace `get_candles`:
```python
async def get_candles(
    self,
    pair: str,
    granularity: str = "1h",
    days: int = 7,
) -> Optional[pd.DataFrame]:
    """Delegate to market data source if available."""
    if self._market_data_source:
        try:
            return await self._market_data_source(
                pair=pair, granularity=granularity, days=days
            )
        except Exception as e:
            logger.warning(
                f"Market data source failed: {type(e).__name__}",
                component=LogComponent.TRADING,
                data={"pair": pair},
            )
    return None
```

Replace `get_ticker`:
```python
async def get_ticker(self, pair: str = "BTC-USD") -> Dict[str, Any]:
    """Use market data source for live spot price if available."""
    if self._market_data_source:
        try:
            df = await self._market_data_source(pair=pair, granularity="1h", days=1)
            if df is not None and not df.empty:
                price = float(df.iloc[-1]["close"])
                self._current_prices[pair] = price
        except Exception:
            pass  # Fall through to cached price

    price = self._current_prices.get(pair, 0.0)
    return {
        "pair": pair,
        "price": price,
        "bid": price * 0.9999,
        "ask": price * 1.0001,
        "volume_24h": 1000000.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

Note: `get_ticker` caches the last known price in `_current_prices` so the fill simulation always has a fresh price, and subsequent calls within the same poll cycle don't re-fetch.

- [ ] **Step 4: Update existing test that asserts None**

In `tests/test_trading_adapter.py`, update `test_paper_adapter_get_candles_returns_none` (line 281):

```python
@pytest.mark.asyncio
async def test_paper_adapter_get_candles_returns_none_without_source(self, paper):
    """Paper adapter without market_data_source returns None."""
    result = await paper.get_candles("BTC-USD")
    assert result is None
```

(Just rename to clarify — the behavior hasn't changed for the default case.)

- [ ] **Step 5: Run all adapter tests**

Run: `python -m pytest tests/test_trading_adapter.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/trading/exchange/paper.py tests/test_trading_adapter.py
git commit -m "feat(trading): add market_data_source to PaperAdapter

DI callable enables paper trading with real market data from
Coinbase public API. get_candles delegates to source, get_ticker
caches last close price for fill simulation. Backward compatible
— None source preserves existing behavior."
```

---

### Task 2: TradingManager — wire DataLoader as market data source

**Files:**
- Modify: `hestia/trading/manager.py:80-96` (initialize method)

- [ ] **Step 1: Write failing test**

Add to `tests/test_trading_pipeline.py` (or create `tests/test_trading_manager_init.py` if cleaner):

```python
class TestTradingManagerPaperWithMarketData:
    """Verify TradingManager wires market data source in paper mode."""

    @pytest.mark.asyncio
    async def test_paper_mode_has_market_data_source(self):
        """Paper adapter gets market_data_source when primary is coinbase."""
        from hestia.trading.manager import TradingManager

        config = {
            "exchange": {
                "primary": "coinbase",
                "mode": "paper",
                "paper": {"initial_balance_usd": 100.0},
            }
        }
        mgr = TradingManager(config=config)
        await mgr.initialize()
        assert mgr.exchange is not None
        assert mgr.exchange.is_paper is True
        assert mgr.exchange._market_data_source is not None
        await mgr.close()

    @pytest.mark.asyncio
    async def test_paper_mode_no_source_without_coinbase_primary(self):
        """Paper adapter has no market_data_source when primary != coinbase."""
        from hestia.trading.manager import TradingManager

        config = {
            "exchange": {
                "primary": "alpaca",
                "mode": "paper",
                "paper": {"initial_balance_usd": 100.0},
            }
        }
        mgr = TradingManager(config=config)
        await mgr.initialize()
        assert mgr.exchange is not None
        assert mgr.exchange.is_paper is True
        assert mgr.exchange._market_data_source is None
        await mgr.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trading_manager_init.py -v`
Expected: FAIL — `_market_data_source` doesn't exist (yet) or is None

- [ ] **Step 3: Implement TradingManager wiring**

In `hestia/trading/manager.py`, replace the paper mode block in `initialize()` (lines 83-90):

```python
if mode == "paper":
    paper_cfg = self._config.get("exchange", {}).get("paper", {})

    # Wire Coinbase public API as market data source for paper trading
    market_data_source = None
    primary = self._config.get("exchange", {}).get("primary", "")
    if primary == "coinbase":
        from hestia.trading.backtest.data_loader import DataLoader
        _loader = DataLoader()

        async def _fetch_candles(
            pair: str, granularity: str = "1h", days: int = 7,
        ) -> Optional[pd.DataFrame]:
            from datetime import timedelta
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            return await _loader.fetch_from_coinbase(
                pair=pair, granularity=granularity, start=start, end=end,
            )

        market_data_source = _fetch_candles

    self._exchange = PaperAdapter(
        initial_balance_usd=paper_cfg.get("initial_balance_usd", 250.0),
        maker_fee=paper_cfg.get("maker_fee", 0.004),
        taker_fee=paper_cfg.get("taker_fee", 0.006),
        slippage=paper_cfg.get("slippage", 0.001),
        market_data_source=market_data_source,
    )
```

Ensure `pd` and `Optional` are imported at the top of manager.py. Also ensure `datetime` and `timezone` are imported (they should be already).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_trading_manager_init.py tests/test_trading_adapter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full trading test suite**

Run: `python -m pytest tests/ -k trading -v --timeout=30`
Expected: ALL PASS — no regressions in existing trading tests

- [ ] **Step 6: Commit**

```bash
git add hestia/trading/manager.py tests/test_trading_manager_init.py
git commit -m "feat(trading): wire Coinbase market data into paper mode

TradingManager.initialize() creates a DataLoader and passes
fetch_from_coinbase as market_data_source to PaperAdapter when
mode=paper and primary=coinbase. Public API, no auth needed."
```

---

### Task 3: Validate on Mac Mini + deploy + restart soak

**Files:** None modified — deployment and validation only.

- [ ] **Step 1: Validate DataLoader works on Mac Mini**

```bash
ssh andrewroman117@hestia-3.local "cd ~/hestia && source .venv/bin/activate && python3 -c \"
from hestia.trading.backtest.data_loader import DataLoader
import asyncio
dl = DataLoader()
df = asyncio.run(dl.fetch_from_coinbase('BTC-USD', '1h'))
print(f'{len(df)} candles fetched')
print(df.tail(3).to_string())
\""
```

Expected: ~168 candles with recent timestamps. If 0 candles, debug SDK on Mac Mini before proceeding.

- [ ] **Step 2: Deploy code to Mac Mini**

```bash
rsync -avz --exclude='.venv' --exclude='data/' --exclude='logs/' --exclude='*.pyc' \
  --exclude='__pycache__' --exclude='.git' --exclude='certs/' \
  /Users/andrewlonati/hestia/ andrewroman117@hestia-3.local:~/hestia/
```

- [ ] **Step 3: Restart bot service**

```bash
ssh andrewroman117@hestia-3.local "launchctl kickstart -k gui/\$(id -u)/com.hestia.trading-bots"
```

- [ ] **Step 4: Watch for first successful candle fetch (within 15 min)**

```bash
ssh andrewroman117@hestia-3.local "tail -f ~/hestia/logs/hestia.log" | grep --line-buffered -i "candle\|signal\|trading"
```

Expected within 15 minutes:
- `Fetched 168 candles from Coinbase: BTC-USD (1h)` (instead of "Candle fetch returned empty")
- `Signal: BUY/SELL/HOLD` from Mean Reversion strategy

If still showing "Candle fetch returned empty" after first poll cycle, check that the deployed code matches (verify `_market_data_source` is set in the running process).

- [ ] **Step 5: Verify after 30 minutes**

```bash
ssh andrewroman117@hestia-3.local "cd ~/hestia && source .venv/bin/activate && python3 -c \"
import sqlite3
conn = sqlite3.connect('data/trading.db')
signals = conn.execute('SELECT count(*) FROM trades').fetchone()[0]
print(f'Trades: {signals}')
\""
```

Check the watchdog is also clean:
```bash
ssh andrewroman117@hestia-3.local "tail -5 ~/hestia/logs/watchdog.log"
```

Expected: No FAILURE/RESTART entries since deploy.

---

## Phase B: Minimal Monitoring

### Task 4: Enable ntfy.sh on watchdog

**Files:**
- Modify: `scripts/launchd/com.hestia.watchdog.plist` (or wherever the plist lives — may need to edit on Mac Mini directly)

- [ ] **Step 1: Create ntfy.sh topic**

Visit https://ntfy.sh/ — no account needed. The topic `hestia-trading` is public (anyone with the URL can subscribe). For a private topic, use `ntfy.sh` self-hosted later.

Subscribe on phone: open ntfy app → subscribe to `hestia-trading`.

- [ ] **Step 2: Test ntfy.sh push from Mac Mini**

```bash
ssh andrewroman117@hestia-3.local "curl -fsS -H 'Title: Hestia Test' -d 'Test alert from Mac Mini' https://ntfy.sh/hestia-trading"
```

Expected: Push notification on phone.

- [ ] **Step 3: Add env var to watchdog launchd plist**

On Mac Mini, edit the plist to add `HESTIA_NTFY_TOPIC`:

```bash
ssh andrewroman117@hestia-3.local "cat ~/Library/LaunchAgents/com.hestia.watchdog.plist"
```

Add inside the `<dict>` under `EnvironmentVariables`:
```xml
<key>HESTIA_NTFY_TOPIC</key>
<string>hestia-trading</string>
```

Then reload:
```bash
ssh andrewroman117@hestia-3.local "launchctl unload ~/Library/LaunchAgents/com.hestia.watchdog.plist && launchctl load ~/Library/LaunchAgents/com.hestia.watchdog.plist"
```

- [ ] **Step 4: Verify by simulating a restart**

Temporarily kill the server to trigger a watchdog restart + ntfy alert:
```bash
ssh andrewroman117@hestia-3.local "lsof -ti :8443 | xargs kill -9"
```

Expected within 2 minutes: ntfy push notification "Hestia Server Restarted" on phone.

After confirming, verify the server recovers and the bot resumes.

- [ ] **Step 5: Commit plist change locally**

```bash
# Copy updated plist back to repo
scp andrewroman117@hestia-3.local:~/Library/LaunchAgents/com.hestia.watchdog.plist scripts/launchd/
git add scripts/launchd/com.hestia.watchdog.plist
git commit -m "feat(ops): enable ntfy.sh push alerts on watchdog

Adds HESTIA_NTFY_TOPIC env var to watchdog launchd plist.
Sends high-priority push notification to phone on server restart.
Topic: hestia-trading (ntfy.sh public, switch to self-hosted for live)."
```

---

### Task 5: Write recovery playbook

**Files:**
- Create: `docs/reference/trading-recovery-playbook.md`

- [ ] **Step 1: Write the playbook**

```markdown
# Trading Recovery Playbook

Quick-response guide when you receive a trading alert or suspect something is wrong.

## Check Status

```bash
# Is the server alive?
ssh andrewroman117@hestia-3.local "curl -sk https://localhost:8443/v1/ping"

# Is the bot service running?
ssh andrewroman117@hestia-3.local "launchctl list | grep trading-bots"

# Recent trading logs (last 20 entries)
ssh andrewroman117@hestia-3.local "grep trading ~/hestia/logs/hestia.log | tail -20"

# Any kill switch or circuit breaker triggers?
ssh andrewroman117@hestia-3.local "grep -i 'kill.switch\|circuit.breaker\|CRITICAL' ~/hestia/logs/hestia.log | tail -10"

# Trade count and last trade time
ssh andrewroman117@hestia-3.local "cd ~/hestia && source .venv/bin/activate && python3 -c \"
import sqlite3; conn = sqlite3.connect('data/trading.db')
print('Trades:', conn.execute('SELECT count(*) FROM trades').fetchone()[0])
for r in conn.execute('SELECT * FROM trades ORDER BY rowid DESC LIMIT 3'):
    print(r)
\""

# Watchdog status (any recent restarts?)
ssh andrewroman117@hestia-3.local "tail -10 ~/hestia/logs/watchdog.log"
```

## Pause Trading (Safe)

```bash
# Stop the bot service (bots pause, no data loss)
ssh andrewroman117@hestia-3.local "launchctl stop com.hestia.trading-bots"
```

## Resume Trading

```bash
# Restart the bot service (resumes RUNNING bots from DB)
ssh andrewroman117@hestia-3.local "launchctl start com.hestia.trading-bots"
```

## Emergency Kill Switch

```bash
# Force stop everything
ssh andrewroman117@hestia-3.local "launchctl stop com.hestia.trading-bots; lsof -ti :8443 | xargs kill -9 2>/dev/null; echo 'All stopped'"

# Verify nothing is running
ssh andrewroman117@hestia-3.local "launchctl list | grep hestia"
```

## Restart Full Stack

```bash
# Restart server (launchd KeepAlive will auto-start)
ssh andrewroman117@hestia-3.local "launchctl kickstart -k gui/\$(id -u)/com.hestia.server"

# Wait 15s for server boot, then restart bots
sleep 15
ssh andrewroman117@hestia-3.local "launchctl kickstart -k gui/\$(id -u)/com.hestia.trading-bots"
```

## Common Scenarios

| Alert | Likely Cause | Action |
|-------|-------------|--------|
| "Hestia Server Restarted" | Watchdog detected /v1/ready failure | Check server logs. Usually auto-recovers. |
| Bot producing no signals | Market data source failing (Coinbase API) | Check `grep 'Market data source failed' ~/hestia/logs/hestia.log` |
| Kill switch triggered | Drawdown > 15% or daily loss > 5% | Review trade history. Manual restart required (`auto_reset: false`). |
| Bot service crashed | Python exception in bot_runner | Check `~/hestia/logs/trading-bots.error.log`. Service auto-restarts via KeepAlive. |
```

- [ ] **Step 2: Commit**

```bash
git add docs/reference/trading-recovery-playbook.md
git commit -m "docs: trading recovery playbook — alert response guide"
```

---

## Phase C: Internal Health Monitor (next session)

### Task 6: Add health check asyncio task to bot_service

**Files:**
- Modify: `hestia/trading/bot_service.py`
- Test: `tests/test_trading_golive.py` (add health check tests)

This task adds a background asyncio task inside the bot service that periodically checks:
- Last candle fetch timestamp (data freshness)
- Signal generation count since last check
- Kill switch / circuit breaker state
- Logs results to `logs/trading-health.log`

**Deferred to next session** — the core fix (Tasks 1-3) and minimal monitoring (Tasks 4-5) are sufficient to run the soak safely.

---

## Verification Checklist

After all Phase A + B tasks:

- [ ] PaperAdapter tests pass (with and without market_data_source)
- [ ] TradingManager wiring tests pass
- [ ] Full trading test suite passes (no regressions)
- [ ] DataLoader validated on Mac Mini (returns 168 candles)
- [ ] Code deployed to Mac Mini
- [ ] Bot service restarted, first candle fetch successful
- [ ] Signal generated within 15 minutes of deploy
- [ ] Watchdog stable (no false restarts)
- [ ] ntfy.sh push received on phone during test alert
- [ ] Recovery playbook written and committed

**Soak clock starts when first signal is confirmed. Target: 72h ending ~Mar 23.**
