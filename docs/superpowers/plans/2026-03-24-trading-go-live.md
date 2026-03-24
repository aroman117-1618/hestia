# Trading Go-Live — Fix & Activate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all code bugs preventing trade execution and activate the full 4-bot Mean Reversion portfolio on live Coinbase from the Mac Mini.

**Architecture:** The trading system uses a distributed IPC architecture: the FastAPI server handles bot CRUD and exposes APIs, while a standalone `bot_service.py` process polls a command queue and runs `BotRunner` tasks. There are 4 code bugs, a missing bot seeding script, and the service was never installed on the Mac Mini. All fixes are surgical — no architectural changes.

**Tech Stack:** Python 3.12, FastAPI, asyncio, Coinbase Advanced Trade SDK, SQLite, launchd

**Key Decision:** Use market orders (not limit+post_only) for live execution. Mean Reversion signals are directional — guaranteed fills matter more than the 0.20% maker/taker fee difference ($0.13 on $62.50 positions).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Fix | `hestia/trading/bot_runner.py:342,344` | `self._bot` → `self.bot` (AttributeError crash) |
| Fix | `hestia/trading/bot_runner.py:79` | Inject `bot.pair` into strategy config at runtime |
| Fix | `hestia/trading/executor.py:138-144` | Switch from limit+post_only to market orders |
| Add | `hestia/trading/product_info.py` | Add SOL-USD, DOGE-USD product entries |
| Create | `scripts/seed-trading-bots.py` | Create 4 MR bots with correct RSI-3 params |
| Fix | `scripts/deploy-to-mini.sh` | Add trading-bots service restart |
| Create | `tests/test_trading_runner.py` | NEW FILE — Test pair injection + portfolio value fallback |
| Modify | `tests/test_trading_pipeline.py` | Add market order assertion to executor tests |

---

## Emergency Rollback Procedure

If anything goes wrong after bots start trading:

1. **Kill switch** (stops all execution immediately):
   ```bash
   curl -sk -X POST https://localhost:8443/v1/trading/kill-switch \
     -H "Authorization: Bearer $(cat ~/.hestia-cli/auth_token)" \
     -H "Content-Type: application/json" \
     -d '{"action": "activate", "reason": "manual emergency halt"}'
   ```
2. **Stop all bots** (graceful shutdown):
   ```bash
   for id in $(sqlite3 ~/hestia/data/trading.db "SELECT id FROM bots WHERE status='running';"); do
     curl -sk -X POST "https://localhost:8443/v1/trading/bots/$id/stop" \
       -H "Authorization: Bearer $(cat ~/.hestia-cli/auth_token)" \
       -H "Content-Type: application/json" -d '{}'
   done
   ```
3. **Stop bot service** (nuclear option):
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.hestia.trading-bots.plist
   ```
4. **Check open positions**: Review in Coinbase app. Close manually if needed.

---

### Task 1: Fix `self._bot` AttributeError in BotRunner

**Files:**
- Fix: `hestia/trading/bot_runner.py:342,344`
- Create: `tests/test_trading_runner.py` (NEW FILE)

This is a new test file. Follow the patterns from `tests/test_trading_pipeline.py` for imports and fixtures.

- [ ] **Step 1: Create test file and write failing test**

```python
"""Tests for BotRunner — portfolio value fallback and pair injection."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from hestia.trading.bot_runner import BotRunner
from hestia.trading.exchange.base import AbstractExchangeAdapter
from hestia.trading.models import Bot, StrategyType
from hestia.trading.risk import RiskManager


@pytest.mark.asyncio
async def test_get_portfolio_value_fallback_on_empty_balances():
    """When exchange returns empty balances, fall back to bot.capital_allocated."""
    bot = Bot(name="test", strategy=StrategyType.MEAN_REVERSION, pair="BTC-USD",
              capital_allocated=62.50, config={})
    exchange = AsyncMock(spec=AbstractExchangeAdapter)
    exchange.get_balances = AsyncMock(return_value={})  # Empty balances

    runner = BotRunner(bot=bot, exchange=exchange, risk_manager=MagicMock())
    result = await runner._get_portfolio_value()
    assert result == 62.50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trading_runner.py::test_get_portfolio_value_fallback_on_empty_balances -v`
Expected: FAIL with `AttributeError: 'BotRunner' object has no attribute '_bot'`

- [ ] **Step 3: Fix the bug — change `self._bot` to `self.bot`**

In `hestia/trading/bot_runner.py`, change lines 342 and 344:
```python
# Line 342: change self._bot to self.bot
            return total if total > 0 else self.bot.capital_allocated
        except Exception:
# Line 344: change self._bot to self.bot
            return self.bot.capital_allocated
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trading_runner.py::test_get_portfolio_value_fallback_on_empty_balances -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/trading/bot_runner.py tests/test_trading_runner.py
git commit -m "fix(trading): self._bot → self.bot in BotRunner portfolio fallback"
```

---

### Task 2: Inject `bot.pair` into Strategy Config

**Files:**
- Fix: `hestia/trading/bot_runner.py:101` (strategy creation in __init__)
- Test: `tests/test_trading_runner.py`

The strategy reads `self.pair = self.config.get("pair", "BTC-USD")` from BaseStrategy, but the Bot model stores pair separately from config. If config doesn't include pair, ALL bots default to BTC-USD signals.

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_strategy_receives_bot_pair():
    """Strategy should use bot.pair, not default to BTC-USD."""
    bot = Bot(name="ETH MR", strategy=StrategyType.MEAN_REVERSION, pair="ETH-USD",
              capital_allocated=62.50, config={"rsi_period": 3, "rsi_oversold": 20, "rsi_overbought": 80})
    exchange = AsyncMock(spec=AbstractExchangeAdapter)

    runner = BotRunner(bot=bot, exchange=exchange, risk_manager=MagicMock())
    assert runner._strategy.pair == "ETH-USD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trading_runner.py::test_strategy_receives_bot_pair -v`
Expected: FAIL — `AssertionError: assert 'BTC-USD' == 'ETH-USD'`

- [ ] **Step 3: Fix — inject pair into config before strategy creation**

In `hestia/trading/bot_runner.py`, around line 100-104, modify strategy creation:

```python
        # Strategy — inject pair into config so strategy knows the trading pair
        strategy_config = {**bot.config, "pair": bot.pair}
        self._strategy = _create_strategy(
            StrategyType(bot.strategy) if isinstance(bot.strategy, str) else bot.strategy,
            strategy_config,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trading_runner.py::test_strategy_receives_bot_pair -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/trading/bot_runner.py tests/test_trading_runner.py
git commit -m "fix(trading): inject bot.pair into strategy config — prevents all bots defaulting to BTC-USD"
```

---

### Task 3: Switch Executor to Market Orders for Live

**Files:**
- Fix: `hestia/trading/executor.py:138-144`
- Test: `tests/test_trading_pipeline.py` (add assertion to existing executor tests)

Post-only limit orders at the current market price are immediately rejected by Coinbase (they'd be taker orders, violating post_only). Market orders guarantee fills.

- [ ] **Step 1: Fix — change to market orders**

In `hestia/trading/executor.py`, replace lines 138-145:

```python
        # Step 4: Execute on exchange — market orders for guaranteed fills
        order = OrderRequest(
            pair=signal.pair,
            side=signal.signal_type.value,
            order_type="market",
            quantity=quantity,
            price=signal.price,  # Reference price for audit trail only
        )
```

- [ ] **Step 2: Check existing executor tests for `order_type="limit"` assertions**

Run: `grep -n "order_type.*limit\|limit.*order" tests/test_trading_pipeline.py tests/test_trading_golive.py`

Update any tests that assert limit order type to expect market orders instead.

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass. Fix any that assert `order_type="limit"`.

- [ ] **Step 4: Commit**

```bash
git add hestia/trading/executor.py tests/
git commit -m "fix(trading): switch to market orders for live Coinbase — limit+post_only rejected at market price"
```

---

### Task 4: Add SOL-USD and DOGE-USD Product Info

**Files:**
- Fix: `hestia/trading/product_info.py`
- Test: `tests/test_trading_product_info.py` (if exists, else inline)

- [ ] **Step 1: Add product entries**

In `hestia/trading/product_info.py`, add to `_PRODUCT_DEFAULTS` after the ETH-USD entry:

```python
    "SOL-USD": {
        "base_min_size": 0.01,       # Coinbase actual minimum
        "base_increment": 0.01,
        "quote_increment": 0.01,
        "base_max_size": 100000.0,
    },
    "DOGE-USD": {
        "base_min_size": 1.0,        # Coinbase actual minimum
        "base_increment": 1.0,
        "quote_increment": 0.00001,
        "base_max_size": 10000000.0,
    },
```

- [ ] **Step 2: Verify product lookup**

```python
# Quick sanity check
from hestia.trading.product_info import get_product_info
info = get_product_info("SOL-USD")
assert info.pair == "SOL-USD"
assert info.base_min_size == 0.01
```

- [ ] **Step 3: Commit**

```bash
git add hestia/trading/product_info.py
git commit -m "feat(trading): add SOL-USD and DOGE-USD product info for live Coinbase"
```

---

### Task 5: Create Bot Seeding Script

**Files:**
- Create: `scripts/seed-trading-bots.py`

This script creates the 4-bot Mean Reversion portfolio via the API. Run once on the Mac Mini after deploying code fixes.

- [ ] **Step 1: Create the seed script**

```python
#!/usr/bin/env python3
"""
Seed the 4-bot Mean Reversion portfolio for live trading.

Usage:
    python scripts/seed-trading-bots.py [--dry-run]

Requires: server running on https://localhost:8443
"""

import argparse
import json
import ssl
import urllib.request

BASE_URL = "https://localhost:8443/v1/trading"

# Per-asset RSI-3 configs from backtested results (S27.6)
BOTS = [
    {
        "name": "Mean Reversion — BTC-USD",
        "strategy": "mean_reversion",
        "pair": "BTC-USD",
        "capital_allocated": 62.50,
        "config": {
            "rsi_period": 3,
            "rsi_oversold": 15,
            "rsi_overbought": 85,
        },
    },
    {
        "name": "Mean Reversion — ETH-USD",
        "strategy": "mean_reversion",
        "pair": "ETH-USD",
        "capital_allocated": 62.50,
        "config": {
            "rsi_period": 3,
            "rsi_oversold": 20,
            "rsi_overbought": 80,
        },
    },
    {
        "name": "Mean Reversion — SOL-USD",
        "strategy": "mean_reversion",
        "pair": "SOL-USD",
        "capital_allocated": 62.50,
        "config": {
            "rsi_period": 3,
            "rsi_oversold": 25,
            "rsi_overbought": 70,
        },
    },
    {
        "name": "Mean Reversion — DOGE-USD",
        "strategy": "mean_reversion",
        "pair": "DOGE-USD",
        "capital_allocated": 62.50,
        "config": {
            "rsi_period": 3,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
    },
]


def get_jwt_token() -> str:
    """Read JWT from CLI config."""
    import os
    token_path = os.path.expanduser("~/.hestia-cli/auth_token")
    if os.path.exists(token_path):
        return open(token_path).read().strip()
    raise RuntimeError(f"No auth token at {token_path} — run 'hestia' CLI to authenticate first")


def api_call(method: str, path: str, body: dict = None, token: str = "") -> dict:
    """Make an API call to the Hestia server."""
    url = f"{BASE_URL}{path}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser(description="Seed trading bots")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be created without creating")
    args = parser.parse_args()

    token = get_jwt_token()

    # Check existing bots
    existing = api_call("GET", "/bots", token=token)
    existing_pairs = {b["pair"] for b in existing.get("bots", [])}

    for bot_def in BOTS:
        if bot_def["pair"] in existing_pairs:
            print(f"  SKIP {bot_def['pair']} — bot already exists")
            continue

        if args.dry_run:
            print(f"  DRY-RUN: would create {bot_def['name']} ({bot_def['pair']})")
            continue

        # Create bot
        created = api_call("POST", "/bots", body=bot_def, token=token)
        bot_id = created["id"]
        print(f"  CREATED {bot_def['name']} → {bot_id[:8]}")

        # Start bot
        api_call("POST", f"/bots/{bot_id}/start", body={}, token=token)
        print(f"  STARTED {bot_def['pair']}")

    print("\nDone. Verify: GET /v1/trading/bots")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/seed-trading-bots.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/seed-trading-bots.py
git commit -m "feat(trading): bot seeding script — creates 4 MR bots with RSI-3 params"
```

---

### Task 6: Update Deploy Script to Manage Trading Service

**Files:**
- Fix: `scripts/deploy-to-mini.sh`

- [ ] **Step 1: Add trading-bots service restart to the remote script**

In `scripts/deploy-to-mini.sh`, inside the `REMOTE_SCRIPT` heredoc, after the server plist reload block (after line 135), add:

```bash
# Reload trading-bots service (if configured)
if [[ -f ~/Library/LaunchAgents/com.hestia.trading-bots.plist ]]; then
    echo "Reloading trading-bots service..."
    launchctl unload ~/Library/LaunchAgents/com.hestia.trading-bots.plist 2>/dev/null || true
    sleep 1
    launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist 2>/dev/null || true
    echo "✓ Trading-bots service reloaded via launchd"
fi
```

- [ ] **Step 2: Commit**

```bash
git add scripts/deploy-to-mini.sh
git commit -m "fix(deploy): restart trading-bots service on deploy — prevents stale code"
```

---

### Task 7: Run Full Test Suite

- [ ] **Step 1: Run full pytest**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass. Fix any regressions from Tasks 1-4.

- [ ] **Step 2: Run @hestia-tester for thorough check**

Use @hestia-tester to validate all trading-related tests pass.

---

### Task 8: Deploy to Mac Mini & Activate

**This task is manual (requires SSH to Mac Mini).** All steps in order.

- [ ] **Step 1: Deploy code**

```bash
./scripts/deploy-to-mini.sh
```

Wait for "Deployment Complete!" and health check pass.

- [ ] **Step 2: SSH to Mac Mini and verify Coinbase credentials**

```bash
ssh andrewroman117@hestia-3.local 'wc -c < ~/.hestia/coinbase-credentials'
# Should show > 50 chars. If file missing or empty, credentials must be set up first.
# To verify they actually work, check the bot service log after Step 4 for
# "Coinbase adapter connected" (success) vs "credentials not found" (failure).
```

- [ ] **Step 3: Verify kill switch is inactive**

```bash
curl -sk https://hestia-3.local:8443/v1/trading/risk/status \
  -H "Authorization: Bearer $(ssh andrewroman117@hestia-3.local 'cat ~/.hestia-cli/auth_token')" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Kill switch:', 'ACTIVE — DEACTIVATE BEFORE PROCEEDING' if d.get('kill_switch',{}).get('active') else 'inactive (OK)')"
```

If active, deactivate before continuing.

- [ ] **Step 4: Install trading-bots launchd service**

```bash
ssh andrewroman117@hestia-3.local 'cp ~/hestia/scripts/launchd/com.hestia.trading-bots.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist'
```

- [ ] **Step 5: Verify bot service started and Coinbase connected**

```bash
ssh andrewroman117@hestia-3.local 'tail -20 ~/hestia/logs/trading-bots.log'
```

Expected: "Bot service starting" + "Coinbase adapter connected" + "Bot service ready — resumed 0 bot(s)"

If you see "credentials not found" → credentials file is missing. Stop and fix.

Check for errors:
```bash
ssh andrewroman117@hestia-3.local 'tail -5 ~/hestia/logs/trading-bots.error.log'
```

- [ ] **Step 6: Delete old stopped bot (MANDATORY)**

The old stopped BTC-USD bot from March 21 MUST be removed. Otherwise the seed script will skip BTC-USD and 25% of capital sits idle.

```bash
ssh andrewroman117@hestia-3.local 'sqlite3 ~/hestia/data/trading.db "DELETE FROM bots WHERE status IN (\"stopped\",\"error\",\"created\"); DELETE FROM bot_commands;"'
ssh andrewroman117@hestia-3.local 'sqlite3 ~/hestia/data/trading.db "SELECT COUNT(*) FROM bots;"'
# Expected: 0
```

- [ ] **Step 7: Dry-run the seed script**

```bash
ssh andrewroman117@hestia-3.local 'cd ~/hestia && source .venv/bin/activate && python scripts/seed-trading-bots.py --dry-run'
```

Expected: 4 "DRY-RUN: would create..." lines. If any show "SKIP", Step 6 didn't clean up.

- [ ] **Step 8: Run bot seeding script for real**

```bash
ssh andrewroman117@hestia-3.local 'cd ~/hestia && source .venv/bin/activate && python scripts/seed-trading-bots.py'
```

Expected: All 4 bots show CREATED + STARTED. If any show SKIP, stop and investigate.

- [ ] **Step 9: Verify bots are running in the bot service**

```bash
ssh andrewroman117@hestia-3.local 'tail -30 ~/hestia/logs/trading-bots.log'
```

Expected: "Processing command: start for bot xxxxxxxx" messages + "BotRunner started: Mean Reversion (RSI-3) on BTC-USD" etc.

- [ ] **Step 10: Wait 15 minutes for first tick, then verify**

After one poll interval (900s = 15 min), check logs for signal generation:

```bash
ssh andrewroman117@hestia-3.local 'grep "Signal:" ~/hestia/logs/trading-bots.log | tail -10'
```

Expected: Signal lines for each pair (BUY/SELL/HOLD with RSI values)

- [ ] **Step 11: Verify via API**

```bash
# From Mac Mini or via Tailscale:
curl -sk https://localhost:8443/v1/trading/bots -H "Authorization: Bearer $(cat ~/.hestia-cli/auth_token)" | python3 -m json.tool
```

Expected: 4 bots, all status "running"

- [ ] **Step 12: Verify in Hestia macOS app**

Open the app → Trading tab. Should show:
- "Active — Hestia is managing your trades" (toggle ON)
- Portfolio Snapshot with correct total
- 4 bots listed (if bot list view exists)
- Decision feed showing signal analysis every 15 min

---

### Task 9: Post-Activation Monitoring (First 24h)

- [ ] **Step 1: Check for first trades after signal fires**

Most signals will be HOLD (RSI in neutral zone). A trade requires RSI to hit extreme levels:
- BTC: RSI < 15 or > 85
- ETH: RSI < 20 or > 80
- SOL: RSI < 25 or > 70
- DOGE: RSI < 25 or > 75

Check trade history:
```bash
ssh andrewroman117@hestia-3.local 'sqlite3 ~/hestia/data/trading.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 5;"'
```

- [ ] **Step 2: Verify no error-state bots**

```bash
ssh andrewroman117@hestia-3.local 'sqlite3 ~/hestia/data/trading.db "SELECT name, status FROM bots;"'
```

All 4 should be "running". If any show "error", check logs for the crash.

- [ ] **Step 3: Confirm Coinbase account reflects activity**

When a trade eventually fires, the Coinbase app should show a non-zero crypto balance matching the traded pair.
