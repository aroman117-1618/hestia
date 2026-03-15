"""
Fact Extractor — LLM-powered extraction of entity-relationship triplets
and contradiction detection against existing knowledge graph facts.

Pipeline:
1. Send text to local LLM with structured extraction prompt
2. Parse JSON triplets from response
3. Resolve entities via EntityRegistry (dedup + create)
4. Check contradictions against existing facts between same entity pairs
5. Store new facts via ResearchDatabase
"""

import json
from typing import Any, Dict, List, Optional

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase
from .entity_registry import EntityRegistry
from .models import EntityType, Fact, FactStatus

logger = get_logger()

MAX_TEXT_LENGTH = 2000

EXTRACTION_PROMPT = """\
Extract entity-relationship-entity triplets from this text.
Return JSON: {"triplets": [{"source": "...", "source_type": "person|tool|concept|place|project|organization", "relation": "SCREAMING_SNAKE_CASE", "target": "...", "target_type": "person|tool|concept|place|project|organization", "fact": "natural language sentence", "confidence": 0.0-1.0}]}
Rules: only factual relationships, specific names not pronouns, max 5 per text."""

CONTRADICTION_PROMPT = """\
Given a new fact and existing facts between the same entities, determine if the new fact contradicts any existing fact.
Return JSON: {"contradicts": true/false, "supersedes_id": "fact-id-if-contradicts-or-null", "reason": "..."}
Only mark contradiction if the new fact makes an existing fact UNTRUE. Additive facts are NOT contradictions."""

# Valid entity type strings for safe parsing
_VALID_ENTITY_TYPES = {t.value for t in EntityType}


async def _get_inference_client() -> Any:
    """Lazy import to avoid circular dependencies."""
    from hestia.inference import get_inference_client
    return await get_inference_client()


class FactExtractor:
    """Extract entity-relationship triplets from text using local LLM."""

    def __init__(self, database: ResearchDatabase, registry: EntityRegistry) -> None:
        self._db = database
        self._registry = registry

    async def extract_from_text(
        self,
        text: str,
        source_chunk_id: Optional[str] = None,
        user_id: str = "default",
    ) -> List[Fact]:
        """Extract facts from text via LLM, resolve entities, check contradictions.

        Args:
            text: The input text to extract facts from.
            source_chunk_id: Optional memory chunk ID for provenance.
            user_id: User scope for entity and fact storage.

        Returns:
            List of newly created Fact objects. Empty on failure.
        """
        truncated = text[:MAX_TEXT_LENGTH]

        try:
            client = await _get_inference_client()
            response = await client.generate(
                prompt=f"Text:\n{truncated}",
                system=EXTRACTION_PROMPT,
                format="json",
            )
        except Exception as e:
            logger.error(
                "LLM extraction failed",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return []

        triplets = self._parse_extraction_response(response.content)
        if not triplets:
            return []

        created_facts: List[Fact] = []

        for triplet in triplets:
            try:
                source_type_str = triplet.get("source_type", "concept")
                target_type_str = triplet.get("target_type", "concept")
                source_type = EntityType(source_type_str) if source_type_str in _VALID_ENTITY_TYPES else EntityType.CONCEPT
                target_type = EntityType(target_type_str) if target_type_str in _VALID_ENTITY_TYPES else EntityType.CONCEPT

                source_entity = await self._registry.resolve_entity(
                    name=triplet["source"],
                    entity_type=source_type,
                    user_id=user_id,
                )
                target_entity = await self._registry.resolve_entity(
                    name=triplet["target"],
                    entity_type=target_type,
                    user_id=user_id,
                )

                confidence = triplet.get("confidence", 0.5)
                if not isinstance(confidence, (int, float)):
                    confidence = 0.5
                confidence = max(0.0, min(1.0, float(confidence)))

                fact = Fact.create(
                    source_entity_id=source_entity.id,
                    relation=triplet["relation"],
                    target_entity_id=target_entity.id,
                    fact_text=triplet.get("fact", f"{triplet['source']} {triplet['relation']} {triplet['target']}"),
                    source_chunk_id=source_chunk_id,
                    confidence=confidence,
                    user_id=user_id,
                )

                # Check contradictions against existing facts between same entities
                existing = await self._db.find_facts_between(
                    source_entity.id, target_entity.id, active_only=True
                )
                if existing:
                    await self.check_contradictions(fact, existing)

                await self._db.create_fact(fact)
                created_facts.append(fact)

            except Exception as e:
                logger.warning(
                    "Failed to process triplet",
                    component=LogComponent.RESEARCH,
                    data={"error": type(e).__name__, "triplet_source": triplet.get("source", "unknown")},
                )
                continue

        logger.info(
            "Fact extraction complete",
            component=LogComponent.RESEARCH,
            data={"facts_created": len(created_facts), "triplets_parsed": len(triplets)},
        )
        return created_facts

    async def check_contradictions(
        self, new_fact: Fact, existing_facts: List[Fact]
    ) -> None:
        """Check if new_fact contradicts any existing facts via LLM.

        If contradiction detected and supersedes_id provided, the old fact
        is invalidated (marked SUPERSEDED).

        Args:
            new_fact: The newly extracted fact to check.
            existing_facts: Active facts between the same entity pair.
        """
        if not existing_facts:
            return

        existing_text = "\n".join(
            f"- [{f.id}] {f.fact_text}" for f in existing_facts
        )
        prompt = (
            f"New fact: {new_fact.fact_text}\n\n"
            f"Existing facts between same entities:\n{existing_text}"
        )

        try:
            client = await _get_inference_client()
            response = await client.generate(
                prompt=prompt,
                system=CONTRADICTION_PROMPT,
                format="json",
            )
        except Exception as e:
            logger.warning(
                "Contradiction check failed, assuming no conflict",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return

        result = self._parse_contradiction_response(response.content)

        if result.get("contradicts") and result.get("supersedes_id"):
            supersedes_id = result["supersedes_id"]
            await self._db.invalidate_fact(supersedes_id)
            logger.info(
                "Fact superseded",
                component=LogComponent.RESEARCH,
                data={
                    "superseded_id": supersedes_id,
                    "new_fact_text": new_fact.fact_text,
                    "reason": result.get("reason", ""),
                },
            )

    def _parse_extraction_response(self, content: str) -> List[Dict[str, Any]]:
        """Parse LLM extraction response into list of triplet dicts.

        Args:
            content: Raw LLM response string (expected JSON).

        Returns:
            List of validated triplet dicts with source/relation/target keys.
            Empty list on any parse failure.
        """
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return []

        triplets = data.get("triplets")
        if not isinstance(triplets, list):
            return []

        validated: List[Dict[str, Any]] = []
        for t in triplets:
            if not isinstance(t, dict):
                continue
            if all(k in t for k in ("source", "relation", "target")):
                validated.append(t)

        return validated

    def _parse_contradiction_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM contradiction check response.

        Args:
            content: Raw LLM response string (expected JSON).

        Returns:
            Dict with 'contradicts' (bool), optional 'supersedes_id' and 'reason'.
            Returns {"contradicts": False} on any parse failure.
        """
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"contradicts": False}

        return {
            "contradicts": bool(data.get("contradicts", False)),
            "supersedes_id": data.get("supersedes_id"),
            "reason": data.get("reason", ""),
        }
