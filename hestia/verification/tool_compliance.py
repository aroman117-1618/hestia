"""
Layer 1: Tool Compliance Gate.

Detects responses that claim personal domain data (calendar, health, notes, reminders)
without a corresponding tool call in the current inference result. Zero inference cost —
pure string pattern matching against configurable domain patterns.

Design notes:
- Fail-open: any exception returns no disclaimer
- Conservative patterns: require both a domain keyword AND a possessive/result framing
  to reduce false positives on conversational mentions
- Patterns are loaded from memory.yaml → hallucination_guard.domain_claim_patterns
"""
import re
from typing import List, Optional

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent


_DISCLAIMER = (
    "\n\n⚠ *I wasn't able to verify this from your live data — "
    "please confirm with a direct tool call.*"
)

logger = get_logger()


def _load_patterns() -> List[str]:
    """Load domain claim patterns from memory.yaml config."""
    try:
        import yaml
        import os
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "memory.yaml"
        )
        with open(os.path.normpath(config_path)) as f:
            cfg = yaml.safe_load(f)
        return cfg.get("hallucination_guard", {}).get("domain_claim_patterns", [])
    except Exception:
        # Fallback to hardcoded minimal set if config unavailable
        return [
            r"your next meeting",
            r"you have an? (?:event|appointment|meeting)",
            r"your heart rate",
            r"in your (?:note|notes)",
            r"your reminder",
        ]


# Compile once at module load
_COMPILED_PATTERNS: Optional[List[re.Pattern]] = None


def _get_patterns() -> List[re.Pattern]:
    global _COMPILED_PATTERNS
    if _COMPILED_PATTERNS is None:
        raw = _load_patterns()
        _COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in raw]
    return _COMPILED_PATTERNS


class ToolComplianceChecker:
    """
    Checks whether a response that references personal domain data
    was actually grounded in a tool call.

    Usage:
        checker = ToolComplianceChecker()
        disclaimer = checker.check(response_content, had_tool_calls=bool(tool_calls))
        if disclaimer:
            response_content += disclaimer
    """

    def check(
        self,
        response_content: str,
        had_tool_calls: bool,
    ) -> Optional[str]:
        """
        Returns a disclaimer string if the response appears to claim domain data
        without a corresponding tool call, otherwise None.

        Args:
            response_content: The generated response text.
            had_tool_calls: Whether the inference result included tool calls.

        Returns:
            Disclaimer string to append, or None if clean.
        """
        if not response_content:
            return None

        # If tools were actually called, the response is grounded — no disclaimer needed
        if had_tool_calls:
            return None

        try:
            patterns = _get_patterns()
            for pattern in patterns:
                if pattern.search(response_content):
                    logger.info(
                        f"Tool compliance: domain claim detected without tool call "
                        f"(pattern: {pattern.pattern[:40]})",
                        component=LogComponent.VERIFICATION,
                        data={"pattern": pattern.pattern},
                    )
                    return _DISCLAIMER
        except Exception as e:
            logger.warning(
                f"Tool compliance check failed: {type(e).__name__}",
                component=LogComponent.VERIFICATION,
            )

        return None
