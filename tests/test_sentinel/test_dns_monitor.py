"""Tests for DNSMonitorAdapter — TDD, stdlib only."""
import time

from hestia.sentinel.adapters.dns_monitor import DNSMonitorAdapter


SAMPLE_LOG_LINES = [
    "2026-03-27 10:00:01.123 mDNSResponder[123:456] q=example.com. IN",
    "2026-03-27 10:00:01.456 mDNSResponder[123:456] q=api.github.com. IN",
    "2026-03-27 10:00:02.000 mDNSResponder[123:456] q=evil-tracker.io. IN",
    "2026-03-27 10:00:02.100 mDNSResponder[123:456] q=localhost. IN",  # no dot → filtered
    "2026-03-27 10:00:02.200 mDNSResponder[123:456] NOT_A_QUERY line",  # no match
    "2026-03-27 10:00:02.300 mDNSResponder[123:456] q=UPPER.Example.COM. IN",  # normalised
]


class TestExtractDomains:
    def test_extract_domains(self):
        adapter = DNSMonitorAdapter.__new__(DNSMonitorAdapter)
        domains = adapter._extract_domains(SAMPLE_LOG_LINES)

        assert "example.com" in domains
        assert "api.github.com" in domains
        assert "evil-tracker.io" in domains
        assert "upper.example.com" in domains  # lowercased
        # Entries without a dot should be excluded
        assert "localhost" not in domains
        # Lines without q= pattern should not produce a domain
        assert "" not in domains


class TestClassifyUnknownDomain:
    def test_classify_unknown_domain_generates_low_event(self):
        adapter = DNSMonitorAdapter.__new__(DNSMonitorAdapter)
        adapter._is_domain_allowed = lambda domain: False
        adapter._recent_unknowns = []

        events = adapter._classify_domains(["evil-tracker.io"])

        low_events = [e for e in events if e["severity"] == "LOW"]
        assert len(low_events) == 1
        assert "evil-tracker.io" in low_events[0]["summary"]
        assert low_events[0]["event_type"] == "dns_unknown_domain"
        assert low_events[0]["event_id"] is not None
        assert len(low_events[0]["event_id"]) == 32  # uuid4 hex

    def test_classify_allowed_domain_generates_no_event(self):
        adapter = DNSMonitorAdapter.__new__(DNSMonitorAdapter)
        adapter._is_domain_allowed = lambda domain: True
        adapter._recent_unknowns = []

        events = adapter._classify_domains(["example.com"])

        assert events == []


class TestClassifyBurstGeneratesHigh:
    def test_burst_generates_high_event(self):
        """Pre-populate with 2 recent unknowns, add 1 more → should emit LOW + HIGH."""
        adapter = DNSMonitorAdapter.__new__(DNSMonitorAdapter)
        adapter._is_domain_allowed = lambda domain: False
        now = time.time()
        adapter._recent_unknowns = [
            (now - 10, "bad-domain-1.io"),
            (now - 5, "bad-domain-2.io"),
        ]

        events = adapter._classify_domains(["bad-domain-3.io"])

        severities = [e["severity"] for e in events]
        assert "LOW" in severities
        assert "HIGH" in severities

        high_events = [e for e in events if e["severity"] == "HIGH"]
        assert len(high_events) == 1
        assert high_events[0]["event_type"] == "dns_burst"

    def test_burst_not_triggered_below_threshold(self):
        """Only 1 pre-existing unknown + 1 new = 2 total, below threshold of 3."""
        adapter = DNSMonitorAdapter.__new__(DNSMonitorAdapter)
        adapter._is_domain_allowed = lambda domain: False
        now = time.time()
        adapter._recent_unknowns = [(now - 5, "bad-domain-1.io")]

        events = adapter._classify_domains(["bad-domain-2.io"])

        severities = [e["severity"] for e in events]
        assert "LOW" in severities
        assert "HIGH" not in severities

    def test_burst_ignores_old_entries(self):
        """Entries older than BURST_WINDOW_SECONDS should not count toward burst."""
        adapter = DNSMonitorAdapter.__new__(DNSMonitorAdapter)
        adapter._is_domain_allowed = lambda domain: False
        now = time.time()
        # Two entries well outside the 60-second window
        adapter._recent_unknowns = [
            (now - 120, "old-bad-1.io"),
            (now - 90, "old-bad-2.io"),
        ]

        events = adapter._classify_domains(["new-bad.io"])

        severities = [e["severity"] for e in events]
        assert "LOW" in severities
        assert "HIGH" not in severities
