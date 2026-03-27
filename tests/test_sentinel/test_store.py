"""Tests for the Sentinel append-only SQLite event store."""
import sqlite3
import tempfile
import os
import pytest

from hestia.sentinel.store import SentinelStore


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "sentinel_test.db")


@pytest.fixture
def store(tmp_db):
    """Provide an initialized SentinelStore."""
    s = SentinelStore(tmp_db)
    s.initialize()
    return s


def test_store_creates_db_and_tables(tmp_db):
    """initialize() must create the events table with the correct schema."""
    s = SentinelStore(tmp_db)
    s.initialize()

    conn = sqlite3.connect(tmp_db)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "events table was not created"
    assert row[0] == "events"


def test_store_insert_event(store):
    """insert_event stores a record and get_recent_events returns all fields."""
    store.insert_event(
        event_id="evt-001",
        source="pip-audit",
        severity="HIGH",
        event_type="dependency_vulnerability",
        summary="requests 2.28 has CVE-2023-XXXX",
        details='{"cve": "CVE-2023-XXXX", "package": "requests"}',
        action_taken="quarantined",
    )

    events = store.get_recent_events(limit=10)
    assert len(events) == 1

    evt = events[0]
    assert evt["event_id"] == "evt-001"
    assert evt["source"] == "pip-audit"
    assert evt["severity"] == "HIGH"
    assert evt["event_type"] == "dependency_vulnerability"
    assert evt["summary"] == "requests 2.28 has CVE-2023-XXXX"
    assert evt["details"] == '{"cve": "CVE-2023-XXXX", "package": "requests"}'
    assert evt["action_taken"] == "quarantined"
    assert evt["acknowledged"] == 0
    # timestamp must be a non-empty ISO 8601 string
    assert isinstance(evt["timestamp"], str) and len(evt["timestamp"]) > 0


def test_store_insert_event_defaults(store):
    """insert_event works with only required arguments; details defaults to '{}'."""
    store.insert_event(
        event_id="evt-002",
        source="sentinel",
        severity="LOW",
        event_type="scan_complete",
        summary="Routine scan finished with no findings",
    )

    events = store.get_recent_events()
    assert len(events) == 1
    evt = events[0]
    assert evt["details"] == "{}"
    assert evt["action_taken"] is None
    assert evt["acknowledged"] == 0


def test_store_blocks_delete(store):
    """DELETE on events must raise sqlite3.IntegrityError (trigger ABORT)."""
    store.insert_event(
        event_id="evt-del",
        source="test",
        severity="MEDIUM",
        event_type="test_event",
        summary="Should not be deletable",
    )

    conn = sqlite3.connect(store.db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM events WHERE event_id = 'evt-del'")
        conn.commit()
    conn.close()


def test_store_allows_acknowledge(store):
    """acknowledge_event sets acknowledged=1 without triggering the UPDATE block."""
    store.insert_event(
        event_id="evt-ack",
        source="sentinel",
        severity="CRITICAL",
        event_type="supply_chain_compromise",
        summary="Tampered package detected",
    )

    store.acknowledge_event("evt-ack")

    events = store.get_recent_events()
    assert events[0]["acknowledged"] == 1


def test_store_get_unacknowledged(store):
    """get_unacknowledged_events returns only events where acknowledged=0."""
    store.insert_event(
        event_id="evt-unacked-1",
        source="sentinel",
        severity="HIGH",
        event_type="type_a",
        summary="Unacked event 1",
    )
    store.insert_event(
        event_id="evt-unacked-2",
        source="sentinel",
        severity="LOW",
        event_type="type_b",
        summary="Unacked event 2",
    )
    store.insert_event(
        event_id="evt-acked",
        source="sentinel",
        severity="MEDIUM",
        event_type="type_c",
        summary="Acked event",
    )
    store.acknowledge_event("evt-acked")

    unacked = store.get_unacknowledged_events()
    ids = {e["event_id"] for e in unacked}

    assert "evt-unacked-1" in ids
    assert "evt-unacked-2" in ids
    assert "evt-acked" not in ids


def test_store_get_events_by_severity(store):
    """get_events_by_severity filters by severity correctly."""
    store.insert_event("e1", "s", "CRITICAL", "t", "Critical event")
    store.insert_event("e2", "s", "HIGH", "t", "High event")
    store.insert_event("e3", "s", "CRITICAL", "t", "Another critical")

    criticals = store.get_events_by_severity("CRITICAL")
    assert len(criticals) == 2
    assert all(e["severity"] == "CRITICAL" for e in criticals)

    highs = store.get_events_by_severity("HIGH")
    assert len(highs) == 1
    assert highs[0]["event_id"] == "e2"


def test_store_blocks_non_acknowledge_update(store):
    """UPDATE on columns other than acknowledged must be blocked by trigger."""
    store.insert_event(
        event_id="evt-upd",
        source="sentinel",
        severity="HIGH",
        event_type="test",
        summary="Original summary",
    )

    conn = sqlite3.connect(store.db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE events SET summary = 'Tampered' WHERE event_id = 'evt-upd'"
        )
        conn.commit()
    conn.close()


def test_store_rejects_invalid_severity(store):
    """insert_event with an invalid severity must raise sqlite3.IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_event(
            event_id="evt-bad",
            source="sentinel",
            severity="INVALID",
            event_type="test",
            summary="Bad severity",
        )


def test_store_get_recent_events_ordering(store):
    """get_recent_events returns events ordered by timestamp DESC."""
    import time
    store.insert_event("e-first", "s", "LOW", "t", "First inserted")
    time.sleep(0.01)  # ensure distinct timestamps
    store.insert_event("e-second", "s", "LOW", "t", "Second inserted")

    events = store.get_recent_events()
    assert events[0]["event_id"] == "e-second"
    assert events[1]["event_id"] == "e-first"
