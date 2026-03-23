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
from .models import EntityType, Fact, FactStatus, SourceCategory, TemporalType

logger = get_logger()

MAX_TEXT_LENGTH = 2000

# Legacy single-stage prompt (kept for fallback)
EXTRACTION_PROMPT = """\
Extract entity-relationship-entity triplets from this text.
Return JSON: {"triplets": [{"source": "...", "source_type": "person|tool|concept|place|project|organization", "relation": "SCREAMING_SNAKE_CASE", "target": "...", "target_type": "person|tool|concept|place|project|organization", "fact": "natural language sentence", "confidence": 0.0-1.0}]}
Rules: only factual relationships, specific names not pronouns, max 5 per text. Exclude conversational fragments, greetings, UI descriptions, and instructions."""

# ── 3-Phase Staged Extraction (Sprint 20A) ─────────────────────

PHASE1_ENTITY_PROMPT = """\
List all named entities in this text. For each, classify as:
- person, tool, concept, place, project, organization
Return JSON: {"entities": [{"name": "...", "type": "person|tool|concept|place|project|organization"}]}
Only include specific named entities, not pronouns or generic references. Max 10.
GOOD examples: people's names, company names, product names, programming languages, frameworks, services, cities, universities.
EXCLUDE: conversational filler ("okay", "let me think"), greetings ("hi boss"), UI descriptions ("dark mode with warm colors"), file paths, device IDs, variable/class names (e.g. MemoryManager, get_user), and sentence fragments."""

PHASE2_SIGNIFICANCE_PROMPT = """\
For each entity, determine if it is a CORE ACTOR (directly relevant to the user's knowledge, decisions, or relationships) or BACKGROUND DETAIL (mentioned incidentally).
Only CORE ACTORS proceed to triple extraction.
BACKGROUND: entities mentioned only in passing with no relationship to the user or other entities.
CORE: people the user knows, tools they use, companies they work with, projects they're building, concepts they're learning about.
Return JSON: {"core": ["Entity1", "Entity2"], "background": ["Entity3"]}"""

PHASE3_PRISM_PROMPT = """\
PERSONA: You are a rigorous knowledge librarian. Only extract facts that belong in a permanent knowledge base.

REASONING: Before extracting, assess: Is this fact durable (true in 30 days)? Is it specific (names concrete entities)? Is it non-obvious?

INPUTS: Core entities: {core_entities}. Current date: {date}.

SECTIONS: Return exactly:
{{
  "triples": [{{
    "source": "...", "source_type": "person|tool|concept|place|project|organization",
    "relation": "SCREAMING_SNAKE_CASE",
    "target": "...", "target_type": "person|tool|concept|place|project|organization",
    "fact": "natural language sentence",
    "confidence": 0.0-1.0,
    "durability": 3,
    "temporal_type": "atemporal|static|dynamic|ephemeral"
  }}]
}}

METRICS: Assign confidence reflecting your certainty. Durability: 3=always true, 2=true for months/years, 1=true for weeks, 0=true only now.
REJECTION: Return {{"triples": []}} if the text is: conversational exchange with no factual content, instructions or commands, stream-of-consciousness or brainstorming without conclusions, meta-commentary about the conversation, UI descriptions, color/style preferences, or greetings. Max 5 triples."""

CONTRADICTION_PROMPT = """\
Given a new fact and existing facts between the same entities, determine if the new fact contradicts any existing fact.
Return JSON: {"contradicts": true/false, "supersedes_id": "fact-id-if-contradicts-or-null", "reason": "..."}
Only mark contradiction if the new fact makes an existing fact UNTRUE. Additive facts are NOT contradictions."""

# Valid entity type strings for safe parsing
_VALID_ENTITY_TYPES = {t.value for t in EntityType}


def _get_inference_client() -> Any:
    """Lazy import to avoid circular dependencies."""
    from hestia.inference import get_inference_client
    return get_inference_client()


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
        source_category: SourceCategory = SourceCategory.CONVERSATION,
        import_source_id: Optional[str] = None,
    ) -> List[Fact]:
        """Extract facts from text via 3-phase LLM pipeline.

        Phase 1: Entity identification
        Phase 2: Significance filtering (core vs background)
        Phase 3: PRISM triple extraction with durability scoring

        Falls back to legacy single-prompt on phase 1/2 failure.

        Args:
            text: The input text to extract facts from.
            source_chunk_id: Optional memory chunk ID for provenance.
            user_id: User scope for entity and fact storage.
            source_category: Provenance of the text.

        Returns:
            List of newly created Fact objects. Empty on failure.
        """
        truncated = text[:MAX_TEXT_LENGTH]
        logger.info(
            "Fact extraction starting",
            component=LogComponent.RESEARCH,
            data={"text_length": len(text)},
        )
        client = None
        try:
            client = _get_inference_client()
        except Exception as e:
            logger.error(
                "Inference client unavailable",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return []

        # ── Phase 1: Entity Identification ─────────────────
        core_entities = await self._phase1_entities(client, truncated)
        logger.info(
            "Fact extraction Phase 1 complete",
            component=LogComponent.RESEARCH,
            data={"entity_count": len(core_entities) if core_entities else 0, "fell_back": core_entities is None},
        )
        if core_entities is None:
            # Phase 1 failed — fall back to legacy single-prompt
            return await self._extract_legacy(client, truncated, source_chunk_id, user_id, source_category, import_source_id)

        # ── Phase 2: Significance Filter ───────────────────
        core_names = await self._phase2_significance(client, truncated, core_entities)
        logger.info(
            "Fact extraction Phase 2 complete",
            component=LogComponent.RESEARCH,
            data={"significant_count": len(core_names), "total_entities": len(core_entities)},
        )
        if not core_names:
            logger.info(
                "No core entities after significance filter",
                component=LogComponent.RESEARCH,
                data={"total_entities": len(core_entities)},
            )
            return []

        # ── Phase 3: PRISM Triple Extraction ───────────────
        from datetime import datetime, timezone
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        system_prompt = PHASE3_PRISM_PROMPT.format(
            core_entities=", ".join(core_names),
            date=date_str,
        )

        try:
            response = await client.complete(
                prompt=f"Text:\n{truncated}",
                system=system_prompt,
                format="json",
                think=False,
                force_tier="primary",
            )
        except Exception as e:
            logger.error(
                "Phase 3 PRISM extraction failed",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return []

        triplets = self._parse_extraction_response(response.content)
        logger.info(
            "Fact extraction Phase 3 complete",
            component=LogComponent.RESEARCH,
            data={"triplet_count": len(triplets)},
        )
        if not triplets:
            return []

        return await self._process_triplets(
            triplets, source_chunk_id, user_id, source_category, import_source_id
        )

    async def _phase1_entities(
        self, client: Any, text: str
    ) -> Optional[List[Dict[str, str]]]:
        """Phase 1: Extract named entities from text. Returns None on failure."""
        try:
            response = await client.complete(
                prompt=f"Text:\n{text}",
                system=PHASE1_ENTITY_PROMPT,
                format="json",
                think=False,
                force_tier="primary",
            )
            data = json.loads(response.content)
            entities = data.get("entities", [])
            if isinstance(entities, list) and entities:
                return [e for e in entities if isinstance(e, dict) and "name" in e]
        except Exception as e:
            logger.warning(
                "Phase 1 entity extraction failed",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
        return None

    async def _phase2_significance(
        self, client: Any, text: str, entities: List[Dict[str, str]]
    ) -> List[str]:
        """Phase 2: Filter to core actors. Returns list of core entity names."""
        entity_list = ", ".join(e["name"] for e in entities)
        prompt = f"Entities found: {entity_list}\n\nOriginal text:\n{text}"

        try:
            response = await client.complete(
                prompt=prompt,
                system=PHASE2_SIGNIFICANCE_PROMPT,
                format="json",
                think=False,
                force_tier="primary",
            )
            data = json.loads(response.content)
            core = data.get("core", [])
            if isinstance(core, list):
                return [str(name) for name in core]
        except Exception as e:
            logger.warning(
                "Phase 2 significance filter failed, using all entities",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            # Fall back to treating all entities as core
            return [e["name"] for e in entities]
        return []

    async def _extract_legacy(
        self,
        client: Any,
        text: str,
        source_chunk_id: Optional[str],
        user_id: str,
        source_category: SourceCategory,
        import_source_id: Optional[str] = None,
    ) -> List[Fact]:
        """Legacy single-prompt extraction (fallback when staged pipeline fails)."""
        try:
            response = await client.complete(
                prompt=f"Text:\n{text}",
                system=EXTRACTION_PROMPT,
                format="json",
                think=False,
                force_tier="primary",
            )
        except Exception as e:
            logger.error(
                "Legacy LLM extraction failed",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return []

        triplets = self._parse_extraction_response(response.content)
        if not triplets:
            return []

        return await self._process_triplets(
            triplets, source_chunk_id, user_id, source_category, import_source_id
        )

    async def _process_triplets(
        self,
        triplets: List[Dict[str, Any]],
        source_chunk_id: Optional[str],
        user_id: str,
        source_category: SourceCategory,
        import_source_id: Optional[str] = None,
    ) -> List[Fact]:
        """Resolve entities, check contradictions, store facts from parsed triplets."""
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
                    source_category=source_category,
                    user_id=user_id,
                )
                target_entity = await self._registry.resolve_entity(
                    name=triplet["target"],
                    entity_type=target_type,
                    source_category=source_category,
                    user_id=user_id,
                )

                confidence = triplet.get("confidence", 0.5)
                if not isinstance(confidence, (int, float)):
                    confidence = 0.5
                confidence = max(0.0, min(1.0, float(confidence)))

                # Parse durability from Phase 3 output (defaults for legacy)
                raw_durability = triplet.get("durability", 1)
                durability = max(0, min(3, int(raw_durability) if isinstance(raw_durability, (int, float)) else 1))

                raw_temporal = triplet.get("temporal_type", "dynamic")
                try:
                    temporal_type = TemporalType(raw_temporal)
                except ValueError:
                    temporal_type = TemporalType.DYNAMIC

                fact = Fact.create(
                    source_entity_id=source_entity.id,
                    relation=triplet["relation"],
                    target_entity_id=target_entity.id,
                    fact_text=triplet.get("fact", f"{triplet['source']} {triplet['relation']} {triplet['target']}"),
                    source_chunk_id=source_chunk_id,
                    confidence=confidence,
                    durability_score=durability,
                    temporal_type=temporal_type,
                    source_category=source_category,
                    import_source_id=import_source_id,
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
            client = _get_inference_client()
            response = await client.complete(
                prompt=prompt,
                system=CONTRADICTION_PROMPT,
                format="json",
                think=False,
                force_tier="primary",
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

        # Accept both "triplets" (legacy prompt) and "triples" (Phase 3 PRISM prompt)
        triplets = data.get("triplets") or data.get("triples")
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
