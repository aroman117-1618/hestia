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
from hestia.memory.models import ChunkTags, ChunkMetadata, ConversationChunk


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
    "status": ["active"] or ["unresolved"] if there's an open question
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

Respond with ONLY the JSON object, no other text."""


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
                f"Auto-tagging failed: {e}",
                component=LogComponent.MEMORY,
                data={"error": str(e)}
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

        return tags, metadata


# Module-level singleton
_tagger: Optional[AutoTagger] = None


def get_tagger() -> AutoTagger:
    """Get or create the singleton auto-tagger instance."""
    global _tagger
    if _tagger is None:
        _tagger = AutoTagger()
    return _tagger
