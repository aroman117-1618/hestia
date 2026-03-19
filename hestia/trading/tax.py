"""
Tax lot tracking — P&L math, lot selection, and trade export.

Pure computation: no database calls, no async. The TaxLotTracker handles
lot creation dicts, HIFO/FIFO matching, and CSV export. Database persistence
remains in database.py; transaction management remains in manager.py.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List


class TaxLotTracker:
    """
    Stateless tax lot math engine.

    Supports HIFO (highest-in-first-out) and FIFO (first-in-first-out)
    lot selection methods. All methods are pure functions operating on
    dicts — no database coupling.
    """

    def __init__(self, method: str = "hifo") -> None:
        if method not in ("hifo", "fifo"):
            raise ValueError(f"Invalid tax lot method: {method}. Must be 'hifo' or 'fifo'.")
        self.method = method

    def create_lot_from_buy(
        self,
        trade_id: str,
        pair: str,
        quantity: float,
        price: float,
        fee: float,
        acquired_at: datetime,
        user_id: str = "user-default",
    ) -> Dict[str, Any]:
        """
        Build a tax lot dict from a buy trade.

        Cost basis = (price * quantity) + fee, so fees are baked into
        per-unit cost for accurate P&L on sell.

        Returns a dict ready for database insertion (matches TaxLot.to_dict() shape).
        """
        cost_basis = (price * quantity) + fee
        cost_per_unit = cost_basis / quantity if quantity > 0 else 0.0

        return {
            "id": str(uuid.uuid4()),
            "trade_id": trade_id,
            "pair": pair,
            "quantity": quantity,
            "remaining_quantity": quantity,
            "cost_basis": cost_basis,
            "cost_per_unit": cost_per_unit,
            "method": self.method,
            "status": "open",
            "acquired_at": acquired_at.isoformat(),
            "closed_at": None,
            "realized_pnl": 0.0,
            "user_id": user_id,
        }

    def match_lots_for_sell(
        self,
        open_lots: List[Dict[str, Any]],
        quantity: float,
        sell_price: float,
        sell_fee: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Match open lots against a sell, computing realized P&L.

        Sorts lots internally by method (HIFO = highest cost_per_unit first,
        FIFO = oldest acquired_at first) regardless of caller ordering.

        Returns:
            {
                "consumed_lots": [{"lot_id", "consumed_qty", "pnl", "new_remaining", "status", "closed_at"}],
                "realized_pnl": float,
                "unmatched_quantity": float,  # >0 if insufficient lots
            }
        """
        # Sort internally — never trust caller ordering
        if self.method == "hifo":
            sorted_lots = sorted(open_lots, key=lambda x: x["cost_per_unit"], reverse=True)
        else:  # fifo
            sorted_lots = sorted(open_lots, key=lambda x: x["acquired_at"])

        remaining = quantity
        total_pnl = 0.0
        consumed_lots: List[Dict[str, Any]] = []

        for lot in sorted_lots:
            if remaining <= 0:
                break

            available = lot["remaining_quantity"]
            consumed = min(available, remaining)
            cost_per_unit = lot["cost_per_unit"]

            proceeds = consumed * sell_price
            cost = consumed * cost_per_unit
            fee_portion = sell_fee * (consumed / quantity) if quantity > 0 else 0.0
            pnl = proceeds - cost - fee_portion
            total_pnl += pnl

            new_remaining = available - consumed

            entry: Dict[str, Any] = {
                "lot_id": lot["id"],
                "consumed_qty": consumed,
                "pnl": pnl,
                "new_remaining": new_remaining,
                "realized_pnl_delta": pnl,
                "prior_realized_pnl": lot.get("realized_pnl", 0.0),
            }

            if new_remaining <= 1e-10:
                entry["status"] = "closed"
                entry["closed_at"] = datetime.now(timezone.utc).isoformat()
            else:
                entry["status"] = "partial"
                entry["closed_at"] = None

            consumed_lots.append(entry)
            remaining -= consumed

        return {
            "consumed_lots": consumed_lots,
            "realized_pnl": total_pnl,
            "unmatched_quantity": max(remaining, 0.0),
        }

    @staticmethod
    def export_trades_csv(trades: List[Dict[str, Any]]) -> str:
        """
        Export trades to CSV string.

        Header: Date,Type,Asset,Quantity,Price,Fee,Total,Exchange
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Type", "Asset", "Quantity", "Price", "Fee", "Total", "Exchange"])

        for t in trades:
            price = float(t.get("price", 0.0))
            quantity = float(t.get("quantity", 0.0))
            fee = float(t.get("fee", 0.0))
            side = t.get("side", "buy")
            total = (price * quantity) + fee if side == "buy" else (price * quantity) - fee

            writer.writerow([
                t.get("timestamp", t.get("date", "")),
                side.upper(),
                t.get("pair", ""),
                f"{quantity:.8f}",
                f"{price:.2f}",
                f"{fee:.2f}",
                f"{total:.2f}",
                t.get("exchange", "unknown"),
            ])

        return output.getvalue()
