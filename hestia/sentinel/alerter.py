"""
SentinelAlerter — dispatches sentinel alerts via ntfy.sh and healthchecks.io.

Zero-dependency constraint: stdlib only (urllib.request).
"""
import urllib.request
import urllib.error
from typing import Optional


class SentinelAlerter:
    SEVERITY_PRIORITY = {
        "CRITICAL": "urgent",
        "HIGH": "high",
        "MEDIUM": "default",
        "LOW": "low",
    }
    SEVERITY_TAGS = {
        "CRITICAL": "rotating_light",
        "HIGH": "warning",
        "MEDIUM": "information_source",
        "LOW": "mag",
    }

    def __init__(
        self,
        ntfy_topic: str,
        heartbeat_url: str,
        learning_mode: bool = False,
    ) -> None:
        self._ntfy_topic = ntfy_topic
        self._heartbeat_url = heartbeat_url
        self._learning_mode = learning_mode

    def should_realtime_alert(self, severity: str) -> bool:
        """Return True if this severity warrants an immediate push notification.

        Learning mode: only CRITICAL gets real-time push.
        Normal mode: CRITICAL and HIGH get real-time push.
        MEDIUM and LOW always go to daily digest (no real-time).
        """
        if self._learning_mode:
            return severity == "CRITICAL"
        return severity in ("CRITICAL", "HIGH")

    def format_ntfy(self, severity: str, summary: str) -> tuple:
        """Build ntfy.sh headers and body for the given severity and summary.

        Returns:
            (headers_dict, body_string)
        """
        headers = {
            "Title": f"Sentinel {severity}",
            "Priority": self.SEVERITY_PRIORITY.get(severity, "default"),
            "Tags": self.SEVERITY_TAGS.get(severity, "bell"),
        }
        body = summary
        return headers, body

    def send_ntfy(self, severity: str, summary: str) -> bool:
        """POST alert to ntfy.sh/{topic}.

        Returns True on success, False on any failure (never raises).
        """
        headers, body = self.format_ntfy(severity, summary)
        url = f"https://ntfy.sh/{self._ntfy_topic}"
        try:
            data = body.encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            for key, value in headers.items():
                req.add_header(key, value)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def send_heartbeat(self) -> bool:
        """GET the healthchecks.io heartbeat URL.

        Returns True on success, False on any failure (never raises).
        """
        try:
            with urllib.request.urlopen(self._heartbeat_url, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def alert(self, event: dict) -> None:
        """Dispatch an alert for the given sentinel event.

        Sends a real-time ntfy push if the severity warrants it.
        MEDIUM/LOW events are silently skipped (destined for daily digest).
        """
        severity: str = event.get("severity", "LOW")
        summary: str = event.get("summary", "Sentinel event detected")
        if self.should_realtime_alert(severity):
            self.send_ntfy(severity, summary)
