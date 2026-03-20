"""Dry-run review output for import pipelines.

Generates a human-reviewable JSON file with proposed memory chunks,
projected importance scores, and summary statistics — without
committing anything to the memory system.
"""

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.memory.models import ConversationChunk


# Importance weights from memory.yaml (duplicated here to avoid
# needing a running server for dry-run scoring)
_TYPE_BONUSES: Dict[str, float] = {
    "fact": 0.8,
    "decision": 0.7,
    "preference": 0.6,
    "research": 0.5,
    "insight": 0.8,
    "action_item": 0.4,
    "conversation": 0.3,
    "observation": 0.0,
    "system": 1.0,
    "source_structured": 0.2,
}
_W_RECENCY = 0.2
_W_TYPE = 0.3
_MIN_IMPORTANCE = 0.05


def _project_importance(chunk: ConversationChunk) -> float:
    """Estimate importance score for a chunk that hasn't been stored yet.

    Uses recency + type_bonus only (no retrieval or durability data).
    This gives a conservative lower-bound estimate.
    """
    # Recency: linear decay from 1.0 (today) to 0.05 (90+ days ago)
    age_days = (datetime.now(timezone.utc) - chunk.timestamp).days
    recency = max(1.0 - (age_days / 90.0), _MIN_IMPORTANCE)

    type_bonus = _TYPE_BONUSES.get(chunk.chunk_type.value, 0.0)

    # Simplified: w_recency * recency + w_type * type_bonus
    # Retrieval and durability are 0 for new chunks
    return round(_W_RECENCY * recency + _W_TYPE * type_bonus, 4)


@dataclass
class DryRunChunkEntry:
    """A single proposed chunk for human review."""

    conversation_title: str
    conversation_date: str
    message_count: int
    chunk_type: str
    confidence: float
    projected_importance: float
    content_preview: str  # First 500 chars
    full_content_length: int
    tags: List[str]
    model_slug: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DryRunReview:
    """Collection of proposed chunks with summary statistics."""

    entries: List[DryRunChunkEntry] = field(default_factory=list)
    generated_at: str = ""

    @classmethod
    def from_chunks(
        cls,
        chunks: List[ConversationChunk],
        conversations: List[Dict[str, Any]],
    ) -> "DryRunReview":
        """Build review from parsed chunks and source conversations."""
        # Build conversation metadata lookup keyed by the first 12 chars of conv id
        conv_meta: Dict[str, Dict[str, Any]] = {}
        for conv in conversations:
            conv_id = str(conv.get("id", conv.get("conversation_id", "unknown")))[:12]
            mapping = conv.get("mapping", {})
            msg_count = sum(
                1
                for node in mapping.values()
                if node.get("message")
                and node["message"].get("role") in ("user", "assistant")
            )
            conv_meta[conv_id] = {
                "title": conv.get("title") or "Untitled",
                "date": "",
                "message_count": msg_count,
            }
            ct = conv.get("create_time")
            if ct:
                try:
                    conv_meta[conv_id]["date"] = datetime.fromtimestamp(
                        float(ct), tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                except (ValueError, TypeError, OSError):
                    pass

        entries: List[DryRunChunkEntry] = []
        for chunk in chunks:
            # Match chunk to conversation via session_id prefix
            session_key = chunk.session_id.replace("openai-import-", "")[:12]
            meta = conv_meta.get(
                session_key,
                {"title": "Unknown", "date": "", "message_count": 0},
            )

            # Extract model slug from tags
            model_slug: Optional[str] = None
            for tag in chunk.tags.topics:
                if tag.startswith("model:"):
                    model_slug = tag.split(":", 1)[1]
                    break

            entries.append(
                DryRunChunkEntry(
                    conversation_title=meta["title"],
                    conversation_date=meta["date"],
                    message_count=meta["message_count"],
                    chunk_type=chunk.chunk_type.value,
                    confidence=chunk.metadata.confidence,
                    projected_importance=_project_importance(chunk),
                    content_preview=chunk.content[:500],
                    full_content_length=len(chunk.content),
                    tags=chunk.tags.topics,
                    model_slug=model_slug,
                )
            )

        return cls(
            entries=entries,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def write_json(self, path: str) -> None:
        """Write review to a JSON file for human inspection."""
        # Group entries by conversation for easier scanning
        by_conv: Dict[str, List[Dict[str, Any]]] = {}
        for entry in self.entries:
            key = f"{entry.conversation_date} — {entry.conversation_title}"
            by_conv.setdefault(key, []).append(entry.to_dict())

        # Type breakdown
        type_counts = Counter(e.chunk_type for e in self.entries)

        # Importance distribution
        importances = [e.projected_importance for e in self.entries]
        avg_importance = sum(importances) / len(importances) if importances else 0.0

        output: Dict[str, Any] = {
            "summary": {
                "generated_at": self.generated_at,
                "total_chunks": len(self.entries),
                "conversations_processed": len(by_conv),
                "by_type": dict(type_counts),
                "avg_projected_importance": round(avg_importance, 4),
                "importance_range": {
                    "min": round(min(importances), 4) if importances else 0,
                    "max": round(max(importances), 4) if importances else 0,
                },
            },
            "entries": by_conv,
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
