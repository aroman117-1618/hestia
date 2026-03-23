"""
Principle Store — ChromaDB-backed storage for distilled interaction principles.

Uses a dedicated `hestia_principles` collection (separate from `hestia_memory`)
to avoid namespace collisions (audit requirement).

Principles are distilled from memory chunks via LLM and stored with embeddings
for semantic search. All new principles start as "pending" and require user
approval before influencing downstream systems.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase
from .models import Principle, PrincipleStatus

logger = get_logger()

COLLECTION_NAME = "hestia_principles"

# Distillation prompt template — source-aware (Sprint 11.5 A7)
DISTILLATION_PROMPT = """Analyze these conversation excerpts and extract reusable behavioral principles about the user.
Focus on: communication preferences, workflow patterns, decision-making style, recurring needs.
Output format: One principle per line, prefixed with [domain].
When a principle is derived from a specific source (email, calendar, reminder), cite it.

Examples:
[scheduling] User prefers morning meetings summarized in bullet points
[coding] User wants tests written before implementation (from conversation on 2026-01-15)
[health] User tracks sleep quality and correlates with productivity (from health data)
[communication] User responds to emails within 2 hours during work hours (from email patterns)

Conversation excerpts:
{excerpts}

Extracted principles:"""


class PrincipleStore:
    """
    Manages distilled principles with ChromaDB embeddings + SQLite metadata.

    ChromaDB stores embeddings for semantic search.
    SQLite (via ResearchDatabase) stores structured metadata and status lifecycle.
    Thread-safe via asyncio.Lock on initialization.
    """

    def __init__(self, database: ResearchDatabase) -> None:
        self._database = database
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None
        self._init_lock = asyncio.Lock()
        self._initialized = False

    def initialize(self, persist_directory: Optional[Path] = None) -> None:
        """Initialize ChromaDB client and collection."""
        if persist_directory is None:
            persist_directory = Path.home() / "hestia" / "data" / "chromadb"

        persist_directory.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        self._initialized = True
        logger.info(
            f"PrincipleStore initialized: {persist_directory}",
            component=LogComponent.RESEARCH,
            data={
                "collection": COLLECTION_NAME,
                "count": self._collection.count(),
            },
        )

    async def ensure_initialized(self, persist_directory: Optional[Path] = None) -> None:
        """Async-safe initialization guard. Concurrent calls will not race."""
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            self.initialize(persist_directory)

    async def store_principle(self, principle: Principle) -> Principle:
        """
        Store a new principle in both SQLite and ChromaDB.

        The principle is stored with status="pending" (enforced by model default).
        ChromaDB auto-generates embeddings from the content.
        """
        # SQLite first (structured metadata)
        await self._database.create_principle(principle)

        # ChromaDB (embeddings for semantic search)
        if self._collection is not None:
            self._collection.upsert(
                ids=[principle.id],
                documents=[principle.content],
                metadatas=[{
                    "domain": principle.domain,
                    "status": principle.status.value,
                    "confidence": principle.confidence,
                }],
            )

        logger.info(
            "Principle stored",
            component=LogComponent.RESEARCH,
            data={"id": principle.id, "domain": principle.domain},
        )
        return principle

    async def find_duplicate(
        self, content: str, threshold: float = 0.85
    ) -> Optional[Principle]:
        """Check if a semantically similar principle already exists.

        Uses ChromaDB cosine distance (1 - similarity). Returns the most similar
        principle if distance < (1 - threshold), else None.

        Prevents principle queue bloat from repeated corrections or outcomes that
        trigger the same behavioral pattern across multiple weekly batches.
        """
        if self._collection is None or self._collection.count() == 0:
            return None

        results = self._collection.query(
            query_texts=[content],
            n_results=1,
        )

        if (
            not results
            or not results["ids"]
            or not results["ids"][0]
            or not results["distances"]
            or not results["distances"][0]
        ):
            return None

        distance = results["distances"][0][0]
        # ChromaDB cosine space: distance = 1 - cosine_similarity
        if distance < (1.0 - threshold):
            principle_id = results["ids"][0][0]
            return await self._database.get_principle(principle_id)

        return None

    async def search_principles(
        self, query: str, limit: int = 10, min_confidence: float = 0.0
    ) -> List[Principle]:
        """Search principles by semantic similarity."""
        if self._collection is None or self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, self._collection.count()),
            where={"confidence": {"$gte": min_confidence}} if min_confidence > 0 else None,
        )

        if not results or not results["ids"] or not results["ids"][0]:
            return []

        # Fetch full principle data from SQLite
        principles = []
        for principle_id in results["ids"][0]:
            p = await self._database.get_principle(principle_id)
            if p:
                principles.append(p)

        return principles

    async def distill_principles(
        self,
        memory_chunks: List[Any],
        inference_client: Optional[Any] = None,
    ) -> List[Principle]:
        """
        Distill principles from memory chunks using LLM.

        Args:
            memory_chunks: List of memory search results to analyze.
            inference_client: InferenceClient for LLM calls. If None, uses lazy import.

        Returns:
            List of newly created Principle objects (all with status="pending").
        """
        if not memory_chunks:
            return []

        # Build excerpts for the prompt
        excerpts = []
        source_chunk_ids = []
        all_topics: List[str] = []
        all_entities: List[str] = []

        # Keep prompt compact to stay on PRIMARY model tier (<500 tokens)
        # and avoid expensive model swaps on resource-constrained hardware.
        # Distill in small batches; callers can invoke multiple times for coverage.
        for result in memory_chunks[:5]:
            chunk = result.chunk
            source_label = f" ({chunk.metadata.source})" if chunk.metadata and chunk.metadata.source else ""
            date_label = f" [{chunk.timestamp.strftime('%Y-%m-%d')}]" if chunk.timestamp else ""
            excerpts.append(
                f"[{chunk.chunk_type.value}]{source_label}{date_label} {chunk.content[:150]}"
            )
            source_chunk_ids.append(chunk.id)
            if chunk.tags:
                all_topics.extend(chunk.tags.topics)
                all_entities.extend(chunk.tags.entities)

        prompt = DISTILLATION_PROMPT.format(excerpts="\n".join(excerpts))

        # Call LLM
        if inference_client is None:
            try:
                from hestia.inference import get_inference_client
                inference_client = get_inference_client()
            except Exception as e:
                logger.warning(
                    f"Cannot get inference client for distillation: {type(e).__name__}",
                    component=LogComponent.RESEARCH,
                )
                return []

        try:
            from hestia.inference import Message
            messages = [
                Message(role="system", content="You are analyzing user interactions to extract behavioral principles."),
                Message(role="user", content=prompt),
            ]
            # Try cloud first (local models struggle with long distillation prompts),
            # fall back to local if cloud unavailable
            try:
                inference_response = await inference_client.chat(
                    messages=messages,
                    max_tokens=1000,
                    force_cloud=True,
                )
            except Exception:
                inference_response = await inference_client.chat(
                    messages=messages,
                    max_tokens=1000,
                )
            response = inference_response.content
        except Exception as e:
            logger.warning(
                f"Principle distillation LLM call failed: {type(e).__name__}: {e}",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__, "detail": str(e)[:200]},
            )
            return []

        # Parse response into principles
        principles = self._parse_distillation_response(
            response, source_chunk_ids, all_topics, all_entities
        )

        # Store each principle
        stored = []
        for p in principles:
            try:
                await self.store_principle(p)
                stored.append(p)
            except Exception as e:
                logger.warning(
                    f"Failed to store principle: {type(e).__name__}",
                    component=LogComponent.RESEARCH,
                )

        logger.info(
            "Distillation complete",
            component=LogComponent.RESEARCH,
            data={"input_chunks": len(memory_chunks), "principles_extracted": len(stored)},
        )
        return stored

    def _parse_distillation_response(
        self,
        response: str,
        source_chunk_ids: List[str],
        topics: List[str],
        entities: List[str],
    ) -> List[Principle]:
        """Parse LLM distillation output into Principle objects."""
        principles = []
        unique_topics = list(set(t.lower() for t in topics))[:10]
        unique_entities = list(set(e.lower() for e in entities))[:10]

        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or len(line) < 10:
                continue

            # Extract domain from [domain] prefix
            domain = "general"
            if line.startswith("[") and "]" in line:
                bracket_end = line.index("]")
                domain = line[1:bracket_end].strip().lower()
                content = line[bracket_end + 1:].strip()
            else:
                content = line

            if content:
                principles.append(Principle.create(
                    content=content,
                    domain=domain,
                    confidence=0.5,
                    source_chunk_ids=source_chunk_ids[:10],
                    topics=unique_topics,
                    entities=unique_entities,
                ))

        return principles

    async def get_approved_principles(self, limit: int = 50) -> List[Principle]:
        """Get approved principles for graph integration."""
        return await self._database.list_principles(
            status=PrincipleStatus.APPROVED,
            limit=limit,
        )

    def get_collection_count(self) -> int:
        """Get the number of principles in ChromaDB."""
        if self._collection is None:
            return 0
        return self._collection.count()
