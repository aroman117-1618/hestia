"""
Tests for hestia.outcomes -- OutcomeDatabase, OutcomeManager, and API routes.

Covers:
- TestOutcomeDatabase: SQLite CRUD, user-scoped queries, filtering, stats, cleanup
- TestOutcomeManager: track_response, record_feedback, detect_implicit_signal
- TestOutcomeRoutes: API endpoints with mocked manager
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch as mock_patch

import pytest

from hestia.outcomes.models import (
    OutcomeRecord,
    OutcomeFeedback,
    ImplicitSignal,
)
from hestia.outcomes.database import OutcomeDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    id: str = "outcome-1",
    user_id: str = "user-1",
    device_id: str = "device-1",
    session_id: str = "session-1",
    message_id: str = "msg-1",
    response_content: str = "Hello there",
    response_type: str = "text",
    duration_ms: int = 150,
    feedback: Optional[str] = None,
    feedback_note: Optional[str] = None,
    implicit_signal: Optional[str] = None,
    elapsed_to_next_ms: Optional[int] = None,
    timestamp: Optional[datetime] = None,
    metadata: Optional[dict] = None,
) -> OutcomeRecord:
    """Helper to create an OutcomeRecord with sensible defaults."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if metadata is None:
        metadata = {}
    return OutcomeRecord(
        id=id,
        user_id=user_id,
        device_id=device_id,
        session_id=session_id,
        message_id=message_id,
        response_content=response_content,
        response_type=response_type,
        duration_ms=duration_ms,
        feedback=feedback,
        feedback_note=feedback_note,
        implicit_signal=implicit_signal,
        elapsed_to_next_ms=elapsed_to_next_ms,
        timestamp=timestamp,
        metadata=metadata,
    )


# ===========================================================================
# TestOutcomeDatabase
# ===========================================================================

class TestOutcomeDatabase:
    """Tests for OutcomeDatabase SQLite operations."""

    @pytest.fixture
    async def db(self, tmp_path: Path):
        """Create an OutcomeDatabase for testing."""
        db_path = tmp_path / "test_outcomes.db"
        database = OutcomeDatabase(db_path=db_path)
        await database.initialize()
        yield database
        await database.close()

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, db: OutcomeDatabase):
        """Stored outcomes should be retrievable."""
        record = _make_record(id="out-1", user_id="user-1")
        result_id = await db.store_outcome(record)
        assert result_id == "out-1"

        outcomes = await db.get_outcomes(user_id="user-1")
        assert len(outcomes) == 1
        assert outcomes[0]["id"] == "out-1"
        assert outcomes[0]["response_type"] == "text"
        assert outcomes[0]["duration_ms"] == 150

    @pytest.mark.asyncio
    async def test_user_scoped_queries(self, db: OutcomeDatabase):
        """Two users should see only their own outcomes."""
        await db.store_outcome(_make_record(id="out-1", user_id="user-a"))
        await db.store_outcome(_make_record(id="out-2", user_id="user-b"))
        await db.store_outcome(_make_record(id="out-3", user_id="user-a"))

        results_a = await db.get_outcomes(user_id="user-a")
        assert len(results_a) == 2
        ids_a = {r["id"] for r in results_a}
        assert ids_a == {"out-1", "out-3"}

        results_b = await db.get_outcomes(user_id="user-b")
        assert len(results_b) == 1
        assert results_b[0]["id"] == "out-2"

    @pytest.mark.asyncio
    async def test_filter_by_session(self, db: OutcomeDatabase):
        """Filtering by session_id should return only matching outcomes."""
        await db.store_outcome(_make_record(id="out-1", session_id="sess-a"))
        await db.store_outcome(_make_record(id="out-2", session_id="sess-b"))
        await db.store_outcome(_make_record(id="out-3", session_id="sess-a"))

        results = await db.get_outcomes(user_id="user-1", session_id="sess-a")
        assert len(results) == 2
        ids = {r["id"] for r in results}
        assert ids == {"out-1", "out-3"}

    @pytest.mark.asyncio
    async def test_filter_by_days(self, db: OutcomeDatabase):
        """Filtering by days should exclude old records."""
        now = datetime.now(timezone.utc)
        await db.store_outcome(
            _make_record(id="out-recent", timestamp=now)
        )
        await db.store_outcome(
            _make_record(id="out-old", timestamp=now - timedelta(days=10))
        )

        results = await db.get_outcomes(user_id="user-1", days=5)
        assert len(results) == 1
        assert results[0]["id"] == "out-recent"

    @pytest.mark.asyncio
    async def test_update_feedback(self, db: OutcomeDatabase):
        """update_feedback should set feedback and feedback_note."""
        await db.store_outcome(_make_record(id="out-1"))

        success = await db.update_feedback(
            "out-1", "user-1", "positive", "Great answer!"
        )
        assert success is True

        outcome = await db.get_outcome("out-1", "user-1")
        assert outcome is not None
        assert outcome["feedback"] == "positive"
        assert outcome["feedback_note"] == "Great answer!"

    @pytest.mark.asyncio
    async def test_update_feedback_nonexistent(self, db: OutcomeDatabase):
        """update_feedback for nonexistent record should return False."""
        success = await db.update_feedback("nonexistent", "user-1", "positive")
        assert success is False

    @pytest.mark.asyncio
    async def test_update_implicit_signal(self, db: OutcomeDatabase):
        """update_implicit_signal should set signal and elapsed_ms."""
        await db.store_outcome(_make_record(id="out-1"))

        success = await db.update_implicit_signal("out-1", "accepted", 60000)
        assert success is True

        outcome = await db.get_outcome("out-1", "user-1")
        assert outcome["implicit_signal"] == "accepted"
        assert outcome["elapsed_to_next_ms"] == 60000

    @pytest.mark.asyncio
    async def test_get_stats(self, db: OutcomeDatabase):
        """get_stats should return correct counts and avg duration."""
        now = datetime.now(timezone.utc)

        # 3 outcomes with different feedback
        await db.store_outcome(
            _make_record(id="out-1", feedback="positive", duration_ms=100, timestamp=now)
        )
        await db.store_outcome(
            _make_record(id="out-2", feedback="negative", duration_ms=200, timestamp=now)
        )
        await db.store_outcome(
            _make_record(id="out-3", feedback="correction", duration_ms=300, timestamp=now)
        )
        await db.store_outcome(
            _make_record(id="out-4", duration_ms=400, timestamp=now)
        )

        stats = await db.get_stats("user-1", days=7)
        assert stats["total"] == 4
        assert stats["positive_count"] == 1
        assert stats["negative_count"] == 1
        assert stats["correction_count"] == 1
        assert stats["avg_duration_ms"] == 250  # (100+200+300+400)/4

    @pytest.mark.asyncio
    async def test_get_latest_for_session(self, db: OutcomeDatabase):
        """get_latest_for_session should return the most recent unsignaled outcome."""
        now = datetime.now(timezone.utc)

        # Older outcome (already signaled)
        record_old = _make_record(
            id="out-old",
            session_id="sess-1",
            implicit_signal="accepted",
            timestamp=now - timedelta(minutes=5),
        )
        await db.store_outcome(record_old)

        # Newer outcome (not signaled yet)
        record_new = _make_record(
            id="out-new",
            session_id="sess-1",
            timestamp=now,
        )
        await db.store_outcome(record_new)

        latest = await db.get_latest_for_session("sess-1", "user-1")
        assert latest is not None
        assert latest["id"] == "out-new"

    @pytest.mark.asyncio
    async def test_get_latest_for_session_none(self, db: OutcomeDatabase):
        """get_latest_for_session should return None when all outcomes are signaled."""
        await db.store_outcome(
            _make_record(id="out-1", session_id="sess-1", implicit_signal="accepted")
        )

        latest = await db.get_latest_for_session("sess-1", "user-1")
        assert latest is None

    @pytest.mark.asyncio
    async def test_cleanup_old(self, db: OutcomeDatabase):
        """cleanup_old should remove outcomes older than retention period."""
        now = datetime.now(timezone.utc)

        await db.store_outcome(
            _make_record(id="out-recent", timestamp=now)
        )
        await db.store_outcome(
            _make_record(id="out-old", timestamp=now - timedelta(days=100))
        )

        deleted = await db.cleanup_old(retention_days=90)
        assert deleted == 1

        outcomes = await db.get_outcomes(user_id="user-1")
        assert len(outcomes) == 1
        assert outcomes[0]["id"] == "out-recent"

    @pytest.mark.asyncio
    async def test_get_outcome_not_found(self, db: OutcomeDatabase):
        """get_outcome should return None for nonexistent records."""
        result = await db.get_outcome("nonexistent", "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_metadata_roundtrip(self, db: OutcomeDatabase):
        """Metadata dict should survive store/retrieve."""
        record = _make_record(id="out-meta", metadata={"model": "qwen", "tokens": 42})
        await db.store_outcome(record)

        result = await db.get_outcome("out-meta", "user-1")
        assert result is not None
        assert result["metadata"]["model"] == "qwen"
        assert result["metadata"]["tokens"] == 42


# ===========================================================================
# TestOutcomeManager
# ===========================================================================

class TestOutcomeManager:
    """Tests for OutcomeManager with real database."""

    @pytest.fixture
    async def db(self, tmp_path: Path):
        """Create a test OutcomeDatabase."""
        db_path = tmp_path / "test_outcomes_mgr.db"
        database = OutcomeDatabase(db_path=db_path)
        await database.initialize()
        yield database
        await database.close()

    @pytest.fixture
    async def manager(self, db):
        """Create an OutcomeManager with test database."""
        from hestia.outcomes.manager import OutcomeManager
        mgr = OutcomeManager(database=db)
        await mgr.initialize()
        yield mgr
        await mgr.close()

    @pytest.mark.asyncio
    async def test_track_response_creates_outcome(self, manager):
        """track_response should create an outcome in the database."""
        outcome_id = await manager.track_response(
            user_id="user-1",
            device_id="device-1",
            session_id="sess-1",
            message_id="msg-1",
            response_content="Hello!",
            response_type="text",
            duration_ms=120,
            metadata={"model": "qwen"},
        )

        assert outcome_id is not None

        outcome = await manager.get_outcome(outcome_id, "user-1")
        assert outcome is not None
        assert outcome["response_type"] == "text"
        assert outcome["duration_ms"] == 120
        assert outcome["metadata"]["model"] == "qwen"

    @pytest.mark.asyncio
    async def test_record_feedback_valid(self, manager):
        """record_feedback with valid value should update the outcome."""
        outcome_id = await manager.track_response(
            user_id="user-1",
            device_id="device-1",
            session_id="sess-1",
            message_id="msg-1",
            response_content="Hi",
            response_type="text",
            duration_ms=100,
        )

        success = await manager.record_feedback(
            outcome_id=outcome_id,
            user_id="user-1",
            feedback="positive",
            note="Very helpful",
        )
        assert success is True

        outcome = await manager.get_outcome(outcome_id, "user-1")
        assert outcome["feedback"] == "positive"
        assert outcome["feedback_note"] == "Very helpful"

    @pytest.mark.asyncio
    async def test_record_feedback_invalid(self, manager):
        """record_feedback with invalid value should return False."""
        outcome_id = await manager.track_response(
            user_id="user-1",
            device_id="device-1",
            session_id="sess-1",
            message_id="msg-1",
            response_content="Hi",
            response_type="text",
            duration_ms=100,
        )

        success = await manager.record_feedback(
            outcome_id=outcome_id,
            user_id="user-1",
            feedback="invalid_value",
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_detect_implicit_signal_quick_followup(self, manager):
        """Quick follow-up (<30s) should detect 'quick_followup' signal."""
        # Create an outcome with a recent timestamp
        outcome_id = await manager.track_response(
            user_id="user-1",
            device_id="device-1",
            session_id="sess-1",
            message_id="msg-1",
            response_content="Answer",
            response_type="text",
            duration_ms=100,
        )

        # Detect signal immediately (elapsed < 30s)
        signal = await manager.detect_implicit_signal(
            session_id="sess-1",
            user_id="user-1",
            new_message_content="follow up",
        )
        assert signal == "quick_followup"

        # Verify the outcome was updated
        outcome = await manager.get_outcome(outcome_id, "user-1")
        assert outcome["implicit_signal"] == "quick_followup"
        assert outcome["elapsed_to_next_ms"] is not None
        assert outcome["elapsed_to_next_ms"] < 30000

    @pytest.mark.asyncio
    async def test_detect_implicit_signal_long_gap(self, manager, db):
        """Long gap (>300s) should detect 'long_gap' signal."""
        # Create an outcome with old timestamp (6 minutes ago)
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=360)
        record = _make_record(
            id="out-old",
            user_id="user-1",
            session_id="sess-1",
            timestamp=old_ts,
        )
        await db.store_outcome(record)

        signal = await manager.detect_implicit_signal(
            session_id="sess-1",
            user_id="user-1",
            new_message_content="I'm back",
        )
        assert signal == "long_gap"

    @pytest.mark.asyncio
    async def test_detect_implicit_signal_accepted(self, manager, db):
        """Medium gap (30-300s) should detect 'accepted' signal."""
        # Create an outcome 2 minutes ago
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=120)
        record = _make_record(
            id="out-mid",
            user_id="user-1",
            session_id="sess-1",
            timestamp=old_ts,
        )
        await db.store_outcome(record)

        signal = await manager.detect_implicit_signal(
            session_id="sess-1",
            user_id="user-1",
            new_message_content="new topic",
        )
        assert signal == "accepted"

    @pytest.mark.asyncio
    async def test_detect_implicit_signal_no_pending(self, manager):
        """No pending outcome should return None."""
        signal = await manager.detect_implicit_signal(
            session_id="sess-nonexistent",
            user_id="user-1",
            new_message_content="hello",
        )
        assert signal is None

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """get_stats should return correct aggregated counts."""
        # Create outcomes with different feedback
        for i, fb in enumerate(["positive", "negative", "correction", None]):
            oid = await manager.track_response(
                user_id="user-1",
                device_id="device-1",
                session_id="sess-1",
                message_id=f"msg-{i}",
                response_content=f"Response {i}",
                response_type="text",
                duration_ms=100 * (i + 1),
            )
            if fb:
                await manager.record_feedback(oid, "user-1", fb)

        stats = await manager.get_stats("user-1", days=7)
        assert stats["total"] == 4
        assert stats["positive_count"] == 1
        assert stats["negative_count"] == 1
        assert stats["correction_count"] == 1
        assert stats["avg_duration_ms"] == 250

    @pytest.mark.asyncio
    async def test_get_outcomes_with_pagination(self, manager):
        """get_outcomes should support limit and offset."""
        for i in range(5):
            await manager.track_response(
                user_id="user-1",
                device_id="device-1",
                session_id="sess-1",
                message_id=f"msg-{i}",
                response_content=f"Response {i}",
                response_type="text",
                duration_ms=100,
            )

        # First page
        page1 = await manager.get_outcomes("user-1", limit=2, offset=0)
        assert len(page1) == 2

        # Second page
        page2 = await manager.get_outcomes("user-1", limit=2, offset=2)
        assert len(page2) == 2

        # Third page (partial)
        page3 = await manager.get_outcomes("user-1", limit=2, offset=4)
        assert len(page3) == 1

        # No overlap
        all_ids = {o["id"] for o in page1 + page2 + page3}
        assert len(all_ids) == 5


# ===========================================================================
# TestOutcomeRoutes
# ===========================================================================

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hestia.api.routes.outcomes import router as outcomes_router_instance


class TestOutcomeRoutes:
    """Tests for /v1/outcomes API routes using mocked OutcomeManager."""

    @pytest.fixture
    def mock_mgr(self):
        """Create a mock OutcomeManager."""
        return AsyncMock()

    @pytest.fixture
    def client(self, mock_mgr):
        """Build a TestClient with the outcomes router and mocked manager."""
        app = FastAPI()
        app.include_router(outcomes_router_instance)

        from hestia.api.middleware.auth import get_device_token
        app.dependency_overrides[get_device_token] = lambda: "test-device-id"

        with mock_patch(
            "hestia.api.routes.outcomes.get_outcome_manager",
            return_value=mock_mgr,
        ):
            yield TestClient(app)

    # ---- 1. List outcomes ----

    def test_list_outcomes_success(self, mock_mgr, client):
        """GET /v1/outcomes should return outcomes list."""
        mock_mgr.get_outcomes.return_value = [
            {
                "id": "out-1",
                "session_id": "sess-1",
                "message_id": "msg-1",
                "response_type": "text",
                "duration_ms": 150,
                "feedback": None,
                "feedback_note": None,
                "implicit_signal": None,
                "elapsed_to_next_ms": None,
                "timestamp": "2026-03-04T10:00:00+00:00",
                "metadata": {},
            },
        ]

        resp = client.get("/v1/outcomes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert len(body["outcomes"]) == 1
        assert body["outcomes"][0]["id"] == "out-1"

    # ---- 2. Get stats ----

    def test_get_stats_success(self, mock_mgr, client):
        """GET /v1/outcomes/stats should return aggregated stats."""
        mock_mgr.get_stats.return_value = {
            "total": 10,
            "positive_count": 5,
            "negative_count": 2,
            "correction_count": 1,
            "avg_duration_ms": 200,
        }

        resp = client.get("/v1/outcomes/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert body["positive_count"] == 5
        assert body["avg_duration_ms"] == 200

    # ---- 3. Get outcome detail ----

    def test_get_outcome_success(self, mock_mgr, client):
        """GET /v1/outcomes/{id} should return the outcome."""
        mock_mgr.get_outcome.return_value = {
            "id": "out-1",
            "session_id": "sess-1",
            "message_id": "msg-1",
            "response_type": "text",
            "duration_ms": 150,
            "feedback": "positive",
            "feedback_note": "Good!",
            "implicit_signal": None,
            "elapsed_to_next_ms": None,
            "timestamp": "2026-03-04T10:00:00+00:00",
            "metadata": {"model": "qwen"},
        }

        resp = client.get("/v1/outcomes/out-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "out-1"
        assert body["feedback"] == "positive"
        assert body["metadata"]["model"] == "qwen"

    def test_get_outcome_not_found(self, mock_mgr, client):
        """GET /v1/outcomes/{id} for nonexistent outcome should return 404."""
        mock_mgr.get_outcome.return_value = None

        resp = client.get("/v1/outcomes/nonexistent")
        assert resp.status_code == 404

    # ---- 4. Submit feedback ----

    def test_submit_feedback_success(self, mock_mgr, client):
        """POST /v1/outcomes/{id}/feedback should update feedback."""
        mock_mgr.record_feedback.return_value = True
        mock_mgr.get_outcome.return_value = {
            "id": "out-1",
            "session_id": "sess-1",
            "message_id": "msg-1",
            "response_type": "text",
            "duration_ms": 150,
            "feedback": "positive",
            "feedback_note": "Helpful",
            "implicit_signal": None,
            "elapsed_to_next_ms": None,
            "timestamp": "2026-03-04T10:00:00+00:00",
            "metadata": {},
        }

        resp = client.post(
            "/v1/outcomes/out-1/feedback",
            json={"feedback": "positive", "note": "Helpful"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["feedback"] == "positive"

    def test_submit_feedback_invalid(self, mock_mgr, client):
        """POST /v1/outcomes/{id}/feedback with invalid feedback should return 400."""
        resp = client.post(
            "/v1/outcomes/out-1/feedback",
            json={"feedback": "invalid_value"},
        )
        assert resp.status_code == 400

    # ---- 5. Track response ----

    def test_track_response_success(self, mock_mgr, client):
        """POST /v1/outcomes/track should create an outcome."""
        mock_mgr.track_response.return_value = "out-new"
        mock_mgr.get_outcome.return_value = {
            "id": "out-new",
            "session_id": "sess-1",
            "message_id": "msg-1",
            "response_type": "text",
            "duration_ms": 200,
            "feedback": None,
            "feedback_note": None,
            "implicit_signal": None,
            "elapsed_to_next_ms": None,
            "timestamp": "2026-03-04T10:00:00+00:00",
            "metadata": {},
        }

        resp = client.post(
            "/v1/outcomes/track",
            json={
                "session_id": "sess-1",
                "message_id": "msg-1",
                "response_content": "Hello!",
                "response_type": "text",
                "duration_ms": 200,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "out-new"
        assert body["duration_ms"] == 200

    # ---- 6. Feedback on missing outcome ----

    def test_submit_feedback_not_found(self, mock_mgr, client):
        """POST feedback on nonexistent outcome should return 404."""
        mock_mgr.record_feedback.return_value = False

        resp = client.post(
            "/v1/outcomes/nonexistent/feedback",
            json={"feedback": "positive"},
        )
        assert resp.status_code == 404
