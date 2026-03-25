"""
Tests for entity references — cross-module linking for Research entities.
TDD: models, database CRUD, and API endpoints.
"""

import uuid

import pytest


# =============================================================================
# Model Tests
# =============================================================================


class TestEntityReferenceModels:
    def test_reference_creation(self) -> None:
        from hestia.research.references import EntityReference, ReferenceModule

        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.WORKFLOW,
            item_id="wf-step-456",
            context="Used in 'Trading Bot' workflow step 3",
            user_id="user-1",
        )
        assert ref.entity_id == "ent-123"
        assert ref.module == ReferenceModule.WORKFLOW
        assert ref.item_id == "wf-step-456"

    def test_reference_to_dict(self) -> None:
        from hestia.research.references import EntityReference, ReferenceModule

        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.CHAT,
            item_id="msg-789",
            context="Mentioned in chat",
            user_id="user-1",
        )
        d = ref.to_dict()
        assert d["entityId"] == "ent-123"
        assert d["module"] == "chat"
        assert d["itemId"] == "msg-789"
        assert "id" in d
        assert "createdAt" in d

    def test_reference_from_dict_camel_case(self) -> None:
        from hestia.research.references import EntityReference, ReferenceModule

        data = {
            "id": "ref-abc",
            "entityId": "ent-999",
            "module": "command",
            "itemId": "cmd-1",
            "context": "From command center",
            "userId": "user-2",
            "createdAt": "2026-03-24T00:00:00+00:00",
        }
        ref = EntityReference.from_dict(data)
        assert ref.id == "ref-abc"
        assert ref.entity_id == "ent-999"
        assert ref.module == ReferenceModule.COMMAND
        assert ref.item_id == "cmd-1"
        assert ref.user_id == "user-2"

    def test_reference_from_dict_snake_case(self) -> None:
        from hestia.research.references import EntityReference, ReferenceModule

        data = {
            "entity_id": "ent-777",
            "module": "memory",
            "item_id": "mem-5",
            "context": "Memory ref",
            "user_id": "user-3",
        }
        ref = EntityReference.from_dict(data)
        assert ref.entity_id == "ent-777"
        assert ref.module == ReferenceModule.MEMORY
        assert ref.item_id == "mem-5"

    def test_all_modules_exist(self) -> None:
        from hestia.research.references import ReferenceModule

        assert ReferenceModule.WORKFLOW.value == "workflow"
        assert ReferenceModule.CHAT.value == "chat"
        assert ReferenceModule.COMMAND.value == "command"
        assert ReferenceModule.RESEARCH_CANVAS.value == "research_canvas"
        assert ReferenceModule.MEMORY.value == "memory"


# =============================================================================
# Database Tests
# =============================================================================


@pytest.mark.asyncio
class TestEntityReferenceDatabase:
    async def test_add_and_get_references(self, tmp_path) -> None:
        from hestia.research.database import ResearchDatabase
        from hestia.research.references import EntityReference, ReferenceModule

        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()
        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.WORKFLOW,
            item_id="wf-456",
            context="Step 3",
            user_id="user-1",
        )
        await db.add_entity_reference(ref)
        refs = await db.get_entity_references("ent-123")
        assert len(refs) == 1
        assert refs[0].module == ReferenceModule.WORKFLOW
        assert refs[0].entity_id == "ent-123"

    async def test_get_references_by_module(self, tmp_path) -> None:
        from hestia.research.database import ResearchDatabase
        from hestia.research.references import EntityReference, ReferenceModule

        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()
        for module in [ReferenceModule.WORKFLOW, ReferenceModule.CHAT, ReferenceModule.CHAT]:
            ref = EntityReference(
                entity_id="ent-123",
                module=module,
                item_id=f"item-{module.value}-{uuid.uuid4()}",
                context=f"Ref from {module.value}",
                user_id="user-1",
            )
            await db.add_entity_reference(ref)
        refs = await db.get_entity_references("ent-123", module=ReferenceModule.CHAT)
        assert len(refs) == 2

    async def test_delete_references_by_item(self, tmp_path) -> None:
        from hestia.research.database import ResearchDatabase
        from hestia.research.references import EntityReference, ReferenceModule

        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()
        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.WORKFLOW,
            item_id="wf-456",
            context="Test",
            user_id="user-1",
        )
        await db.add_entity_reference(ref)
        await db.delete_entity_references_by_item(ReferenceModule.WORKFLOW, "wf-456")
        refs = await db.get_entity_references("ent-123")
        assert len(refs) == 0

    async def test_upsert_on_duplicate(self, tmp_path) -> None:
        """Duplicate (entity_id, module, item_id) should not raise an error."""
        from hestia.research.database import ResearchDatabase
        from hestia.research.references import EntityReference, ReferenceModule

        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()
        ref1 = EntityReference(
            entity_id="ent-1",
            module=ReferenceModule.CHAT,
            item_id="msg-1",
            context="First mention",
            user_id="user-1",
        )
        ref2 = EntityReference(
            entity_id="ent-1",
            module=ReferenceModule.CHAT,
            item_id="msg-1",
            context="Updated mention",
            user_id="user-1",
        )
        await db.add_entity_reference(ref1)
        await db.add_entity_reference(ref2)  # should not raise
        refs = await db.get_entity_references("ent-1")
        assert len(refs) == 1  # UNIQUE constraint: only one row

    async def test_pagination(self, tmp_path) -> None:
        from hestia.research.database import ResearchDatabase
        from hestia.research.references import EntityReference, ReferenceModule

        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()
        for i in range(5):
            ref = EntityReference(
                entity_id="ent-page",
                module=ReferenceModule.MEMORY,
                item_id=f"mem-{i}",
                context=f"ref {i}",
                user_id="user-1",
            )
            await db.add_entity_reference(ref)
        page1 = await db.get_entity_references("ent-page", limit=3, offset=0)
        page2 = await db.get_entity_references("ent-page", limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2
