"""Parser for Claude.ai conversation export data.

Converts Claude's JSON export into memory chunks ready for the
Hestia memory pipeline. Extracts 4 content layers:
1. Conversation text (human/assistant turn pairs)
2. Thinking blocks (Claude's extended reasoning)
3. Thinking summaries (distilled reasoning steps)
4. Tool use patterns (search queries as topic metadata)
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger
from hestia.memory.models import (
    ChunkMetadata,
    ChunkTags,
    ChunkType,
    ConversationChunk,
    MemoryScope,
    MemorySource,
)

logger = get_logger()

# Max chars per memory chunk before splitting
MAX_CHUNK_CHARS = 2000
# Source tag for all imported chunks
SOURCE_TAG = MemorySource.CLAUDE_HISTORY.value

# Credential patterns to strip (audit condition #6)
CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI/Anthropic API keys
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub PATs
    re.compile(r"xox[bprs]-[a-zA-Z0-9\-]+"),  # Slack tokens
    re.compile(r"-----BEGIN [A-Z ]+ KEY-----"),  # PEM keys
    re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),  # password=...
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),  # api_key=...
]


def strip_credentials(text: str) -> str:
    """Remove potential credentials from imported text."""
    for pattern in CREDENTIAL_PATTERNS:
        text = pattern.sub("[CREDENTIAL_REDACTED]", text)
    return text


class ClaudeHistoryParser:
    """Parse Claude.ai exported conversations into ConversationChunks.

    Chunking strategy:
    - Group human+assistant turn pairs
    - Split when accumulated text exceeds MAX_CHUNK_CHARS
    - Extract thinking blocks as INSIGHT chunks
    - Capture web search queries as topic tags
    - Strip credentials before storage
    """

    def parse_export(
        self,
        conversations: List[Dict[str, Any]],
        memories: Optional[List[Dict[str, Any]]] = None,
        projects: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ConversationChunk]:
        """Parse a full Claude export into ConversationChunks."""
        all_chunks: List[ConversationChunk] = []

        for conv in conversations:
            all_chunks.extend(self.parse_conversation(conv))

        # Parse Claude's memory summaries as high-value context
        if memories and len(memories) > 0:
            all_chunks.extend(self._parse_memories(memories[0]))

        # Parse project context (skip docs — they're in the codebase)
        if projects:
            all_chunks.extend(self._parse_projects(projects))

        logger.info(
            "Parsed Claude export: %d conversations, %d chunks",
            len(conversations),
            len(all_chunks),
        )
        return all_chunks

    def parse_conversation(self, conv: Dict[str, Any]) -> List[ConversationChunk]:
        """Parse a single conversation into chunks.

        Extracts 4 content layers:
        1. Conversation text (human/assistant turn pairs)
        2. Thinking blocks (Claude's extended reasoning)
        3. Thinking summaries (distilled reasoning steps)
        4. Tool use patterns (search queries as topic metadata)
        """
        messages = conv.get("chat_messages", [])
        if not messages:
            return []

        conv_name = conv.get("name", "Untitled")
        conv_id = conv.get("uuid", "unknown")
        created_at = conv.get("created_at", "")
        summary = conv.get("summary", "")

        base_tags = ["claude_history", "imported"]
        base_source = SOURCE_TAG

        chunks: List[ConversationChunk] = []
        current_text = ""
        current_start = created_at
        tool_queries: List[str] = []

        for msg in messages:
            sender = msg.get("sender", "unknown")
            content_parts = msg.get("content", [])

            # Extract text content
            text = msg.get("text", "")
            if not text:
                text = " ".join(
                    p.get("text", "")
                    for p in content_parts
                    if isinstance(p, dict) and p.get("type") == "text"
                )

            # Process content parts for thinking + tool use
            for part in content_parts:
                if not isinstance(part, dict):
                    continue

                if part.get("type") == "thinking":
                    thinking_text = part.get("thinking", "")
                    if thinking_text and len(thinking_text) > 100:
                        chunks.append(self._make_thinking_chunk(
                            thinking_text, conv_name, conv_id, base_source,
                            msg.get("created_at", created_at),
                        ))

                elif part.get("type") == "tool_use":
                    tool_name = part.get("name", "")
                    tool_input = part.get("input", {})
                    if tool_name == "web_search" and isinstance(tool_input, dict):
                        query = tool_input.get("query", "")
                        if query:
                            tool_queries.append(query)

            if not text.strip():
                continue

            role = "User" if sender == "human" else "Assistant"
            turn = f"[{role}]: {text.strip()}\n\n"

            if len(current_text) + len(turn) > MAX_CHUNK_CHARS and current_text:
                chunks.append(self._make_conversation_chunk(
                    current_text, conv_name, conv_id, base_source,
                    current_start, base_tags,
                ))
                current_text = ""
                current_start = msg.get("created_at", created_at)

            current_text += turn

        # Flush remaining conversation text
        if current_text.strip():
            chunks.append(self._make_conversation_chunk(
                current_text, conv_name, conv_id, base_source,
                current_start, base_tags,
            ))

        # Add conversation summary as insight chunk
        if summary and len(summary) > 50:
            chunks.append(self._make_insight_chunk(
                f"[CLAUDE CONVERSATION SUMMARY — {conv_name}]: {strip_credentials(summary)}",
                conv_id, base_source, created_at,
                tags=base_tags + ["summary"],
            ))

        # Attach tool query topics as tags on all chunks
        if tool_queries:
            topic_tags = [f"researched:{q[:60]}" for q in tool_queries[:10]]
            for chunk in chunks:
                chunk.tags.topics.extend(topic_tags)

        return chunks

    def _make_conversation_chunk(
        self, text: str, conv_name: str, conv_id: str,
        source: str, timestamp: str, tags: List[str],
    ) -> ConversationChunk:
        content = strip_credentials(
            f"[IMPORTED CLAUDE HISTORY — {conv_name}]:\n{text.strip()}"
        )
        return ConversationChunk(
            id=f"import-{uuid.uuid4().hex[:12]}",
            session_id=f"claude-import-{conv_id[:12]}",
            timestamp=self._parse_timestamp(timestamp),
            content=content,
            chunk_type=ChunkType.CONVERSATION,
            scope=MemoryScope.LONG_TERM,
            tags=ChunkTags(topics=list(tags)),
            metadata=ChunkMetadata(
                source=source,
                confidence=0.8,
            ),
        )

    def _make_thinking_chunk(
        self, thinking_text: str, conv_name: str, conv_id: str,
        source: str, timestamp: str,
    ) -> ConversationChunk:
        content = strip_credentials(
            f"[CLAUDE REASONING — {conv_name}]:\n{thinking_text[:MAX_CHUNK_CHARS]}"
        )
        return ConversationChunk(
            id=f"import-{uuid.uuid4().hex[:12]}",
            session_id=f"claude-import-{conv_id[:12]}",
            timestamp=self._parse_timestamp(timestamp),
            content=content,
            chunk_type=ChunkType.INSIGHT,
            scope=MemoryScope.LONG_TERM,
            tags=ChunkTags(topics=["claude_history", "claude_thinking", "imported"]),
            metadata=ChunkMetadata(
                source=source,
                confidence=0.7,
            ),
        )

    def _make_insight_chunk(
        self, content: str, conv_id: str, source: str,
        timestamp: str, tags: Optional[List[str]] = None,
    ) -> ConversationChunk:
        return ConversationChunk(
            id=f"import-{uuid.uuid4().hex[:12]}",
            session_id=f"claude-import-{conv_id[:12]}",
            timestamp=self._parse_timestamp(timestamp),
            content=strip_credentials(content),
            chunk_type=ChunkType.INSIGHT,
            scope=MemoryScope.LONG_TERM,
            tags=ChunkTags(topics=tags or ["claude_history", "imported"]),
            metadata=ChunkMetadata(
                source=source,
                confidence=0.9,
            ),
        )

    def _parse_memories(self, memories: Dict[str, Any]) -> List[ConversationChunk]:
        """Parse Claude's conversation memory summary."""
        chunks = []
        conv_memory = memories.get("conversations_memory", "")
        if conv_memory and len(conv_memory) > 50:
            chunks.append(self._make_insight_chunk(
                f"[CLAUDE MEMORY SUMMARY]: {conv_memory}",
                "memory-summary", SOURCE_TAG,
                datetime.now(timezone.utc).isoformat(),
                tags=["claude_history", "memory_summary", "imported"],
            ))

        for project_id, content in memories.get("project_memories", {}).items():
            if isinstance(content, str) and len(content) > 50:
                chunks.append(self._make_insight_chunk(
                    f"[CLAUDE PROJECT MEMORY]: {content}",
                    f"project-{project_id[:12]}", SOURCE_TAG,
                    datetime.now(timezone.utc).isoformat(),
                    tags=["claude_history", "project_memory", "imported"],
                ))
        return chunks

    def _parse_projects(self, projects: List[Dict[str, Any]]) -> List[ConversationChunk]:
        """Parse project descriptions (skip docs — they're in the codebase)."""
        chunks = []
        for project in projects:
            name = project.get("name", "Unknown")
            desc = project.get("description", "")
            if desc and len(desc) > 50:
                chunks.append(self._make_insight_chunk(
                    f"[CLAUDE PROJECT — {name}]: {desc}",
                    project.get("uuid", "unknown")[:12], SOURCE_TAG,
                    project.get("created_at", datetime.now(timezone.utc).isoformat()),
                    tags=["claude_history", "project_context", "imported", name.lower()],
                ))
        return chunks

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        """Parse ISO timestamp, falling back to now."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
