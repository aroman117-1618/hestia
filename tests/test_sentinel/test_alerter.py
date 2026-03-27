"""Tests for SentinelAlerter — TDD, stdlib only."""
import pytest

from hestia.sentinel.alerter import SentinelAlerter


class TestShouldAlertCriticalAlways:
    def test_should_alert_critical_always(self):
        alerter = SentinelAlerter(
            ntfy_topic="test-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
        )
        assert alerter.should_realtime_alert("CRITICAL") is True


class TestShouldAlertHighAlways:
    def test_should_alert_high_always(self):
        alerter = SentinelAlerter(
            ntfy_topic="test-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
        )
        assert alerter.should_realtime_alert("HIGH") is True


class TestShouldNotAlertMediumRealtime:
    def test_should_not_alert_medium_realtime(self):
        alerter = SentinelAlerter(
            ntfy_topic="test-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
        )
        assert alerter.should_realtime_alert("MEDIUM") is False

    def test_should_not_alert_low_realtime(self):
        alerter = SentinelAlerter(
            ntfy_topic="test-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
        )
        assert alerter.should_realtime_alert("LOW") is False


class TestLearningModeSuppressesNonCritical:
    def test_learning_mode_suppresses_non_critical(self):
        alerter = SentinelAlerter(
            ntfy_topic="test-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
            learning_mode=True,
        )
        assert alerter.should_realtime_alert("CRITICAL") is True
        assert alerter.should_realtime_alert("HIGH") is False
        assert alerter.should_realtime_alert("MEDIUM") is False


class TestFormatNtfyPayload:
    def test_format_ntfy_payload(self):
        alerter = SentinelAlerter(
            ntfy_topic="my-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
        )
        headers, body = alerter.format_ntfy(
            severity="CRITICAL",
            summary="Malicious .pth file detected: evil.pth",
        )
        assert headers["Title"] == "Sentinel CRITICAL"
        assert headers["Priority"] == "urgent"
        assert headers["Tags"] == "rotating_light"
        assert "Malicious .pth file detected: evil.pth" in body

    def test_format_ntfy_high_severity(self):
        alerter = SentinelAlerter(
            ntfy_topic="my-topic",
            heartbeat_url="https://hc-ping.io/fake-uuid",
        )
        headers, body = alerter.format_ntfy(
            severity="HIGH",
            summary="Checksum mismatch",
        )
        assert headers["Title"] == "Sentinel HIGH"
        assert headers["Priority"] == "high"
        assert headers["Tags"] == "warning"
        assert "Checksum mismatch" in body
