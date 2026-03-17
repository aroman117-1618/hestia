"""Outcome-to-Principle Distiller — extract behavioral principles from outcomes.

Queries high-signal outcomes (positive feedback, long-gap implicit signal),
runs LLM distillation to extract reusable principles, stores them via
the existing PrincipleStore with status="pending".

Quality gate: rejects principles < 10 words or matching generic phrases.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.learning.database import LearningDatabase
from hestia.learning.models import DistillationRun, DistillationStatus
from hestia.research.models import Principle, PrincipleStatus

logger = get_logger()

DISTILLATION_PROMPT = """Analyze these successful AI assistant interactions.
The user gave positive feedback or spent significant time with these responses.

Interactions:
{outcomes}

Extract reusable behavioral principles about what makes a good response.
Focus on: communication style, depth preferences, format preferences, topic patterns.
Output exactly one principle per line, prefixed with [domain].
Only output principles you are confident about. If nothing stands out, output nothing.

Example format:
[communication] User prefers concise bullet-point answers over long paragraphs
[coding] User wants test examples alongside code explanations"""

# Generic phrases that indicate low-quality principles
_GENERIC_BLACKLIST = [
    "user likes good",
    "user wants correct",
    "user prefers helpful",
    "user values quality",
    "be accurate",
    "be helpful",
]

MIN_PRINCIPLE_WORDS = 10


class OutcomeDistiller:
    """Extract principles from high-quality outcomes."""

    def __init__(
        self,
        learning_db: LearningDatabase,
        outcome_db: Any,
        principle_store: Optional[Any] = None,
        inference_client: Optional[Any] = None,
    ) -> None:
        self._learning_db = learning_db
        self._outcome_db = outcome_db
        self._principle_store = principle_store
        self._inference = inference_client

    async def distill_from_outcomes(
        self,
        user_id: str,
        days: int = 30,
        min_outcomes: int = 3,
    ) -> Dict[str, Any]:
        """Run a distillation pass over recent high-signal outcomes.

        Returns: {outcomes_analyzed, principles_generated, run_id, error}
        """
        run = DistillationRun(
            id=str(uuid.uuid4()),
            user_id=user_id,
            run_timestamp=datetime.now(timezone.utc),
            source="manual",
        )
        await self._learning_db.create_distillation_run(run)

        result: Dict[str, Any] = {
            "outcomes_analyzed": 0,
            "principles_generated": 0,
            "run_id": run.id,
            "error": None,
        }

        try:
            outcomes = await self._outcome_db.get_high_signal_outcomes(
                user_id=user_id, days=days,
            )
            result["outcomes_analyzed"] = len(outcomes)

            if len(outcomes) < min_outcomes:
                logger.info(
                    f"Insufficient outcomes for distillation: {len(outcomes)} < {min_outcomes}",
                    component=LogComponent.LEARNING,
                )
                await self._learning_db.update_distillation_run(
                    run.id, status="complete",
                    outcomes_processed=len(outcomes),
                )
                return result

            if self._inference is None:
                logger.info(
                    "No inference client — skipping LLM distillation",
                    component=LogComponent.LEARNING,
                )
                await self._learning_db.update_distillation_run(
                    run.id, status="complete",
                    outcomes_processed=len(outcomes),
                )
                return result

            # Build prompt
            formatted = self._format_outcomes(outcomes)
            prompt = DISTILLATION_PROMPT.format(outcomes=formatted)

            # Call LLM
            response = await self._inference.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a behavioral analysis assistant.",
                temperature=0.3,
                max_tokens=1024,
            )

            # Parse and quality-filter principles
            principles = self._parse_principles(response.content, user_id)
            result["principles_generated"] = len(principles)

            # Store principles
            if self._principle_store and principles:
                for principle in principles:
                    await self._principle_store.store_principle(principle)
                    for outcome in outcomes:
                        await self._learning_db.link_outcome_to_principle(
                            user_id=user_id,
                            outcome_id=outcome.id,
                            principle_id=principle.id,
                            confidence=principle.confidence,
                            source="batch_distill",
                        )

            await self._learning_db.update_distillation_run(
                run.id, status="complete",
                outcomes_processed=len(outcomes),
                principles_generated=len(principles),
            )

        except Exception as e:
            result["error"] = str(e)
            await self._learning_db.update_distillation_run(
                run.id, status="failed",
                error_message=f"{type(e).__name__}: {e}",
            )
            logger.warning(
                f"Distillation failed: {type(e).__name__}",
                component=LogComponent.LEARNING,
            )

        return result

    def _format_outcomes(self, outcomes: List[Any]) -> str:
        """Format outcomes for the distillation prompt."""
        lines = []
        for i, o in enumerate(outcomes[:20], 1):
            feedback = f" [feedback: {o.feedback}]" if o.feedback else ""
            note = f" Note: {o.feedback_note}" if getattr(o, "feedback_note", None) else ""
            content = (o.response_content or "")[:300]
            lines.append(f"{i}. {content}{feedback}{note}")
        return "\n".join(lines)

    def _parse_principles(self, llm_output: str, user_id: str) -> List[Principle]:
        """Parse LLM output into Principle objects with quality filtering."""
        principles = []
        for line in llm_output.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            bracket_end = line.find("]")
            if bracket_end < 0:
                continue
            domain = line[1:bracket_end].strip()
            content = line[bracket_end + 1:].strip()
            if not content:
                continue

            # Quality gate: reject short or generic principles
            word_count = len(content.split())
            if word_count < MIN_PRINCIPLE_WORDS:
                logger.debug(
                    f"Rejected short principle ({word_count} words): {content[:50]}",
                    component=LogComponent.LEARNING,
                )
                continue

            content_lower = content.lower()
            if any(phrase in content_lower for phrase in _GENERIC_BLACKLIST):
                logger.debug(
                    f"Rejected generic principle: {content[:50]}",
                    component=LogComponent.LEARNING,
                )
                continue

            principles.append(Principle(
                id=str(uuid.uuid4()),
                content=content,
                domain=domain,
                confidence=0.7,
                status=PrincipleStatus.PENDING,
                source_chunk_ids=[],
                topics=[domain],
                entities=[],
            ))
        return principles
