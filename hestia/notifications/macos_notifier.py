"""
macOS notification delivery via osascript (AppleScript).
"""

import asyncio

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent

logger = get_logger()


async def send_macos_notification(
    title: str,
    body: str = "",
    subtitle: str = "",
    sound: str = "default",
) -> bool:
    """Send a native macOS notification via osascript.

    Args:
        title: Notification title.
        body: Notification body text.
        subtitle: Optional subtitle line.
        sound: Sound name or empty for silent.

    Returns:
        True if notification was sent successfully.
    """
    safe_title = _escape_applescript(title)
    safe_body = _escape_applescript(body)
    safe_subtitle = _escape_applescript(subtitle)

    script = f'display notification "{safe_body}" with title "{safe_title}"'
    if subtitle:
        script += f' subtitle "{safe_subtitle}"'
    if sound:
        script += f' sound name "{sound}"'

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        if proc.returncode == 0:
            logger.info(
                "macOS notification sent",
                component=LogComponent.NOTIFICATION,
                data={"title": title},
            )
            return True

        logger.warning(
            "osascript notification failed",
            component=LogComponent.NOTIFICATION,
            data={
                "returncode": proc.returncode,
                "stderr": stderr.decode()[:200],
            },
        )
        return False

    except asyncio.TimeoutError:
        logger.warning(
            "osascript notification timed out",
            component=LogComponent.NOTIFICATION,
        )
        return False
    except OSError as e:
        logger.warning(
            "osascript notification error",
            component=LogComponent.NOTIFICATION,
            data={"error": type(e).__name__},
        )
        return False


def _escape_applescript(text: str) -> str:
    """Escape a string for safe embedding in AppleScript double quotes."""
    return text.replace("\\", "\\\\").replace('"', '\\"')
