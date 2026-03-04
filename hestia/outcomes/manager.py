"""
Outcome manager -- tracks chat response outcomes for the learning cycle.

Records every chat response as an OutcomeRecord, processes explicit user
feedback (thumbs-up/down/correction), and detects implicit behavioral
signals from follow-up timing patterns.

Outcome tracking failures NEVER break chat -- all operations are wrapped
in try/except with silent fallback.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .database import OutcomeDatabase, get_outcome_database
from .models import OutcomeFeedback, OutcomeRecord

logger = get_logger()

# Implicit signal thresholds (milliseconds)
QUICK_FOLLOWUP_THRESHOLD_MS = 30_000    # < 30s = quick follow-up (likely negative)
LONG_GAP_THRESHOLD_MS = 300_000         # > 5min = long gap (positive)

_instance: Optional["OutcomeManager"] = None


class OutcomeManager:
    """
    Tracks chat response outcomes for the Learning Cycle.

    Creates an OutcomeRecord for every chat response, updates them with
    explicit feedback or implicit signals, and provides aggregate stats.
    """

    def __init__(self, database: Optional[OutcomeDatabase] = None):
        self._database = database

    async def initialize(self) -> None:
        """Initialize database and run startup cleanup."""
        if self._database is None:
            self._database = await get_outcome_database()

        # Clean up old records on startup
        deleted = await self._database.cleanup_old(retention_days=90)
        if deleted > 0:
            logger.info(
                f"Cleaned up {deleted} old outcome records",
                component=LogComponent.OUTCOMES,
            )

        logger.info(
            "Outcome manager initialized",
            component=LogComponent.OUTCOMES,
        )

    async def close(self) -> None:
        """Close manager resources."""
        logger.debug(
            "Outcome manager closed",
            component=LogComponent.OUTCOMES,
        )

    # -- Public API -----------------------------------------------------------

    async def track_response(
        self,
        user_id: str,
        device_id: Optional[str],
        session_id: Optional[str],
        message_id: Optional[str],
        response_content: Optional[str],
        response_type: Optional[str],
        duration_ms: Optional[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a chat response outcome.

        Creates an OutcomeRecord and stores it. Returns the outcome ID.
        This should be called after every chat response.
        """
        outcome_id = str(uuid.uuid4())

        record = OutcomeRecord(
            id=outcome_id,
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            message_id=message_id,
            response_content=response_content,
            response_type=response_type,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        stored_id = await self._database.store_outcome(record)

        logger.debug(
            f"Tracked outcome {stored_id}",
            component=LogComponent.OUTCOMES,
            data={
                "outcome_id": stored_id,
                "session_id": session_id,
                "response_type": response_type,
                "duration_ms": duration_ms,
            },
        )

        return stored_id

    async def record_feedback(
        self,
        outcome_id: str,
        user_id: str,
        feedback: str,
        note: Optional[str] = None,
    ) -> bool:
        """
        Record explicit user feedback on an outcome.

        Validates feedback against OutcomeFeedback enum values.
        Returns True if the outcome was found and updated.
        """
        # Validate feedback value
        valid_values = [f.value for f in OutcomeFeedback]
        if feedback not in valid_values:
            logger.warning(
                f"Invalid feedback value: {feedback}",
                component=LogComponent.OUTCOMES,
                data={"valid_values": valid_values},
            )
            return False

        success = await self._database.update_feedback(
            outcome_id=outcome_id,
            user_id=user_id,
            feedback=feedback,
            note=note,
        )

        if success:
            logger.debug(
                f"Recorded feedback on outcome {outcome_id}: {feedback}",
                component=LogComponent.OUTCOMES,
            )

        return success

    async def detect_implicit_signal(
        self,
        session_id: str,
        user_id: str,
        new_message_content: str,
    ) -> Optional[str]:
        """
        Detect implicit behavioral signal from follow-up timing.

        Finds the latest unsignaled outcome in this session, calculates
        elapsed time since it was created, and assigns a signal:
        - elapsed < 30s  -> "quick_followup" (likely negative)
        - elapsed > 300s -> "long_gap" (positive)
        - 30s-300s       -> "accepted" (neutral-positive)

        Returns the signal name, or None if no pending outcome exists.
        """
        latest = await self._database.get_latest_for_session(session_id, user_id)
        if latest is None:
            return None

        # Calculate elapsed time from outcome timestamp to now
        try:
            outcome_ts = datetime.fromisoformat(latest["timestamp"])
        except (ValueError, TypeError):
            return None

        now = datetime.now(timezone.utc)
        # Ensure both are timezone-aware for comparison
        if outcome_ts.tzinfo is None:
            outcome_ts = outcome_ts.replace(tzinfo=timezone.utc)

        elapsed_ms = int((now - outcome_ts).total_seconds() * 1000)

        # Determine signal based on elapsed time
        if elapsed_ms < QUICK_FOLLOWUP_THRESHOLD_MS:
            signal = "quick_followup"
        elif elapsed_ms > LONG_GAP_THRESHOLD_MS:
            signal = "long_gap"
        else:
            signal = "accepted"

        # Update the outcome record
        await self._database.update_implicit_signal(
            outcome_id=latest["id"],
            signal=signal,
            elapsed_ms=elapsed_ms,
        )

        logger.debug(
            f"Detected implicit signal: {signal}",
            component=LogComponent.OUTCOMES,
            data={
                "outcome_id": latest["id"],
                "elapsed_ms": elapsed_ms,
                "signal": signal,
            },
        )

        return signal

    async def get_outcomes(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get outcome records with optional filters."""
        return await self._database.get_outcomes(
            user_id=user_id,
            session_id=session_id,
            days=days,
            limit=limit,
            offset=offset,
        )

    async def get_outcome(
        self, outcome_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single outcome record."""
        return await self._database.get_outcome(outcome_id, user_id)

    async def get_stats(
        self, user_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """Get aggregated outcome statistics."""
        return await self._database.get_stats(user_id, days)


async def get_outcome_manager() -> OutcomeManager:
    """Singleton factory for OutcomeManager."""
    global _instance
    if _instance is None:
        _instance = OutcomeManager()
        await _instance.initialize()
    return _instance


async def close_outcome_manager() -> None:
    """Close the singleton outcome manager."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
