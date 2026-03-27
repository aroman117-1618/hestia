"""Tests for CredentialWatchAdapter — TDD, stdlib only."""
import pytest

from hestia.sentinel.adapters.credential_watch import CredentialWatchAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WATCHED_PATHS = [
    "/Users/hestia/.coinbase-credentials",
    "/Users/hestia/.cloud_api_key",
]

ALLOWLIST = {
    "coinbase-credentials": ["bot_service", "python3"],
    "cloud_api_key": ["hestia_server"],
}

LSOF_HEADER = "COMMAND   PID   USER   FD   TYPE DEVICE SIZE/OFF NODE NAME"

LSOF_ROGUE = (
    f"{LSOF_HEADER}\n"
    "curl      9999  hestia  txt  REG  disk0s2  4096  123  /Users/hestia/.coinbase-credentials\n"
)

LSOF_ALLOWED = (
    f"{LSOF_HEADER}\n"
    "bot_service 1234 hestia txt REG disk0s2 4096 123 /Users/hestia/.coinbase-credentials\n"
)

LSOF_EMPTY = LSOF_HEADER + "\n"


# ---------------------------------------------------------------------------
# _parse_lsof_output
# ---------------------------------------------------------------------------

class TestParseLsofOutputDetectsAccess:
    def test_parse_lsof_output_detects_access(self):
        adapter = CredentialWatchAdapter(WATCHED_PATHS, ALLOWLIST)
        records = adapter._parse_lsof_output(LSOF_ROGUE)

        assert len(records) == 1
        record = records[0]
        assert record["process"] == "curl"
        assert record["pid"] == "9999"
        assert record["path"] == "/Users/hestia/.coinbase-credentials"
        assert record["credential"] == "coinbase-credentials"
        assert record["allowed"] is False


class TestParseLsofOutputAllowsKnownProcess:
    def test_parse_lsof_output_allows_known_process(self):
        adapter = CredentialWatchAdapter(WATCHED_PATHS, ALLOWLIST)
        records = adapter._parse_lsof_output(LSOF_ALLOWED)

        assert len(records) == 1
        record = records[0]
        assert record["process"] == "bot_service"
        assert record["allowed"] is True


# ---------------------------------------------------------------------------
# poll()
# ---------------------------------------------------------------------------

class TestPollGeneratesCriticalForRogueAccess:
    def test_poll_generates_critical_for_rogue_access(self, monkeypatch):
        adapter = CredentialWatchAdapter(WATCHED_PATHS, ALLOWLIST)
        monkeypatch.setattr(adapter, "_run_lsof", lambda: LSOF_ROGUE)

        events = adapter.poll()

        assert len(events) == 1
        event = events[0]
        assert event["severity"] == "CRITICAL"
        assert event["source"] == CredentialWatchAdapter.SOURCE
        assert "curl" in event["summary"]
        assert event["event_type"] == "credential_access"


class TestPollNoEventsWhenClean:
    def test_poll_no_events_when_clean(self, monkeypatch):
        adapter = CredentialWatchAdapter(WATCHED_PATHS, ALLOWLIST)
        monkeypatch.setattr(adapter, "_run_lsof", lambda: LSOF_EMPTY)

        events = adapter.poll()

        assert events == []
