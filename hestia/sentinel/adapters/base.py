"""BaseAdapter — abstract polling interface for Sentinel adapters.

Stdlib only. No hestia.* imports outside hestia/sentinel/.
"""
import uuid
from typing import Optional


class BaseAdapter:
    """Base class for all Sentinel adapters."""

    def poll(self) -> list[dict]:
        raise NotImplementedError

    @staticmethod
    def make_event(
        source: str,
        severity: str,
        event_type: str,
        summary: str,
        details: Optional[dict] = None,
        action_taken: Optional[str] = None,
    ) -> dict:
        """Return a Sentinel event dict with a fresh uuid4 hex event_id."""
        return {
            "event_id": uuid.uuid4().hex,
            "source": source,
            "severity": severity,
            "event_type": event_type,
            "summary": summary,
            "details": details if details is not None else {},
            "action_taken": action_taken,
        }
