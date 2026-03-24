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
