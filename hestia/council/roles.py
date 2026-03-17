"""
Council roles for specialized LLM calls.

Each role has a system_prompt property and parse_response() method.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from hestia.logging import get_logger, LogComponent

from .models import (
    IntentType,
    IntentClassification,
    ToolExtraction,
    ValidationReport,
)


class CouncilRole(ABC):
    """Base class for council roles."""

    def __init__(self) -> None:
        self.logger = get_logger()

    @property
    def name(self) -> str:
        """Role name for logging and tracking."""
        return self.__class__.__name__.lower()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for this role's LLM call."""

    @abstractmethod
    def parse_response(self, content: str) -> Any:
        """Parse LLM response into role-specific data structure."""


class Coordinator(CouncilRole):
    """
    Intent classification role.

    Runs on SLM when cloud disabled, cloud LLM when enabled.
    Returns IntentClassification with primary intent and confidence.
    """

    @property
    def system_prompt(self) -> str:
        from .prompts import COORDINATOR_PROMPT
        return COORDINATOR_PROMPT

    def parse_response(self, content: str) -> IntentClassification:
        """Parse JSON intent classification from LLM response."""
        try:
            # Strip markdown code fences if present
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)

            primary = IntentType.from_string(data.get("primary_intent", "unclear"))
            confidence = float(data.get("confidence", 0.5))

            secondary = []
            for intent_str in data.get("secondary_intents", []):
                intent = IntentType.from_string(intent_str)
                if intent != IntentType.UNCLEAR:
                    secondary.append(intent)

            return IntentClassification.create(
                primary_intent=primary,
                confidence=confidence,
                secondary_intents=secondary,
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            self.logger.warning(
                f"Coordinator parse failed: {type(e).__name__}",
                component=LogComponent.COUNCIL,
                data={"content_preview": content[:200]},
            )
            return IntentClassification.create(
                primary_intent=IntentType.UNCLEAR,
                confidence=0.0,
                reasoning=f"Parse error: {type(e).__name__}",
            )


class Analyzer(CouncilRole):
    """
    Tool call extraction role.

    Cloud-only enhancement. Parses tool calls from LLM responses
    with higher accuracy than regex.
    """

    @property
    def system_prompt(self) -> str:
        from .prompts import ANALYZER_PROMPT
        return ANALYZER_PROMPT

    def parse_response(self, content: str) -> ToolExtraction:
        """Parse JSON tool extraction from LLM response."""
        try:
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)

            tool_calls = data.get("tool_calls", [])
            # Validate each tool call has required fields
            valid_calls = []
            for tc in tool_calls:
                if isinstance(tc, dict) and "name" in tc:
                    valid_calls.append({
                        "name": tc["name"],
                        "arguments": tc.get("arguments", {}),
                    })

            confidence = float(data.get("confidence", 1.0))

            return ToolExtraction.create(
                tool_calls=valid_calls,
                confidence=confidence,
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            self.logger.warning(
                f"Analyzer parse failed: {type(e).__name__}",
                component=LogComponent.COUNCIL,
            )
            return ToolExtraction.create(
                tool_calls=[],
                confidence=0.0,
                reasoning=f"Parse error: {type(e).__name__}",
            )


class Validator(CouncilRole):
    """
    Response quality and safety validation role.

    Cloud-only enhancement. Falls back to "pass" on parse error
    to avoid blocking responses.
    """

    @property
    def system_prompt(self) -> str:
        from .prompts import VALIDATOR_PROMPT
        return VALIDATOR_PROMPT

    def parse_response(self, content: str) -> ValidationReport:
        """Parse JSON validation report from LLM response."""
        try:
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)

            return ValidationReport.create(
                is_safe=data.get("is_safe", True),
                is_high_quality=data.get("is_high_quality", True),
                quality_score=float(data.get("quality_score", 1.0)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            self.logger.warning(
                f"Validator parse failed: {type(e).__name__} — verification_status=parse_error",
                component=LogComponent.COUNCIL,
            )
            # Fail open — don't block on parse error.
            # is_high_quality=False signals parse failure to callers (not a clean pass).
            return ValidationReport.create(
                is_safe=True,
                is_high_quality=False,
                quality_score=0.0,
                issues=[f"verification_status=parse_error: {type(e).__name__}"],
            )


class Responder(CouncilRole):
    """
    Personality synthesis role.

    Cloud-only enhancement. Takes raw tool results and synthesizes
    a response in Hestia's voice. Returns plain text, not JSON.
    """

    @property
    def system_prompt(self) -> str:
        from .prompts import RESPONDER_PROMPT
        return RESPONDER_PROMPT

    def parse_response(self, content: str) -> str:
        """Responder returns plain text — no JSON parsing needed."""
        return content.strip()
