"""
Auto-tagger for Hestia memory chunks.

Uses Mixtral to automatically extract tags from conversation content.
Runs asynchronously to avoid blocking the main conversation flow.
"""

import json
import re
from typing import Optional

from hestia.inference import get_inference_client, Message
from hestia.logging import get_logger, LogComponent
from hestia.memory.models import ChunkTags, ChunkMetadata, ChunkType, ConversationChunk


# Prompt for tag extraction
TAG_EXTRACTION_PROMPT = """Analyze the following conversation content and extract structured tags.

Content:
{content}

Extract the following information as JSON:
{{
    "topics": ["list", "of", "main", "topics"],
    "entities": ["specific", "named", "things", "mentioned"],
    "people": ["names", "of", "people", "mentioned"],
    "has_code": true/false,
    "has_decision": true/false,
    "has_action_item": true/false,
    "sentiment": "positive" | "neutral" | "negative",
    "status": ["active"] or ["unresolved"] if there's an open question,
    "suggested_type": "conversation" | "decision" | "action_item" | "preference" | "research",
    "type_confidence": 0.0 to 1.0
}}

Guidelines:
- Topics should be general categories (e.g., "security", "authentication", "database")
- Entities should be specific things (e.g., "ChromaDB", "Face ID", "ADR-009")
- Only include people if explicitly mentioned by name
- has_code is true if there's actual code, not just technical discussion
- has_decision is true if a decision was made or confirmed
- has_action_item is true if there's a task to be done
- sentiment reflects the overall tone
- status is ["unresolved"] if there's an open question or issue

Chunk Type Classification (for suggested_type):
- "decision": Author made a clear, finalized choice between alternatives.
  MUST contain explicit commitment ("I decided", "we're going with", "I chose").
  Do NOT classify tentative statements ("maybe we should", "thinking about").
- "action_item": A concrete task with implied or stated deadline.
  MUST describe a specific action ("TODO:", "need to update X", "schedule Y").
  Do NOT classify vague intentions ("should probably", "would be nice to").
- "preference": A personal taste, habit, or recurring style choice.
  MUST express a consistent preference ("I prefer", "I always", "I never").
  Do NOT classify one-time situational choices.
- "research": Analysis results, investigation findings, or comparative evaluation.
  MUST contain synthesized findings, not just raw data or questions.
- "conversation": Default. Casual chat, questions, greetings, troubleshooting.
  When in doubt, choose "conversation" — false negatives are better than false positives.
- type_confidence: How confident you are in the classification (0.0-1.0).
  Use 0.9+ only for unambiguous cases. Use <0.5 for borderline.

Respond with ONLY the JSON object, no other text."""


# Patterns that indicate sensitive content (PII, health, financial)
SENSITIVE_PATTERNS = [
    # Health data
    r'\b(blood pressure|glucose|medication|diagnosis|symptoms|doctor|therapy|heart rate|cholesterol|bmi|body mass)\b',
    # Financial data
    r'\b(salary|income|bank account|credit card|mortgage|debt|net worth|tax return|401k|ira)\b',
    # Personal identifiers
    r'\b\d{3}-\d{2}-\d{4}\b',                          # SSN format
    r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',    # Card number format
    # Explicit privacy markers
    r'\b(private|confidential|secret|don\'t share|between us|off the record)\b',
]

# Promotional email signals — skip these from classification
PROMO_SIGNALS = [
    "unsubscribe", "view in browser", "email preferences",
    "no longer wish to receive", "opt out", "manage subscriptions",
    "privacy policy", "terms of service", "do not reply",
    "noreply@", "no-reply@", "marketing@", "updates@",
    "newsletter", "weekly digest", "daily summary",
    "powered by mailchimp", "powered by sendgrid",
]

# Minimum content length for classification (chars)
MIN_CLASSIFICATION_LENGTH = 40

# Minimum LLM confidence to promote chunk type
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.7

# Explicit action item prefixes (high-confidence heuristic, sync-safe)
ACTION_ITEM_PREFIXES = [
    "todo:", "todo -", "action item:", "action item -",
    "task:", "[ ]", "[x]", "- [ ]", "- [x]",
]

# Valid LLM-suggested types for promotion
PROMOTABLE_TYPES = {"decision", "action_item", "preference", "research"}


class AutoTagger:
    """
    Automatically extracts tags from conversation content using LLM.

    Designed to run asynchronously after conversation turns
    so users don't wait for tagging to complete.
    """

    def __init__(self):
        """Initialize auto-tagger."""
        self.logger = get_logger()

    async def extract_tags(
        self,
        content: str,
        existing_tags: Optional[ChunkTags] = None,
    ) -> tuple[ChunkTags, ChunkMetadata]:
        """
        Extract tags from content using LLM.

        Args:
            content: The content to analyze.
            existing_tags: Optional existing tags to merge with.

        Returns:
            Tuple of (ChunkTags, ChunkMetadata).
        """
        try:
            client = get_inference_client()

            prompt = TAG_EXTRACTION_PROMPT.format(content=content[:2000])  # Limit content length

            response = await client.complete(
                prompt=prompt,
                temperature=0.0,  # Deterministic for consistent tagging
                max_tokens=500,
                validate=False,  # Don't validate - JSON might look like an error
            )

            # Parse JSON response
            tags, metadata = self._parse_tag_response(response.content)

            # Merge with existing tags if provided
            if existing_tags:
                tags = self._merge_tags(existing_tags, tags)

            self.logger.debug(
                "Auto-tagged content",
                component=LogComponent.MEMORY,
                data={
                    "topics": tags.topics,
                    "entities": tags.entities[:5],  # Limit for logging
                    "has_code": metadata.has_code,
                }
            )

            return tags, metadata

        except Exception as e:
            self.logger.warning(
                f"Auto-tagging failed: {type(e).__name__}",
                component=LogComponent.MEMORY,
                data={"error_type": type(e).__name__}
            )
            # Return empty tags on failure
            return existing_tags or ChunkTags(), ChunkMetadata()

    def _parse_tag_response(self, response: str) -> tuple[ChunkTags, ChunkMetadata]:
        """Parse LLM response into tags and metadata."""
        # Try to extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if not json_match:
            return ChunkTags(), ChunkMetadata()

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return ChunkTags(), ChunkMetadata()

        tags = ChunkTags(
            topics=data.get("topics", [])[:10],  # Limit tags
            entities=data.get("entities", [])[:20],
            people=data.get("people", [])[:10],
            status=data.get("status", ["active"]),
        )

        metadata = ChunkMetadata(
            has_code=data.get("has_code", False),
            has_decision=data.get("has_decision", False),
            has_action_item=data.get("has_action_item", False),
            sentiment=data.get("sentiment"),
            is_sensitive=data.get("is_sensitive", False),
            sensitive_reason=data.get("sensitive_reason"),
            suggested_type=data.get("suggested_type"),
            type_confidence=float(data.get("type_confidence", 0.0)),
        )

        return tags, metadata

    def _merge_tags(self, existing: ChunkTags, new: ChunkTags) -> ChunkTags:
        """Merge new tags with existing tags."""
        return ChunkTags(
            topics=list(set(existing.topics + new.topics))[:10],
            entities=list(set(existing.entities + new.entities))[:20],
            people=list(set(existing.people + new.people))[:10],
            mode=existing.mode or new.mode,
            phase=existing.phase or new.phase,
            status=list(set(existing.status + new.status)),
            custom={**existing.custom, **new.custom},
        )

    def _should_classify(self, chunk: ConversationChunk) -> bool:
        """Content quality gate: only classify chunks worth promoting."""
        # Only classify CONVERSATION and OBSERVATION chunks
        if chunk.chunk_type not in (ChunkType.CONVERSATION, ChunkType.OBSERVATION):
            return False

        # Too short to classify meaningfully
        if len(chunk.content.strip()) < MIN_CLASSIFICATION_LENGTH:
            return False

        source = chunk.metadata.source if chunk.metadata else None

        # Mail filter: skip promotional/marketing emails
        if source == "mail":
            content_lower = chunk.content.lower()
            if any(signal in content_lower for signal in PROMO_SIGNALS):
                return False

        # Notes filter: only classify from "Intelligence" folder
        if source == "notes":
            folder = ""
            if chunk.tags and chunk.tags.custom:
                folder = chunk.tags.custom.get("folder", "")
            if not folder or "intelligence" not in folder.lower():
                return False

        return True

    def classify_chunk_type(
        self,
        content: str,
        metadata: ChunkMetadata,
        llm_suggested_type: Optional[str] = None,
        llm_type_confidence: float = 0.0,
    ) -> ChunkType:
        """Classify chunk type using heuristic + LLM signals.

        Priority:
        1. Explicit ACTION_ITEM prefixes (heuristic, high confidence)
        2. LLM suggested_type with confidence >= threshold
        3. Default: CONVERSATION
        """
        # Tier 1: Heuristic — explicit action item prefixes only
        content_stripped = content.strip().lower()
        if any(content_stripped.startswith(prefix) for prefix in ACTION_ITEM_PREFIXES):
            return ChunkType.ACTION_ITEM

        # Tier 2: LLM classification with confidence gate
        if (
            llm_suggested_type
            and llm_suggested_type in PROMOTABLE_TYPES
            and llm_type_confidence >= CLASSIFICATION_CONFIDENCE_THRESHOLD
        ):
            try:
                return ChunkType(llm_suggested_type)
            except ValueError:
                pass  # Invalid type string, fall through

        return ChunkType.CONVERSATION

    def quick_tag(self, content: str) -> tuple[ChunkTags, ChunkMetadata]:
        """
        Quick synchronous tagging using heuristics (no LLM).

        Use this for immediate tagging when LLM isn't needed.

        Args:
            content: The content to analyze.

        Returns:
            Tuple of (ChunkTags, ChunkMetadata).
        """
        tags = ChunkTags()
        metadata = ChunkMetadata()

        content_lower = content.lower()

        # Detect code
        code_indicators = ["```", "def ", "class ", "import ", "function ", "const ", "let ", "var "]
        metadata.has_code = any(ind in content for ind in code_indicators)

        # Detect decisions
        decision_indicators = ["decided", "decision", "we'll go with", "chosen", "selected", "agreed"]
        metadata.has_decision = any(ind in content_lower for ind in decision_indicators)

        # Detect action items
        action_indicators = ["todo", "action item", "next step", "will do", "need to", "should"]
        metadata.has_action_item = any(ind in content_lower for ind in action_indicators)

        # Detect questions (unresolved status)
        if "?" in content and not any(ind in content_lower for ind in ["answered", "resolved", "done"]):
            tags.status = ["unresolved"]
        else:
            tags.status = ["active"]

        # Extract common entities (simple pattern matching)
        common_entities = [
            "ChromaDB", "SQLite", "Mixtral", "Ollama", "FastAPI", "SwiftUI",
            "Face ID", "Touch ID", "Keychain", "Secure Enclave", "Tailscale",
            "ADR-", "Phase "
        ]
        for entity in common_entities:
            if entity in content:
                # Find actual matches with context
                pattern = rf'{entity}[\w-]*'
                matches = re.findall(pattern, content)
                tags.entities.extend(matches[:5])

        tags.entities = list(set(tags.entities))[:20]

        # Detect sensitive content
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                metadata.is_sensitive = True
                metadata.sensitive_reason = "pii_detected"
                break

        return tags, metadata


# Module-level singleton
_tagger: Optional[AutoTagger] = None


def get_tagger() -> AutoTagger:
    """Get or create the singleton auto-tagger instance."""
    global _tagger
    if _tagger is None:
        _tagger = AutoTagger()
    return _tagger
