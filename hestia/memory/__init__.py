"""
Memory module for Hestia.

Provides conversation history storage and retrieval with:
- Hybrid storage: SQLite (structured) + ChromaDB (vectors)
- Tag-based metadata (ADR-013)
- Governed memory persistence (ADR-002)
- Semantic + temporal + categorical search
"""

from hestia.memory.models import (
    ConversationChunk,
    ChunkTags,
    ChunkMetadata,
    ChunkType,
    MemoryScope,
    MemoryStatus,
    MemoryQuery,
    MemorySearchResult,
)

from hestia.memory.database import MemoryDatabase, get_database
from hestia.memory.vector_store import VectorStore, get_vector_store
from hestia.memory.tagger import AutoTagger, get_tagger
from hestia.memory.manager import MemoryManager, get_memory_manager

__all__ = [
    # Models
    "ConversationChunk",
    "ChunkTags",
    "ChunkMetadata",
    "ChunkType",
    "MemoryScope",
    "MemoryStatus",
    "MemoryQuery",
    "MemorySearchResult",
    # Database
    "MemoryDatabase",
    "get_database",
    # Vector Store
    "VectorStore",
    "get_vector_store",
    # Tagger
    "AutoTagger",
    "get_tagger",
    # Manager
    "MemoryManager",
    "get_memory_manager",
]
