"""Parser for ChatGPT/OpenAI conversation export data.

Converts ChatGPT's JSON export into memory chunks ready for the
Hestia memory pipeline. Key differences from Claude exports:
- Messages stored as a DAG (mapping dict), not a flat list
- Timestamps are Unix floats, not ISO strings
- No thinking blocks or tool_use metadata
- current_node pointer identifies the active thread leaf
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from hestia.logging import get_logger
from hestia.memory.importers.claude import (
    CREDENTIAL_PATTERNS,
    MAX_CHUNK_CHARS,
    strip_credentials,
)
from hestia.memory.models import (
    ChunkMetadata,
    ChunkTags,
    ChunkType,
    ConversationChunk,
    MemoryScope,
    MemorySource,
)

logger = get_logger()

SOURCE_TAG = MemorySource.OPENAI_HISTORY.value

# Keywords that identify Hestia-related conversations (excluded from dry-run)
HESTIA_KEYWORDS = [
    "hestia", "tia", "mac mini", "ollama", "fastapi",
    "claude code", "hestia-cli", "swiftui", "chromadb",
    "memory pipeline", "council", "orchestrat",
]


def flatten_message_dag(
    mapping: Dict[str, Any], current_node: str
) -> List[Dict[str, Any]]:
    """Walk from current_node to root via parent pointers, return ordered list.

    ChatGPT stores messages as a DAG with parent/children pointers.
    When users edit messages, branches form. We only want the active
    thread: the path from root to current_node.
    """
    if current_node not in mapping:
        return []

    # Walk backward from leaf to root
    path: List[Dict[str, Any]] = []
    node_id: Optional[str] = current_node
    visited: Set[str] = set()

    while node_id and node_id in mapping and node_id not in visited:
        visited.add(node_id)
        node = mapping[node_id]
        path.append(node)
        node_id = node.get("parent")

    # Reverse to get root → leaf order
    path.reverse()
    return path


class OpenAIHistoryParser:
    """Parse ChatGPT exported conversations into ConversationChunks.

    Chunking strategy:
    - Flatten message DAG to active thread
    - Group user+assistant turn pairs
    - Split when accumulated text exceeds MAX_CHUNK_CHARS
    - All chunks typed as OBSERVATION (not DECISION/PREFERENCE)
    - Strip credentials before storage
    - Skip system messages
    """

    def __init__(self, exclude_keywords: Optional[List[str]] = None) -> None:
        self._exclude_keywords = [
            kw.lower() for kw in (exclude_keywords or HESTIA_KEYWORDS)
        ]

    def should_exclude(self, conversation: Dict[str, Any]) -> bool:
        """Check if conversation matches exclusion keywords."""
        title = (conversation.get("title") or "").lower()
        return any(kw in title for kw in self._exclude_keywords)

    def parse_export(
        self,
        conversations: List[Dict[str, Any]],
        exclude_hestia: bool = True,
    ) -> List[ConversationChunk]:
        """Parse a full ChatGPT export into ConversationChunks.

        Args:
            conversations: List of conversation dicts from ChatGPT export.
            exclude_hestia: If True, skip conversations matching Hestia keywords.

        Returns:
            List of ConversationChunks ready for pipeline.
        """
        all_chunks: List[ConversationChunk] = []
        skipped = 0

        for conv in conversations:
            if exclude_hestia and self.should_exclude(conv):
                skipped += 1
                continue
            all_chunks.extend(self.parse_conversation(conv))

        logger.info(
            "Parsed OpenAI export: %d conversations (%d excluded), %d chunks",
            len(conversations), skipped, len(all_chunks),
        )
        return all_chunks

    def parse_conversation(
        self, conv: Dict[str, Any]
    ) -> List[ConversationChunk]:
        """Parse a single ChatGPT conversation into chunks."""
        mapping = conv.get("mapping", {})
        current_node = conv.get("current_node")
        if not mapping or not current_node:
            return []

        # Flatten DAG to active thread
        thread = flatten_message_dag(mapping, current_node)
        if not thread:
            return []

        title = conv.get("title") or "Untitled"
        conv_id = conv.get("id", conv.get("conversation_id", "unknown"))
        create_time = conv.get("create_time", 0.0)

        # Extract model slug from any assistant message
        model_slug = self._extract_model_slug(thread)

        base_tags = ["openai_history", "imported"]
        if model_slug:
            base_tags.append(f"model:{model_slug}")

        chunks: List[ConversationChunk] = []
        current_text = ""
        current_ts = create_time

        for node in thread:
            msg = node.get("message")
            if not msg:
                continue

            role = msg.get("role", "")
            if role == "system":
                continue  # Skip system prompts

            # Extract text from content.parts
            content = msg.get("content", {})
            parts = content.get("parts", [])
            text = " ".join(
                str(p) for p in parts if isinstance(p, str) and p.strip()
            )
            if not text.strip():
                continue

            label = "User" if role == "user" else "Assistant"
            turn = f"[{label}]: {text.strip()}\n\n"

            if len(current_text) + len(turn) > MAX_CHUNK_CHARS and current_text:
                chunks.append(self._make_chunk(
                    current_text, title, conv_id, current_ts, base_tags,
                ))
                current_text = ""
                current_ts = msg.get("create_time", create_time)

            current_text += turn
            if not current_ts:
                current_ts = msg.get("create_time", create_time)

        # Flush remaining text
        if current_text.strip():
            chunks.append(self._make_chunk(
                current_text, title, conv_id, current_ts, base_tags,
            ))

        return chunks

    def _make_chunk(
        self, text: str, title: str, conv_id: str,
        timestamp: float, tags: List[str],
    ) -> ConversationChunk:
        content = strip_credentials(
            f"[IMPORTED CHATGPT HISTORY — {title}]:\n{text.strip()}"
        )
        return ConversationChunk(
            id=f"import-{uuid.uuid4().hex[:12]}",
            session_id=f"openai-import-{str(conv_id)[:12]}",
            timestamp=self._parse_unix_timestamp(timestamp),
            content=content,
            chunk_type=ChunkType.OBSERVATION,
            scope=MemoryScope.LONG_TERM,
            tags=ChunkTags(topics=list(tags)),
            metadata=ChunkMetadata(
                source=SOURCE_TAG,
                confidence=0.6,  # Lower confidence for imported observations
            ),
        )

    @staticmethod
    def _extract_model_slug(thread: List[Dict[str, Any]]) -> Optional[str]:
        """Extract model slug from assistant message metadata."""
        for node in thread:
            msg = node.get("message", {})
            if msg and msg.get("role") == "assistant":
                slug = msg.get("metadata", {}).get("model_slug")
                if slug:
                    return slug
        return None

    @staticmethod
    def _parse_unix_timestamp(ts: Any) -> datetime:
        """Parse Unix float timestamp to datetime."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return datetime.now(timezone.utc)
