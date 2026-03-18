"""
macOS idle time detection.

Uses IOKit HIDIdleTime to determine how long since last user input
(keyboard/mouse/trackpad). Used by the notification router to decide
whether to deliver locally or escalate to iPhone.
"""

import asyncio
import re

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent

logger = get_logger()


async def get_idle_seconds() -> float:
    """Get macOS idle time in seconds since last input event.

    Uses ``ioreg -c IOHIDSystem`` to read HIDIdleTime (nanoseconds).
    Returns 0.0 on any failure (assumes active).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ioreg", "-c", "IOHIDSystem",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        output = stdout.decode("utf-8", errors="replace")

        match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', output)
        if match:
            nanoseconds = int(match.group(1))
            return nanoseconds / 1_000_000_000  # ns to seconds

        return 0.0

    except (asyncio.TimeoutError, OSError) as e:
        logger.warning(
            "Idle detection failed, assuming active",
            component=LogComponent.NOTIFICATION,
            data={"error": type(e).__name__},
        )
        return 0.0


async def is_focus_mode_active() -> bool:
    """Check if macOS Focus/Do Not Disturb is active.

    Reads the assertion state from defaults. Returns False on failure
    (assumes not in Focus mode - safer to deliver than suppress).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "defaults", "read",
            "com.apple.controlcenter",
            "NSStatusItem Visible FocusModes",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        output = stdout.decode("utf-8", errors="replace").strip()
        return output == "1"

    except (asyncio.TimeoutError, OSError):
        return False
