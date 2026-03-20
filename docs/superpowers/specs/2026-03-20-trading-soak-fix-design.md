# Trading Soak Fix + Monitoring — Design Spec

**Date:** 2026-03-20
**Status:** Draft
**Urgency:** HIGH — paper soak has produced zero trades due to two bugs

## Problem Statement

The Sprint 27 paper soak (started 2026-03-19) has been non-functional:

1. **PaperAdapter has no market data source** — `get_candles()` returns `None`, so Mean Reversion strategy can never compute RSI, generate signals, or execute trades. Zero trades in 24+ hours.
2. **Watchdog grep mismatch** (FIXED) — `"ready": true"` vs `"ready":true` caused 400+ false-positive restarts, killing the server every ~2 minutes.
3. **No soak monitoring** — both failures went undetected for hours. No alerting exists.

## Design

### 1. PaperAdapter Market Data Delegation

**File:** `hestia/trading/exchange/paper.py`

Add an optional `market_data_source` callable to PaperAdapter. When provided, `get_candles()` delegates to it instead of returning `None`.

```python
class PaperAdapter(AbstractExchangeAdapter):
    def __init__(
        self,
        initial_balance_usd: float = 250.0,
        maker_fee: float = DEFAULT_MAKER_FEE,
        taker_fee: float = DEFAULT_TAKER_FEE,
        slippage: float = DEFAULT_SLIPPAGE,
        market_data_source: Optional[Callable] = None,
    ) -> None:
        # ... existing init ...
        self._market_data_source = market_data_source

    async def get_candles(
        self, pair: str, granularity: str = "1h", days: int = 7,
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

    async def get_ticker(self, pair: str = "BTC-USD") -> Dict[str, Any]:
        """Use market data source for live spot price if available."""
        if self._market_data_source:
            try:
                df = await self._market_data_source(pair=pair, granularity="1h", days=1)
                if df is not None and not df.empty:
                    price = float(df.iloc[-1]["close"])
                    self._current_prices[pair] = price
                    return {"pair": pair, "price": price}
            except Exception:
                pass
        # Fallback to cached price
        return {"pair": pair, "price": self._current_prices.get(pair, 0.0)}
```

**Data source:** `DataLoader.fetch_from_coinbase()` — Coinbase public REST API, no auth needed. Already used by `CoinbaseAdapter.get_candles()`.

### 2. TradingManager Wiring

**File:** `hestia/trading/manager.py`

When `mode: "paper"`, create a DataLoader and pass its fetch method as the market data source:

```python
if mode == "paper":
    paper_cfg = self._config.get("exchange", {}).get("paper", {})

    # Wire Coinbase public API as market data source for paper trading
    market_data_source = None
    if self._config.get("exchange", {}).get("primary") == "coinbase":
        from hestia.trading.backtest.data_loader import DataLoader
        loader = DataLoader()

        async def _fetch_candles(pair: str, granularity: str = "1h", days: int = 7):
            from datetime import datetime, timedelta, timezone
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            return await loader.fetch_from_coinbase(
                pair=pair, granularity=granularity, start=start, end=end
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

### 3. Watchdog Hardening

**File:** `scripts/hestia-watchdog.sh`

Already fixed: grep pattern uses `\s*` for JSON spacing tolerance.

Add post-restart cooldown — after a kickstart, write a timestamp to a cooldown file. On next check, if cooldown file exists and < 90s old, skip the check (give server time to boot).

```bash
COOLDOWN_FILE="${PROJECT_ROOT}/logs/.watchdog-cooldown"
COOLDOWN_SECONDS=90

# Skip check if in cooldown after restart
if [[ -f "$COOLDOWN_FILE" ]]; then
    cooldown_ts=$(cat "$COOLDOWN_FILE" 2>/dev/null)
    now_ts=$(date +%s)
    if (( now_ts - cooldown_ts < COOLDOWN_SECONDS )); then
        exit 0  # Still in cooldown, skip this check
    fi
    rm -f "$COOLDOWN_FILE"
fi

# ... existing ready check ...

# After kickstart:
date +%s > "$COOLDOWN_FILE"
```

### 4. Trading Health Monitor

**New file:** `scripts/trading-health-monitor.sh`
**New launchd plist:** `com.hestia.trading-monitor`
**Runs:** Every 15 minutes via launchd StartInterval

Checks:
1. **Bot service alive** — `launchctl list com.hestia.trading-bots` has a PID
2. **Recent activity** — last trading log entry < 20 min old
3. **Signal generation** — grep for signal/candle entries in last interval
4. **Kill switch** — grep for kill_switch or circuit_breaker triggers
5. **Trade count** — query trading.db for trade count (track delta between checks)

Alert actions:
- **ntfy.sh push** — high priority for kill switch, default for inactivity
- **Log to** `logs/trading-monitor.log` — all check results

### 5. ntfy.sh Configuration

**File:** `hestia/config/trading.yaml` — add to `monitoring` section:

```yaml
monitoring:
  daily_summary_time: "00:00"
  log_every_trade: true
  log_every_signal: true
  alerts:
    ntfy_topic: "hestia-trading"     # ntfy.sh topic for push notifications
    inactivity_threshold_minutes: 30  # Alert if no signals in this window
    # Thresholds below apply in live mode only
    daily_pnl_alert_pct: -3.0        # Alert if daily P&L worse than -3%
    portfolio_drift_pct: 5.0          # Alert if portfolio value drifts >5% from expected
```

**Watchdog also gets the topic** via env var in launchd plist:
```xml
<key>HESTIA_NTFY_TOPIC</key>
<string>hestia-trading</string>
```

### 6. Bot Cleanup + Restart

Manual steps after deploying:
1. SSH to Mac Mini
2. Stop the 2 stale bots in DB (`UPDATE bots SET status='stopped' WHERE id != '0d845e6c...'`)
3. Restart bot service: `launchctl kickstart -k gui/$(id -u)/com.hestia.trading-bots`
4. Watch logs for first successful candle fetch + signal generation
5. Verify with `/check-soak` or manual log check after 30 min

### 7. `/check-soak` Skill

**File:** `.claude/skills/check-soak/SKILL.md`

Quick health check skill for use during the soak (and later for live monitoring):

1. SSH to Mac Mini
2. Check server uptime via `/v1/ready`
3. Check watchdog log for recent restarts
4. Check trading logs for recent signals/trades
5. Query trading.db for trade count and P&L
6. Report status

Can be run manually (`/check-soak`) or on a loop (`/loop 4h /check-soak`).

## What This Does NOT Change

- CoinbaseAdapter — untouched
- Strategy logic (Mean Reversion, Grid, etc.) — untouched
- Risk manager / circuit breakers — untouched
- Execution pipeline (signal → risk → price → exchange) — untouched
- Bot runner poll interval (15 min) — untouched
- Config file format — additive only (new `alerts` subsection)
- No new Python dependencies

## Estimated Effort

| Component | Hours |
|-----------|-------|
| PaperAdapter market data delegation | 1 |
| TradingManager wiring | 0.5 |
| Watchdog cooldown | 0.5 |
| Trading health monitor script | 2 |
| ntfy.sh config + launchd plists | 1 |
| Bot cleanup + deploy + verify | 1 |
| `/check-soak` skill | 1 |
| Tests | 2 |
| **Total** | **~9h** |

## Success Criteria

1. Paper soak produces at least 1 signal within the first 30 minutes after deploy
2. Watchdog stays green (no false restarts) for 24+ hours
3. ntfy.sh push received on phone within 2 minutes of a simulated failure
4. Trading health monitor correctly detects and alerts on bot inactivity
5. 72-hour soak window completes with trade history available for review

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Coinbase public API rate limiting | DataLoader already has retry logic; 15-min poll interval is well under limits |
| DataLoader returns different format than PaperAdapter expects | Same code path CoinbaseAdapter uses; format is proven |
| ntfy.sh service down | Alerts are additive — watchdog and health monitor still log locally |
| Bot generates signals but PaperAdapter fill simulation is unrealistic | Fees/slippage already calibrated to Coinbase tiers in Sprint 21 |

## Transition: Soak → Live

When paper soak validates (72h clean run):
1. Change `trading.yaml`: `exchange.mode: paper` → `exchange.mode: live`
2. Optionally tighten alert thresholds in `monitoring.alerts`
3. Restart bot service
4. Trading health monitor continues working — same script, same alerts, different mode

The health monitor checks are mode-agnostic (log recency, signal generation, kill switch). The only live-specific checks (P&L, portfolio drift) are gated by the mode in config.
