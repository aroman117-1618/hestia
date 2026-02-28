"""
Response cache for Hestia orchestration.

In-memory TTL cache for repeated queries. Reduces unnecessary cloud API calls
by returning cached responses when the same question is asked in the same
conversation context.

Cache scope:
- Only TEXT responses are cached (no tool-call results, which reflect live data).
- force_local messages bypass the cache entirely.
- Cache resets on server restart (intentional — stale responses are worse than cache misses).
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.orchestration.models import Conversation


@dataclass
class CacheEntry:
    """A single cached response."""
    content: str
    tokens_in: int
    tokens_out: int
    created_at: float = field(default_factory=time.monotonic)
    hits: int = 0


class ResponseCache:
    """
    Thread-safe in-memory response cache with TTL.

    Only caches plain TEXT responses with no tool calls.
    Cache key is derived from the normalized message + recent conversation context.
    """

    DEFAULT_TTL_SECONDS: int = 3600  # 1 hour
    MAX_ENTRIES: int = 500

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self.logger = get_logger()

    def _make_key(self, message: str, context_hash: str) -> str:
        """SHA-256 of normalized message + context."""
        raw = f"{message.strip().lower()}|{context_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _context_hash(self, conversation: Optional[Conversation]) -> str:
        """Hash recent conversation turns as context fingerprint."""
        if conversation is None or not conversation.messages:
            return "empty"
        # Use last 3 turns' content for context stability
        recent = conversation.messages[-6:]  # 3 pairs of user+assistant
        parts = [turn.get("content", "")[:100] for turn in recent]
        raw = "|".join(parts)
        return hashlib.md5(raw.encode()).hexdigest()[:8]

    async def get(
        self,
        message: str,
        conversation: Optional[Conversation] = None,
    ) -> Optional[CacheEntry]:
        """Return a cached entry if valid, else None."""
        key = self._make_key(message, self._context_hash(conversation))
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() - entry.created_at > self._ttl:
                del self._store[key]
                return None
            entry.hits += 1
            return entry

    async def put(
        self,
        message: str,
        conversation: Optional[Conversation],
        content: str,
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        """Store a response in cache."""
        if len(self._store) >= self.MAX_ENTRIES:
            await self._evict_oldest()
        key = self._make_key(message, self._context_hash(conversation))
        async with self._lock:
            self._store[key] = CacheEntry(
                content=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        self.logger.debug(
            "Response cached",
            component=LogComponent.ORCHESTRATION,
            data={"key_prefix": key[:8], "store_size": len(self._store)},
        )

    async def _evict_oldest(self) -> None:
        """Remove the oldest 10% of entries."""
        async with self._lock:
            sorted_keys = sorted(
                self._store.keys(),
                key=lambda k: self._store[k].created_at,
            )
            evict_count = max(1, len(sorted_keys) // 10)
            for k in sorted_keys[:evict_count]:
                del self._store[k]


# Module-level singleton
_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get or create the singleton response cache."""
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache
