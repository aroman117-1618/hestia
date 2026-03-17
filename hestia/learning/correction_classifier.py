"""Correction Classifier — detect and categorize user corrections.

Heuristic-first approach: keyword matching for high-confidence cases.
No LLM inference required — pure string matching on feedback notes.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.learning.database import LearningDatabase
from hestia.learning.models import Correction, CorrectionType

logger = get_logger()

# Keyword patterns for heuristic classification (checked in priority order)
_TIMEZONE_PATTERNS = re.compile(
    r'\b(timezone?|utc|est|pst|cst|mst|am\s*/?\s*pm|[AP]M|gmt|'
    r'time\s*zone|daylight|morning|afternoon|evening)\b',
    re.IGNORECASE,
)
_TOOL_PATTERNS = re.compile(
    r'\b(should\s+have\s+used|wrong\s+tool|didn\'?t\s+use|'
    r'use\s+the|tool|calendar|reminder|note|mail)\b',
    re.IGNORECASE,
)
_PREFERENCE_PATTERNS = re.compile(
    r'\b(prefer|rather|instead|style|format|tone|'
    r'don\'?t\s+like|I\s+like|too\s+long|too\s+short)\b',
    re.IGNORECASE,
)


class CorrectionClassifier:
    """Classify user corrections from outcome feedback."""

    def __init__(
        self,
        learning_db: LearningDatabase,
        outcome_db: Any,
        inference_client: Optional[Any] = None,
    ) -> None:
        self._learning_db = learning_db
        self._outcome_db = outcome_db
        self._inference = inference_client

    @staticmethod
    def heuristic_classify(note: str) -> CorrectionType:
        """Classify correction type using keyword heuristics.

        Priority order: timezone > tool_usage > preference > factual (default).
        """
        if not note:
            return CorrectionType.FACTUAL
        if _TIMEZONE_PATTERNS.search(note):
            return CorrectionType.TIMEZONE
        if _TOOL_PATTERNS.search(note):
            return CorrectionType.TOOL_USAGE
        if _PREFERENCE_PATTERNS.search(note):
            return CorrectionType.PREFERENCE
        return CorrectionType.FACTUAL

    async def classify_outcome(
        self,
        user_id: str,
        outcome_id: str,
        feedback_note: str,
        response_content: str,
    ) -> Optional[Correction]:
        """Classify a single correction and store it.

        Returns the Correction if newly classified, None if already exists.
        """
        existing = await self._learning_db.get_correction(outcome_id, user_id)
        if existing:
            return None

        correction_type = self.heuristic_classify(feedback_note)
        confidence = 0.75

        if correction_type == CorrectionType.TIMEZONE and "timezone" in feedback_note.lower():
            confidence = 0.90
        elif correction_type == CorrectionType.TOOL_USAGE and "should have used" in feedback_note.lower():
            confidence = 0.90

        correction = Correction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            outcome_id=outcome_id,
            correction_type=correction_type,
            analysis=f"Heuristic: matched {correction_type.value} pattern",
            confidence=confidence,
        )

        await self._learning_db.create_correction(correction)
        logger.info(
            "Correction classified",
            component=LogComponent.LEARNING,
            data={"outcome_id": outcome_id, "type": correction_type.value, "confidence": confidence},
        )
        return correction

    async def classify_all_pending(self, user_id: str) -> Dict[str, int]:
        """Classify all unclassified correction outcomes.

        Returns: {classified, skipped, errors}
        """
        stats: Dict[str, int] = {"classified": 0, "skipped": 0, "errors": 0}

        try:
            outcomes = await self._outcome_db.list_outcomes_with_feedback(
                user_id=user_id, feedback="correction", limit=50,
            )
        except Exception as e:
            logger.warning(
                f"Failed to fetch correction outcomes: {type(e).__name__}",
                component=LogComponent.LEARNING,
            )
            return stats

        for outcome in outcomes:
            try:
                result = await self.classify_outcome(
                    user_id=user_id,
                    outcome_id=outcome.id,
                    feedback_note=outcome.feedback_note or "",
                    response_content=outcome.response_content or "",
                )
                if result:
                    stats["classified"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.warning(
                    f"Failed to classify correction {outcome.id}: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )

        return stats
