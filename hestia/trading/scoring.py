"""Confidence scoring — composite pre-execution quality metric.

Formula: 0.30 * signal_confidence
       + 0.25 * risk_efficiency    (adjusted_qty / requested_qty)
       + 0.25 * execution_quality  (1 - abs(slippage_pct))
       + 0.20 * timing_alignment   (volume_confirmed * trend_aligned)

Renamed from "satisfaction" per second-opinion review — this is a
pre-execution confidence metric, not a post-hoc satisfaction measure.
Outcome-based scoring (P&L, MAE) deferred to Sprint 27.
"""

from typing import Optional


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
        """Compute composite confidence score (0.0 - 1.0).

        Args:
            signal_confidence: Strategy signal confidence (0-1)
            requested_quantity: Original quantity from signal
            adjusted_quantity: Quantity after risk adjustment
            expected_price: Price from signal
            filled_price: Actual fill price from exchange
            volume_confirmed: Whether volume filter confirmed the signal
            trend_aligned: Whether trend filter aligned with the signal
        """
        # Signal confidence (0-1, clamped)
        sig = max(0.0, min(1.0, signal_confidence))

        # Risk efficiency: how much of requested size survived risk checks
        risk_eff = (adjusted_quantity / requested_quantity) if requested_quantity > 0 else 0.0
        risk_eff = max(0.0, min(1.0, risk_eff))

        # Execution quality: 1 - slippage percentage (scaled so 5% = 0.0)
        if expected_price > 0:
            slippage_pct = abs(filled_price - expected_price) / expected_price
            exec_qual = max(0.0, 1.0 - slippage_pct * 20)
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
