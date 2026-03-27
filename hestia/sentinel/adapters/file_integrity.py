"""FileIntegrityAdapter — detects new or modified .pth files via BaselineManager.

Stdlib only. No hestia.* imports outside hestia/sentinel/.
"""
import os

from hestia.sentinel.adapters.base import BaseAdapter
from hestia.sentinel.baseline import BaselineManager

_SOURCE = "file_integrity"
_EVENT_TYPE = "pth_tampering"


class FileIntegrityAdapter(BaseAdapter):
    """Polls for .pth file changes relative to a stored baseline."""

    def __init__(self, site_packages_path: str, baseline_manager: BaselineManager) -> None:
        self._site_packages_path = site_packages_path
        self._baseline = baseline_manager

    def poll(self) -> list[dict]:
        """Return CRITICAL events for any new or modified .pth files."""
        changes = self._baseline.diff(self._site_packages_path)
        events: list[dict] = []

        for change in changes:
            filename = os.path.basename(change["path"])
            change_type = change["type"]

            if change_type == "new_pth":
                summary = f"New .pth file detected: {filename}"
            else:
                summary = f"Modified .pth file detected: {filename}"

            event = self.make_event(
                source=_SOURCE,
                severity="CRITICAL",
                event_type=_EVENT_TYPE,
                summary=summary,
                details={
                    "change_type": change_type,
                    "path": change["path"],
                    "hash": change["hash"],
                },
            )
            events.append(event)

        return events
