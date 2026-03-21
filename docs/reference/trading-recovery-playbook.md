# Trading Recovery Playbook

Quick-response guide when you receive a trading alert or suspect something is wrong.

## Check Status

```bash
# Is the server alive?
ssh andrewroman117@hestia-3.local "curl -sk https://localhost:8443/v1/ping"

# Is the bot service running?
ssh andrewroman117@hestia-3.local "launchctl list | grep trading-bots"

# Recent trading logs (last 20 entries)
ssh andrewroman117@hestia-3.local "grep 'component.*trading' ~/hestia/logs/hestia.log | tail -20"

# Any kill switch or circuit breaker triggers?
ssh andrewroman117@hestia-3.local "grep -i 'kill.switch\|circuit.breaker\|CRITICAL' ~/hestia/logs/hestia.log | tail -10"

# Trade count
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

## ntfy.sh Subscription

Subscribe to alerts on your phone:
1. Install ntfy app (iOS or Android)
2. Subscribe to topic: `hestia-trading-49ceebba`
3. You'll receive push notifications when the watchdog restarts the server
