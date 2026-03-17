"""Tests for research graph: earliest_fact_date, center entity name resolution."""

import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pytest

from hestia.research.database import ResearchDatabase
from hestia.research.models import Entity, EntityType, Fact, FactStatus


@pytest.fixture
async def research_db(tmp_path: Path):
    """Create a fresh in-memory research database for testing."""
    db = ResearchDatabase(db_path=tmp_path / "test_research.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_get_earliest_fact_date_returns_min(research_db: ResearchDatabase):
    """get_earliest_fact_date() should return the earliest valid_at among active facts."""
    # Create two entities
    e1 = Entity.create(name="Alice", entity_type=EntityType.PERSON)
    e2 = Entity.create(name="Bob", entity_type=EntityType.PERSON)
    await research_db.create_entity(e1)
    await research_db.create_entity(e2)

    # Create facts with different valid_at dates
    older_date = datetime(2025, 1, 15, tzinfo=timezone.utc)
    newer_date = datetime(2026, 3, 10, tzinfo=timezone.utc)

    f1 = Fact.create(
        source_entity_id=e1.id,
        relation="KNOWS",
        target_entity_id=e2.id,
        fact_text="Alice knows Bob",
        valid_at=older_date,
    )
    f2 = Fact.create(
        source_entity_id=e2.id,
        relation="WORKS_WITH",
        target_entity_id=e1.id,
        fact_text="Bob works with Alice",
        valid_at=newer_date,
    )
    await research_db.create_fact(f1)
    await research_db.create_fact(f2)

    earliest = await research_db.get_earliest_fact_date()
    assert earliest is not None
    assert earliest == older_date


@pytest.mark.asyncio
async def test_get_earliest_fact_date_returns_none_when_empty(research_db: ResearchDatabase):
    """get_earliest_fact_date() should return None when no facts exist."""
    earliest = await research_db.get_earliest_fact_date()
    assert earliest is None


@pytest.mark.asyncio
async def test_get_earliest_fact_date_ignores_superseded(research_db: ResearchDatabase):
    """get_earliest_fact_date() should ignore non-active facts."""
    e1 = Entity.create(name="X", entity_type=EntityType.CONCEPT)
    e2 = Entity.create(name="Y", entity_type=EntityType.CONCEPT)
    await research_db.create_entity(e1)
    await research_db.create_entity(e2)

    old_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
    recent_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Superseded fact with older date
    f_old = Fact.create(
        source_entity_id=e1.id,
        relation="R",
        target_entity_id=e2.id,
        fact_text="old fact",
        valid_at=old_date,
    )
    await research_db.create_fact(f_old)
    await research_db.invalidate_fact(f_old.id)  # mark as superseded

    # Active fact with recent date
    f_new = Fact.create(
        source_entity_id=e1.id,
        relation="R2",
        target_entity_id=e2.id,
        fact_text="new fact",
        valid_at=recent_date,
    )
    await research_db.create_fact(f_new)

    earliest = await research_db.get_earliest_fact_date()
    assert earliest is not None
    assert earliest == recent_date


@pytest.mark.asyncio
async def test_center_entity_name_resolution(research_db: ResearchDatabase):
    """Searching entities by partial canonical_name should find a match."""
    entity = Entity.create(
        name="Andrew Lonati",
        entity_type=EntityType.PERSON,
    )
    await research_db.create_entity(entity)

    # Partial name search (simulating what the route does)
    cursor = await research_db._connection.execute(
        "SELECT id FROM entities WHERE LOWER(canonical_name) LIKE ? LIMIT 1",
        ("%andrew%",),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == entity.id


@pytest.mark.asyncio
async def test_center_entity_name_resolution_no_match(research_db: ResearchDatabase):
    """Searching for a non-existent entity name should return no rows."""
    entity = Entity.create(
        name="Hestia",
        entity_type=EntityType.PROJECT,
    )
    await research_db.create_entity(entity)

    cursor = await research_db._connection.execute(
        "SELECT id FROM entities WHERE LOWER(canonical_name) LIKE ? LIMIT 1",
        ("%nonexistent%",),
    )
    row = await cursor.fetchone()
    assert row is None
