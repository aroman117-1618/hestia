"""
Data models for the Investigate module.

URL content analysis: extraction results, investigation records,
and depth-level configuration for LLM analysis.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ContentType(Enum):
    """Types of content that can be investigated."""
    WEB_ARTICLE = "web_article"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    AUDIO = "audio"
    VIDEO = "video"
    UNKNOWN = "unknown"


class AnalysisDepth(Enum):
    """Depth levels for LLM analysis."""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


# Max content chars per depth level for LLM prompt
DEPTH_CONTENT_LIMITS: Dict[AnalysisDepth, int] = {
    AnalysisDepth.QUICK: 8_000,
    AnalysisDepth.STANDARD: 32_000,
    AnalysisDepth.DEEP: 64_000,
}

# Target output tokens per depth level
DEPTH_TOKEN_TARGETS: Dict[AnalysisDepth, int] = {
    AnalysisDepth.QUICK: 500,
    AnalysisDepth.STANDARD: 2_000,
    AnalysisDepth.DEEP: 4_000,
}


class InvestigationStatus(Enum):
    """Status of an investigation."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ExtractionResult:
    """Raw extraction output from a content extractor."""
    content_type: ContentType
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether extraction produced usable text."""
        return bool(self.text.strip()) and self.error is None

    @property
    def word_count(self) -> int:
        """Approximate word count of extracted text."""
        return len(self.text.split()) if self.text else 0

    def truncate_for_depth(self, depth: AnalysisDepth) -> str:
        """Return text truncated to the depth's character limit."""
        limit = DEPTH_CONTENT_LIMITS.get(depth, 32_000)
        if len(self.text) <= limit:
            return self.text
        return self.text[:limit] + "\n\n[Content truncated...]"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_type": self.content_type.value,
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "date": self.date,
            "text": self.text,
            "word_count": self.word_count,
            "metadata": self.metadata,
            "error": self.error,
        }


@dataclass
class Investigation:
    """A completed (or in-progress) URL investigation."""
    id: str
    url: str
    user_id: str
    content_type: ContentType
    depth: AnalysisDepth
    status: InvestigationStatus
    title: Optional[str] = None
    source_author: Optional[str] = None
    source_date: Optional[str] = None
    extracted_text: str = ""
    analysis: str = ""
    key_points: List[str] = field(default_factory=list)
    model_used: Optional[str] = None
    tokens_used: int = 0
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        url: str,
        user_id: str,
        content_type: ContentType,
        depth: AnalysisDepth = AnalysisDepth.STANDARD,
    ) -> "Investigation":
        """Factory method to create a new investigation."""
        return cls(
            id=f"inv-{uuid4().hex[:12]}",
            url=url,
            user_id=user_id,
            content_type=content_type,
            depth=depth,
            status=InvestigationStatus.PENDING,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "url": self.url,
            "content_type": self.content_type.value,
            "depth": self.depth.value,
            "status": self.status.value,
            "title": self.title,
            "source_author": self.source_author,
            "source_date": self.source_date,
            "analysis": self.analysis,
            "key_points": self.key_points,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "word_count": len(self.extracted_text.split()) if self.extracted_text else 0,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Investigation":
        """Create from dictionary."""
        key_points = data.get("key_points", [])
        if isinstance(key_points, str):
            try:
                key_points = json.loads(key_points)
            except (json.JSONDecodeError, ValueError):
                key_points = []

        metadata = data.get("extraction_metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, ValueError):
                metadata = {}

        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        return cls(
            id=data["id"],
            url=data["url"],
            user_id=data.get("user_id", "default"),
            content_type=ContentType(data["content_type"]),
            depth=AnalysisDepth(data["depth"]),
            status=InvestigationStatus(data["status"]),
            title=data.get("title"),
            source_author=data.get("source_author"),
            source_date=data.get("source_date"),
            extracted_text=data.get("extracted_text", ""),
            analysis=data.get("analysis", ""),
            key_points=key_points,
            model_used=data.get("model_used"),
            tokens_used=data.get("tokens_used", 0),
            extraction_metadata=metadata,
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=completed_at,
            error=data.get("error"),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple for INSERT."""
        return (
            self.id,
            self.url,
            self.user_id,
            self.content_type.value,
            self.depth.value,
            self.status.value,
            self.title,
            self.source_author,
            self.source_date,
            self.extracted_text,
            self.analysis,
            json.dumps(self.key_points),
            self.model_used,
            self.tokens_used,
            json.dumps(self.extraction_metadata) if self.extraction_metadata else None,
            self.created_at.isoformat(),
            self.completed_at.isoformat() if self.completed_at else None,
            self.error,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "Investigation":
        """Create from SQLite row (dict)."""
        return cls.from_dict(dict(row))
