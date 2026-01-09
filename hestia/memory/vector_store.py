"""
ChromaDB vector store for Hestia memory.

Handles embedding storage and semantic similarity search.
Works alongside SQLite for structured metadata.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import chromadb
from chromadb.config import Settings

from hestia.logging import get_logger, LogComponent
from hestia.memory.models import ConversationChunk


class VectorStore:
    """
    ChromaDB-backed vector store for semantic search.

    Uses ChromaDB's built-in embedding function (all-MiniLM-L6-v2)
    for generating embeddings from text.
    """

    COLLECTION_NAME = "hestia_memory"

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
    ):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory for ChromaDB persistence.
                Defaults to ~/hestia/data/chromadb
        """
        if persist_directory is None:
            persist_directory = Path.home() / "hestia" / "data" / "chromadb"

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.logger = get_logger()
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None

    def connect(self) -> None:
        """Initialize ChromaDB client and collection."""
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Get or create collection with default embedding function
        # ChromaDB uses all-MiniLM-L6-v2 by default
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

        self.logger.info(
            f"Vector store connected: {self.persist_directory}",
            component=LogComponent.MEMORY,
            data={
                "persist_dir": str(self.persist_directory),
                "collection": self.COLLECTION_NAME,
                "count": self._collection.count()
            }
        )

    def close(self) -> None:
        """Close vector store connection."""
        # ChromaDB persists automatically, no explicit close needed
        self._client = None
        self._collection = None

    def __enter__(self) -> "VectorStore":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def collection(self) -> chromadb.Collection:
        """Get the ChromaDB collection."""
        if self._collection is None:
            raise RuntimeError("Vector store not connected")
        return self._collection

    def add_chunk(
        self,
        chunk: ConversationChunk,
        embedding: Optional[List[float]] = None
    ) -> None:
        """
        Add a chunk to the vector store.

        If no embedding is provided, ChromaDB will generate one
        using its default embedding function.

        Args:
            chunk: The conversation chunk to add.
            embedding: Optional pre-computed embedding.
        """
        metadata = {
            "session_id": chunk.session_id,
            "timestamp": chunk.timestamp.isoformat(),
            "chunk_type": chunk.chunk_type.value,
            "scope": chunk.scope.value,
            "status": chunk.status.value,
        }

        # Add some tags to metadata for filtering
        if chunk.tags.topics:
            metadata["topics"] = ",".join(chunk.tags.topics)
        if chunk.tags.mode:
            metadata["mode"] = chunk.tags.mode

        if embedding:
            self.collection.add(
                ids=[chunk.id],
                embeddings=[embedding],
                documents=[chunk.content],
                metadatas=[metadata]
            )
        else:
            # Let ChromaDB compute the embedding
            self.collection.add(
                ids=[chunk.id],
                documents=[chunk.content],
                metadatas=[metadata]
            )

        self.logger.debug(
            f"Added chunk to vector store: {chunk.id}",
            component=LogComponent.MEMORY,
            data={"chunk_id": chunk.id}
        )

    def add_chunks(
        self,
        chunks: List[ConversationChunk],
        embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """
        Add multiple chunks to the vector store.

        Args:
            chunks: List of chunks to add.
            embeddings: Optional list of pre-computed embeddings.
        """
        if not chunks:
            return

        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "session_id": c.session_id,
                "timestamp": c.timestamp.isoformat(),
                "chunk_type": c.chunk_type.value,
                "scope": c.scope.value,
                "status": c.status.value,
                "topics": ",".join(c.tags.topics) if c.tags.topics else "",
                "mode": c.tags.mode or "",
            }
            for c in chunks
        ]

        if embeddings:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
        else:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

        self.logger.debug(
            f"Added {len(chunks)} chunks to vector store",
            component=LogComponent.MEMORY
        )

    def search(
        self,
        query: str,
        n_results: int = 10,
        min_score: float = 0.0,
        where: Optional[dict] = None,
    ) -> List[Tuple[str, float]]:
        """
        Search for similar chunks.

        Args:
            query: The search query text.
            n_results: Maximum number of results.
            min_score: Minimum similarity score (0-1, higher is more similar).
            where: Optional ChromaDB where filter.

        Returns:
            List of (chunk_id, score) tuples, sorted by score descending.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["distances"]
        )

        # Convert distances to similarity scores
        # ChromaDB returns cosine distance (0 = identical, 2 = opposite)
        # Convert to similarity: 1 - (distance / 2)
        chunk_scores = []

        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            distances = results["distances"][0] if results["distances"] else [0] * len(ids)

            for chunk_id, distance in zip(ids, distances):
                # Convert cosine distance to similarity score
                score = 1 - (distance / 2)
                if score >= min_score:
                    chunk_scores.append((chunk_id, score))

        # Sort by score descending
        chunk_scores.sort(key=lambda x: x[1], reverse=True)

        self.logger.debug(
            f"Vector search: '{query[:50]}...' returned {len(chunk_scores)} results",
            component=LogComponent.MEMORY,
            data={"query_preview": query[:50], "result_count": len(chunk_scores)}
        )

        return chunk_scores

    def search_by_embedding(
        self,
        embedding: List[float],
        n_results: int = 10,
        min_score: float = 0.0,
        where: Optional[dict] = None,
    ) -> List[Tuple[str, float]]:
        """
        Search using a pre-computed embedding.

        Args:
            embedding: The query embedding vector.
            n_results: Maximum number of results.
            min_score: Minimum similarity score.
            where: Optional ChromaDB where filter.

        Returns:
            List of (chunk_id, score) tuples.
        """
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["distances"]
        )

        chunk_scores = []

        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            distances = results["distances"][0] if results["distances"] else [0] * len(ids)

            for chunk_id, distance in zip(ids, distances):
                score = 1 - (distance / 2)
                if score >= min_score:
                    chunk_scores.append((chunk_id, score))

        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        return chunk_scores

    def delete_chunk(self, chunk_id: str) -> None:
        """Delete a chunk from the vector store."""
        self.collection.delete(ids=[chunk_id])

    def delete_chunks(self, chunk_ids: List[str]) -> None:
        """Delete multiple chunks from the vector store."""
        if chunk_ids:
            self.collection.delete(ids=chunk_ids)

    def update_chunk(
        self,
        chunk: ConversationChunk,
        embedding: Optional[List[float]] = None
    ) -> None:
        """
        Update a chunk in the vector store.

        Args:
            chunk: The updated chunk.
            embedding: Optional new embedding.
        """
        metadata = {
            "session_id": chunk.session_id,
            "timestamp": chunk.timestamp.isoformat(),
            "chunk_type": chunk.chunk_type.value,
            "scope": chunk.scope.value,
            "status": chunk.status.value,
            "topics": ",".join(chunk.tags.topics) if chunk.tags.topics else "",
            "mode": chunk.tags.mode or "",
        }

        if embedding:
            self.collection.update(
                ids=[chunk.id],
                embeddings=[embedding],
                documents=[chunk.content],
                metadatas=[metadata]
            )
        else:
            self.collection.update(
                ids=[chunk.id],
                documents=[chunk.content],
                metadatas=[metadata]
            )

    def get_embedding(self, chunk_id: str) -> Optional[List[float]]:
        """Get the embedding for a chunk."""
        results = self.collection.get(
            ids=[chunk_id],
            include=["embeddings"]
        )

        if results["embeddings"] and results["embeddings"][0]:
            return results["embeddings"][0]
        return None

    def count(self) -> int:
        """Get the total number of chunks in the store."""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all chunks from the store."""
        if self._client:
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )


# Module-level singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        _vector_store.connect()
    return _vector_store
