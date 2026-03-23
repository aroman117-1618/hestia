"""Diagnostic tests for fact extraction pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hestia.research.fact_extractor import FactExtractor
from hestia.research.entity_registry import EntityRegistry
from hestia.research.models import SourceCategory


@pytest.mark.asyncio
class TestFactExtractionDiagnostic:

    async def test_extract_from_text_with_mock_client(self) -> None:
        """Full pipeline with mocked inference -- should produce facts."""
        mock_db = AsyncMock()
        mock_db.create_fact = AsyncMock(return_value=None)
        mock_db.find_facts_between = AsyncMock(return_value=[])
        mock_registry = AsyncMock(spec=EntityRegistry)
        mock_entity_source = MagicMock()
        mock_entity_source.id = "test-entity-1"
        mock_entity_source.name = "Hestia"
        mock_entity_target = MagicMock()
        mock_entity_target.id = "test-entity-2"
        mock_entity_target.name = "PostgreSQL"
        mock_registry.resolve_entity = AsyncMock(
            side_effect=[mock_entity_source, mock_entity_target]
        )

        extractor = FactExtractor(mock_db, mock_registry)

        # Phase 1 response: entity list
        phase1_resp = MagicMock()
        phase1_resp.content = '{"entities": [{"name": "Hestia", "type": "project"}, {"name": "PostgreSQL", "type": "tool"}]}'

        # Phase 2 response: significance filter
        phase2_resp = MagicMock()
        phase2_resp.content = '{"core": ["Hestia", "PostgreSQL"], "background": []}'

        # Phase 3 response: PRISM triples
        phase3_resp = MagicMock()
        phase3_resp.content = '{"triples": [{"source": "Hestia", "source_type": "project", "relation": "USES", "target": "PostgreSQL", "target_type": "tool", "fact": "Hestia uses PostgreSQL", "confidence": 0.9, "durability": 2, "temporal_type": "static"}]}'

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(side_effect=[phase1_resp, phase2_resp, phase3_resp])

        with patch(
            'hestia.research.fact_extractor._get_inference_client',
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            facts = await extractor.extract_from_text(
                "Hestia uses PostgreSQL as its primary database for structured data storage.",
                source_chunk_id="test-chunk-1",
            )

        assert mock_client.complete.call_count == 3, (
            f"Expected 3 LLM calls (phase 1/2/3), got {mock_client.complete.call_count}"
        )
        assert mock_db.create_fact.called, "create_fact was never called"
        assert len(facts) == 1, f"Expected 1 fact, got {len(facts)}"

    async def test_phase1_failure_falls_back_to_legacy(self) -> None:
        """When Phase 1 fails, pipeline should fall back to legacy extraction."""
        mock_db = AsyncMock()
        mock_db.create_fact = AsyncMock(return_value=None)
        mock_db.find_facts_between = AsyncMock(return_value=[])
        mock_registry = AsyncMock(spec=EntityRegistry)
        mock_entity = MagicMock()
        mock_entity.id = "e1"
        mock_entity.name = "Hestia"
        mock_registry.resolve_entity = AsyncMock(return_value=mock_entity)

        extractor = FactExtractor(mock_db, mock_registry)

        # Phase 1: return invalid JSON to trigger fallback
        phase1_resp = MagicMock()
        phase1_resp.content = 'not json'

        # Legacy fallback response
        legacy_resp = MagicMock()
        legacy_resp.content = '{"triplets": [{"source": "Hestia", "source_type": "project", "relation": "RUNS_ON", "target": "Mac Mini", "target_type": "tool", "fact": "Hestia runs on Mac Mini", "confidence": 0.8}]}'

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(side_effect=[phase1_resp, legacy_resp])

        with patch(
            'hestia.research.fact_extractor._get_inference_client',
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            facts = await extractor.extract_from_text(
                "Hestia runs on a Mac Mini M1 as its primary hardware platform.",
                source_chunk_id="test-chunk-2",
            )

        # Should have called generate twice: once for phase 1 (failed), once for legacy
        assert mock_client.complete.call_count == 2
        assert mock_db.create_fact.called, "Legacy fallback should have created facts"

    async def test_no_core_entities_returns_empty(self) -> None:
        """When Phase 2 filters out all entities, should return empty list."""
        mock_db = AsyncMock()
        mock_registry = AsyncMock(spec=EntityRegistry)
        extractor = FactExtractor(mock_db, mock_registry)

        phase1_resp = MagicMock()
        phase1_resp.content = '{"entities": [{"name": "SomeThing", "type": "concept"}]}'

        phase2_resp = MagicMock()
        phase2_resp.content = '{"core": [], "background": ["SomeThing"]}'

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(side_effect=[phase1_resp, phase2_resp])

        with patch(
            'hestia.research.fact_extractor._get_inference_client',
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            facts = await extractor.extract_from_text(
                "I was thinking about something earlier today.",
                source_chunk_id="test-chunk-3",
            )

        assert facts == [], "Should return empty when no core entities"
        assert not mock_db.create_fact.called

    async def test_inference_client_unavailable(self) -> None:
        """When inference client cannot be obtained, should return empty."""
        mock_db = AsyncMock()
        mock_registry = AsyncMock(spec=EntityRegistry)
        extractor = FactExtractor(mock_db, mock_registry)

        with patch(
            'hestia.research.fact_extractor._get_inference_client',
            new_callable=AsyncMock,
            side_effect=RuntimeError("Ollama not running"),
        ):
            facts = await extractor.extract_from_text(
                "Some text that should not be processed.",
            )

        assert facts == []
        assert not mock_db.create_fact.called
