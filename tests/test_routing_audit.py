"""Tests for routing audit database."""

import pytest
from pathlib import Path

from hestia.orchestration.audit_db import RoutingAuditDatabase
from hestia.orchestration.agent_models import RoutingAuditEntry


@pytest.fixture
async def audit_db(tmp_path):
    db = RoutingAuditDatabase(db_path=tmp_path / "test_audit.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_store_and_retrieve(audit_db):
    entry = RoutingAuditEntry.create(
        user_id="user-1",
        request_id="req-abc",
        intent="chat",
        route_chosen="artemis",
        route_confidence=0.85,
    )
    entry.actual_agents = ["artemis"]
    entry.total_inference_calls = 2
    entry.total_duration_ms = 3500

    await audit_db.store(entry)
    results = await audit_db.get_recent(user_id="user-1", limit=10)
    assert len(results) == 1
    assert results[0]["route_chosen"] == "artemis"
    assert results[0]["route_confidence"] == 0.85


@pytest.mark.asyncio
async def test_user_scoping(audit_db):
    e1 = RoutingAuditEntry.create("user-1", "req-1", "chat", "artemis", 0.8)
    e2 = RoutingAuditEntry.create("user-2", "req-2", "coding", "apollo", 0.9)
    await audit_db.store(e1)
    await audit_db.store(e2)

    results = await audit_db.get_recent(user_id="user-1")
    assert len(results) == 1
    assert results[0]["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_route_stats(audit_db):
    for route in ["artemis", "artemis", "apollo", "hestia_solo"]:
        entry = RoutingAuditEntry.create("user-1", f"req-{route}", "chat", route, 0.8)
        await audit_db.store(entry)

    stats = await audit_db.get_route_stats(user_id="user-1")
    assert stats["artemis"] == 2
    assert stats["apollo"] == 1
    assert stats["hestia_solo"] == 1


@pytest.mark.asyncio
async def test_fallback_count(audit_db):
    e1 = RoutingAuditEntry.create("user-1", "req-1", "chat", "artemis", 0.8)
    e1.fallback_triggered = True
    e2 = RoutingAuditEntry.create("user-1", "req-2", "chat", "apollo", 0.9)
    await audit_db.store(e1)
    await audit_db.store(e2)

    results = await audit_db.get_recent(user_id="user-1")
    fallbacks = [r for r in results if r["fallback_triggered"]]
    assert len(fallbacks) == 1
