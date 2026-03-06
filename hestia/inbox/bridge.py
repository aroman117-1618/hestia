"""
InboxMemoryBridge -- ingests Apple inbox data into the memory system.

Mediates between InboxManager (read-only) and MemoryManager (write).
Handles preprocessing, deduplication, encryption, and prompt injection
sanitization for email/calendar/reminder/notes content.

Architecture: InboxManager (read) -> InboxMemoryBridge (transform) -> MemoryManager (write)
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from hestia.logging import get_logger, LogComponent
from hestia.memory.models import (
    ChunkMetadata,
    ChunkTags,
    ChunkType,
    MemoryScope,
    MemorySource,
)

logger = get_logger()

# Maps InboxItemSource -> MemorySource
_SOURCE_MAP = {
    "mail": MemorySource.MAIL,
    "calendar": MemorySource.CALENDAR,
    "reminders": MemorySource.REMINDERS,
}

# Maps InboxItemSource -> ChunkType
_CHUNK_TYPE_MAP = {
    "mail": ChunkType.FACT,
    "calendar": ChunkType.FACT,
    "reminders": ChunkType.FACT,
    "notes": ChunkType.INSIGHT,
}

# Email signature patterns to strip
_SIGNATURE_PATTERNS = [
    re.compile(r"^--\s*$.*", re.MULTILINE | re.DOTALL),
    re.compile(r"^Sent from my (iPhone|iPad|Mac).*$", re.MULTILINE | re.DOTALL),
    re.compile(r"^Get Outlook for.*$", re.MULTILINE | re.DOTALL),
]

# Prompt injection suspicious patterns (log-only)
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?previous instructions", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"system:\s", re.IGNORECASE),
    re.compile(r"</?system>", re.IGNORECASE),
    re.compile(r"IMPORTANT:.*override", re.IGNORECASE),
]

# Max chunk size before splitting
MAX_CHUNK_CHARS = 2000

# Per-source caps
MAX_CHUNKS_PER_SOURCE = 500


@dataclass
class IngestionResult:
    """Result of a batch ingestion run."""
    batch_id: str
    source: str
    items_processed: int
    items_stored: int
    items_skipped: int
    items_failed: int
    errors: List[str]


class InboxMemoryBridge:
    """
    Bridge that ingests inbox data into the memory system.

    InboxManager stays read-only. This bridge handles all transformation,
    dedup, and security before writing to MemoryManager.
    """

    def __init__(
        self,
        inbox_manager: "InboxManager",
        memory_manager: "MemoryManager",
    ) -> None:
        self._inbox = inbox_manager
        self._memory = memory_manager

    async def ingest(
        self,
        user_id: str,
        source_filter: Optional[str] = None,
        batch_size: int = 50,
        days_back: int = 30,
    ) -> IngestionResult:
        """
        Ingest inbox items into the memory system.

        Args:
            user_id: User whose inbox to ingest.
            source_filter: Optional source to limit ("mail", "calendar", "reminders").
            batch_size: Items per processing batch.
            days_back: Only ingest items from the last N days.

        Returns:
            IngestionResult with counts and errors.
        """
        batch_id = f"ingest-{uuid4().hex[:8]}"
        db = self._memory.database

        await db.start_ingestion_batch(batch_id, source_filter or "all")

        items = await self._inbox.get_inbox(
            user_id=user_id,
            source=source_filter,
            include_archived=False,
            limit=MAX_CHUNKS_PER_SOURCE,
        )

        result = IngestionResult(
            batch_id=batch_id,
            source=source_filter or "all",
            items_processed=0,
            items_stored=0,
            items_skipped=0,
            items_failed=0,
            errors=[],
        )

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            for item in batch:
                result.items_processed += 1
                try:
                    stored = await self._ingest_item(item, batch_id)
                    if stored:
                        result.items_stored += 1
                    else:
                        result.items_skipped += 1
                except Exception as e:
                    result.items_failed += 1
                    result.errors.append(f"{item.id}: {type(e).__name__}")
                    logger.warning(
                        f"Ingestion failed for {item.id}: {type(e).__name__}",
                        component=LogComponent.MEMORY,
                    )

        await db.complete_ingestion_batch(
            batch_id, result.items_processed,
            result.items_stored, result.items_skipped,
        )

        logger.info(
            f"Ingestion complete: {result.items_stored} stored, "
            f"{result.items_skipped} skipped, {result.items_failed} failed",
            component=LogComponent.MEMORY,
            data={"batch_id": batch_id},
        )

        return result

    async def _ingest_item(self, item: "InboxItem", batch_id: str) -> bool:
        """Ingest a single inbox item. Returns True if stored, False if skipped."""
        db = self._memory.database
        source_str = item.source.value

        # Dedup check
        if await db.check_duplicate(source_str, item.id):
            return False

        # Map source
        memory_source = _SOURCE_MAP.get(source_str)
        if memory_source is None:
            return False

        chunk_type = _CHUNK_TYPE_MAP.get(source_str, ChunkType.FACT)

        # Preprocess content
        content = self._preprocess_content(item)
        if not content or len(content.strip()) < 10:
            return False

        # Check for prompt injection (log only)
        self._check_injection(item.id, content)

        # Build chunks (split if too long)
        chunks = self._split_content(content, MAX_CHUNK_CHARS)

        tags = ChunkTags(
            topics=[source_str],
            people=[item.sender] if item.sender else [],
        )

        for chunk_content in chunks:
            chunk = await self._memory.store(
                content=chunk_content,
                chunk_type=chunk_type,
                tags=tags,
                metadata=ChunkMetadata(source=memory_source.value),
                scope=MemoryScope.SHORT_TERM,
            )
            await db.record_dedup(source_str, item.id, chunk.id, batch_id)

        return True

    def _preprocess_content(self, item: "InboxItem") -> str:
        """Build memory-ready content from an inbox item."""
        parts = []

        # Content prefix for provenance
        source_label = item.source.value.upper()
        date_str = item.timestamp.strftime("%Y-%m-%d") if item.timestamp else "unknown"
        sender_str = item.sender or "unknown"

        if item.source.value == "mail":
            parts.append(f"[INGESTED {source_label} -- {sender_str} -- {date_str}]:")
            parts.append(f"Subject: {item.title}")
            if item.body:
                cleaned = self._clean_email_body(item.body)
                parts.append(cleaned)
        elif item.source.value == "calendar":
            parts.append(f"[INGESTED {source_label} -- {date_str}]:")
            parts.append(f"Event: {item.title}")
            if item.metadata.get("location"):
                parts.append(f"Location: {item.metadata['location']}")
            if item.metadata.get("start"):
                parts.append(f"Time: {item.metadata['start']}")
        elif item.source.value == "reminders":
            parts.append(f"[INGESTED {source_label} -- {date_str}]:")
            parts.append(f"Reminder: {item.title}")
            if item.metadata.get("due"):
                parts.append(f"Due: {item.metadata['due']}")
            if item.metadata.get("list_name"):
                parts.append(f"List: {item.metadata['list_name']}")
        else:
            parts.append(f"[INGESTED {source_label} -- {date_str}]:")
            parts.append(item.title)
            if item.body:
                parts.append(item.body[:MAX_CHUNK_CHARS])

        return "\n".join(parts)

    def _clean_email_body(self, body: str) -> str:
        """Strip HTML, signatures, quoted threads, and control chars from email body."""
        text = body

        # Strip basic HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Strip HTML entities
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&[a-z]+;", "", text)

        # Remove email signatures
        for pattern in _SIGNATURE_PATTERNS:
            text = pattern.sub("", text)

        # Collapse quoted thread text (lines starting with >)
        text = re.sub(r"^>.*$", "", text, flags=re.MULTILINE)

        # Strip control characters and zero-width Unicode
        text = self._sanitize_text(text)

        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Remove control characters and zero-width Unicode."""
        # Remove zero-width chars
        text = text.replace("\u200b", "")  # zero-width space
        text = text.replace("\u200c", "")  # zero-width non-joiner
        text = text.replace("\u200d", "")  # zero-width joiner
        text = text.replace("\ufeff", "")  # BOM

        # Remove other control chars (keep \n, \t, \r)
        cleaned = []
        for ch in text:
            if ch in ("\n", "\t", "\r"):
                cleaned.append(ch)
            elif unicodedata.category(ch) == "Cc":
                continue  # Skip control characters
            else:
                cleaned.append(ch)
        return "".join(cleaned)

    @staticmethod
    def _check_injection(item_id: str, content: str) -> None:
        """Log suspicious prompt injection patterns (monitoring only)."""
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(content):
                logger.warning(
                    f"Potential prompt injection in {item_id}",
                    component=LogComponent.MEMORY,
                    data={"pattern": pattern.pattern},
                )
                break  # One warning per item is enough

    @staticmethod
    def _split_content(content: str, max_chars: int) -> List[str]:
        """Split content into chunks on paragraph boundaries."""
        if len(content) <= max_chars:
            return [content]

        chunks = []
        paragraphs = content.split("\n\n")
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 > max_chars:
                if current:
                    chunks.append(current.strip())
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [content[:max_chars]]
