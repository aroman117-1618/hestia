"""
Data models for the Wiki module.

Wiki articles representing architecture documentation —
overview narratives, module deep dives, ADR cards,
roadmap milestones, and Mermaid diagrams.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class ArticleType(Enum):
    """Types of wiki articles."""
    OVERVIEW = "overview"
    MODULE = "module"
    DECISION = "decision"
    ROADMAP = "roadmap"
    DIAGRAM = "diagram"


@dataclass
class WikiRoadmapMilestone:
    """A single milestone within a roadmap group."""
    id: str
    title: str
    status: str
    scope: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "scope": self.scope,
        }


@dataclass
class WikiRoadmapMilestoneGroup:
    """A group of milestones (e.g., a sprint or phase)."""
    id: str
    title: str
    order: int
    milestones: list

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "order": self.order,
            "milestones": [m.to_dict() for m in self.milestones],
        }


class GenerationStatus(Enum):
    """Status of AI-generated content."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"
    STATIC = "static"  # Not AI-generated (decisions, roadmap)


@dataclass
class WikiArticle:
    """
    A single wiki article.

    Attributes:
        id: Unique article identifier (e.g., "overview", "module-memory").
        article_type: Type of article content.
        title: Display title.
        subtitle: Short description.
        content: Markdown body (or Mermaid source for diagrams).
        module_name: Module identifier (MODULE type only).
        source_hash: SHA256 of source material at generation time.
        generation_status: Current status of content generation.
        generated_at: When content was last generated.
        generation_model: Which model generated this content.
        word_count: Number of words in content.
        estimated_read_time: Estimated reading time in minutes.
    """
    id: str
    article_type: ArticleType
    title: str
    subtitle: str = ""
    content: str = ""
    module_name: Optional[str] = None
    source_hash: Optional[str] = None
    generation_status: GenerationStatus = GenerationStatus.PENDING
    generated_at: Optional[datetime] = None
    generation_model: Optional[str] = None
    word_count: int = 0
    estimated_read_time: int = 0
    last_trigger_source: str = "manual"
    regeneration_count: int = 0

    @classmethod
    def create(
        cls,
        article_type: ArticleType,
        title: str,
        subtitle: str = "",
        content: str = "",
        module_name: Optional[str] = None,
        source_hash: Optional[str] = None,
        generation_status: GenerationStatus = GenerationStatus.PENDING,
        generation_model: Optional[str] = None,
        last_trigger_source: str = "manual",
        regeneration_count: int = 0,
    ) -> "WikiArticle":
        """Factory method to create a new wiki article."""
        # Generate ID based on type
        if article_type == ArticleType.MODULE and module_name:
            article_id = f"module-{module_name}"
        elif article_type == ArticleType.DECISION and module_name:
            article_id = f"decision-{module_name}"
        elif article_type == ArticleType.DIAGRAM and module_name:
            article_id = f"diagram-{module_name}"
        else:
            article_id = article_type.value

        word_count = len(content.split()) if content else 0
        read_time = max(1, word_count // 200)  # ~200 wpm reading speed

        return cls(
            id=article_id,
            article_type=article_type,
            title=title,
            subtitle=subtitle,
            content=content,
            module_name=module_name,
            source_hash=source_hash,
            generation_status=generation_status,
            generated_at=datetime.now(timezone.utc) if content else None,
            generation_model=generation_model,
            word_count=word_count,
            estimated_read_time=read_time,
            last_trigger_source=last_trigger_source,
            regeneration_count=regeneration_count,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "article_type": self.article_type.value,
            "title": self.title,
            "subtitle": self.subtitle,
            "content": self.content,
            "module_name": self.module_name,
            "source_hash": self.source_hash,
            "generation_status": self.generation_status.value,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "generation_model": self.generation_model,
            "word_count": self.word_count,
            "estimated_read_time": self.estimated_read_time,
            "last_trigger_source": self.last_trigger_source,
            "regeneration_count": self.regeneration_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WikiArticle":
        """Create from dictionary."""
        generated_at = None
        if data.get("generated_at"):
            generated_at = datetime.fromisoformat(data["generated_at"])

        return cls(
            id=data["id"],
            article_type=ArticleType(data["article_type"]),
            title=data["title"],
            subtitle=data.get("subtitle", ""),
            content=data.get("content", ""),
            module_name=data.get("module_name"),
            source_hash=data.get("source_hash"),
            generation_status=GenerationStatus(data.get("generation_status", "pending")),
            generated_at=generated_at,
            generation_model=data.get("generation_model"),
            word_count=data.get("word_count", 0),
            estimated_read_time=data.get("estimated_read_time", 0),
            last_trigger_source=data.get("last_trigger_source", "manual"),
            regeneration_count=data.get("regeneration_count", 0),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.article_type.value,
            self.title,
            self.subtitle,
            self.content,
            self.module_name,
            self.source_hash,
            self.generation_status.value,
            self.generated_at.isoformat() if self.generated_at else None,
            self.generation_model,
            self.word_count,
            self.estimated_read_time,
            self.last_trigger_source,
            self.regeneration_count,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "WikiArticle":
        """Create from SQLite row (dict)."""
        generated_at = None
        if row.get("generated_at"):
            try:
                generated_at = datetime.fromisoformat(row["generated_at"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=row["id"],
            article_type=ArticleType(row["article_type"]),
            title=row["title"],
            subtitle=row.get("subtitle", ""),
            content=row.get("content", ""),
            module_name=row.get("module_name"),
            source_hash=row.get("source_hash"),
            generation_status=GenerationStatus(row.get("generation_status", "pending")),
            generated_at=generated_at,
            generation_model=row.get("generation_model"),
            word_count=row.get("word_count", 0),
            estimated_read_time=row.get("estimated_read_time", 0),
            last_trigger_source=row.get("last_trigger_source", "manual"),
            regeneration_count=row.get("regeneration_count", 0),
        )
