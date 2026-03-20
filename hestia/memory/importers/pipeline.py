"""Import pipeline — orchestrates parse → dedup → store → embed.

Processes external conversation history through the full memory pipeline
so imported content gets proper tagging, embedding, and is queryable
alongside native conversation memory.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger
from hestia.memory.models import MemorySource

logger = get_logger()


@dataclass
class ImportResult:
    """Result of a history import operation."""
    batch_id: str
    source: str
    conversations_processed: int = 0
    chunks_stored: int = 0
    chunks_skipped: int = 0
    chunks_failed: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "source": self.source,
            "conversations_processed": self.conversations_processed,
            "chunks_stored": self.chunks_stored,
            "chunks_skipped": self.chunks_skipped,
            "chunks_failed": self.chunks_failed,
            "errors": self.errors[:20],  # Cap error list
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ImportPipeline:
    """Import external conversation history into Hestia's memory.

    Flow: parse → dedup → store (SQLite + ChromaDB) → record dedup
    """

    def __init__(self, memory_manager: Any, memory_database: Any) -> None:
        self.memory_manager = memory_manager
        self.memory_database = memory_database

    async def import_claude_history(
        self,
        conversations_path: str,
        memories_path: Optional[str] = None,
        projects_path: Optional[str] = None,
    ) -> ImportResult:
        """Import Claude.ai export data into Hestia memory.

        Args:
            conversations_path: Path to conversations.json
            memories_path: Optional path to memories.json
            projects_path: Optional path to projects.json

        Returns:
            ImportResult with stats on what was imported.
        """
        from hestia.memory.importers.claude import ClaudeHistoryParser

        batch_id = f"claude-import-{uuid.uuid4().hex[:8]}"
        result = ImportResult(
            batch_id=batch_id,
            source=MemorySource.CLAUDE_HISTORY.value,
            started_at=datetime.now(timezone.utc),
        )

        # Load JSON files
        try:
            conversations = self._load_json(conversations_path)
            memories = self._load_json(memories_path) if memories_path else None
            projects = self._load_json(projects_path) if projects_path else None
        except Exception as e:
            result.errors.append(f"Failed to load JSON: {type(e).__name__}: {e}")
            result.completed_at = datetime.now(timezone.utc)
            return result

        result.conversations_processed = len(conversations) if isinstance(conversations, list) else 0

        # Parse into chunks
        parser = ClaudeHistoryParser()
        chunks = parser.parse_export(
            conversations=conversations if isinstance(conversations, list) else [],
            memories=memories if isinstance(memories, list) else None,
            projects=projects if isinstance(projects, list) else None,
        )

        logger.info(
            "Import pipeline: parsed %d chunks from %d conversations",
            len(chunks), result.conversations_processed,
        )

        # Store each chunk with dedup
        source = MemorySource.CLAUDE_HISTORY.value
        for chunk in chunks:
            try:
                # Dedup using stable key (session + content hash, not random chunk ID)
                import hashlib
                content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:16]
                source_id = f"{chunk.session_id}:{content_hash}"
                is_dup = await self.memory_database.check_duplicate(source, source_id)
                if is_dup:
                    result.chunks_skipped += 1
                    continue

                # Store through memory manager (SQLite + ChromaDB)
                stored = await self.memory_manager.store(
                    content=chunk.content,
                    chunk_type=chunk.chunk_type,
                    tags=chunk.tags,
                    metadata=chunk.metadata,
                    session_id=chunk.session_id,
                    auto_tag=False,  # Already tagged by parser
                    scope=chunk.scope,
                )

                # Record dedup
                await self.memory_database.record_dedup(
                    source=source,
                    source_id=source_id,
                    chunk_id=stored.id,
                    batch_id=batch_id,
                )

                result.chunks_stored += 1

            except Exception as e:
                result.chunks_failed += 1
                if len(result.errors) < 20:
                    result.errors.append(f"{type(e).__name__}: {str(e)[:100]}")

        result.completed_at = datetime.now(timezone.utc)
        logger.info(
            "Import complete: %d stored, %d skipped, %d failed",
            result.chunks_stored, result.chunks_skipped, result.chunks_failed,
        )
        return result

    @staticmethod
    def dry_run_openai(
        export_path: str,
        output_path: str,
        exclude_hestia: bool = True,
        exclude_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Parse ChatGPT export and output proposed chunks for review.

        Does NOT store anything in the memory system. Outputs a JSON
        file with proposed chunks, projected importance scores, and
        summary statistics for human review.

        Args:
            export_path: Path to conversations JSON file (or directory with
                         conversations-NNN.json files).
            output_path: Path to write the review JSON file.
            exclude_hestia: Skip Hestia-related conversations.
            exclude_keywords: Custom exclusion keywords (overrides default).

        Returns:
            Summary dict with counts and stats.
        """
        from hestia.memory.importers.openai import OpenAIHistoryParser
        from hestia.memory.importers.review import DryRunReview

        export = Path(export_path)

        # Load conversations — single file or directory with numbered files
        all_conversations: List[Dict[str, Any]] = []
        if export.is_dir():
            for f in sorted(export.glob("conversations*.json")):
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        all_conversations.extend(data)
        else:
            with open(export, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    all_conversations = data

        # Parse with exclusion filter
        parser = OpenAIHistoryParser(
            exclude_keywords=exclude_keywords,
        )
        chunks = parser.parse_export(
            all_conversations, exclude_hestia=exclude_hestia,
        )

        # Build review and write
        review = DryRunReview.from_chunks(chunks, all_conversations)
        review.write_json(output_path)

        logger.info(
            "Dry run complete: %d chunks from %d conversations → %s",
            len(chunks), len(all_conversations), output_path,
        )

        return {
            "total_chunks": len(review.entries),
            "conversations_processed": len(all_conversations),
            "output_path": output_path,
        }

    @staticmethod
    def _load_json(path: str) -> Any:
        """Load a JSON file from disk."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
