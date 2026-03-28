"""Memory bridge for the Hestia Agentic Development System.

Provides dev-specific memory storage and retrieval by wrapping the existing
MemoryManager with structured dev memory types (session summaries, technical
learnings, failure patterns, codebase invariants).
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, List

from hestia.logging import get_logger, LogComponent

logger = get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """Dev-specific memory type tags injected into stored content."""

    SESSION_SUMMARY = "dev_session_summary"
    TECHNICAL_LEARNING = "dev_technical_learning"
    FAILURE_PATTERN = "dev_failure_pattern"
    CODEBASE_INVARIANT = "dev_codebase_invariant"


# ---------------------------------------------------------------------------
# DevMemoryBridge
# ---------------------------------------------------------------------------

class DevMemoryBridge:
    """Bridge between the Agentic Dev System and Hestia's MemoryManager.

    Stores structured dev memories using the existing memory pipeline and
    provides retrieval methods tailored to each agent tier (Architect,
    Engineer, Researcher).
    """

    def __init__(self, memory_manager: Any) -> None:
        """Initialize with an existing MemoryManager instance.

        Args:
            memory_manager: An initialized MemoryManager instance.
        """
        self._memory = memory_manager

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def store_session_summary(
        self,
        session_id: str,
        title: str,
        description: str,
        files_changed: List[str],
        key_decisions: List[str],
    ) -> None:
        """Store a dev session summary in memory.

        Args:
            session_id: Unique identifier for the dev session.
            title: Short title of the session.
            description: Longer description of what the session accomplished.
            files_changed: List of file paths modified during the session.
            key_decisions: Significant architectural or implementation decisions made.
        """
        user_message = f"[DEV SESSION SUMMARY] session_id={session_id} title={title}"
        assistant_message = (
            f"[DEV SESSION SUMMARY]\n"
            f"Session: {session_id}\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Files changed: {', '.join(files_changed)}\n"
            f"Key decisions: {'; '.join(key_decisions)}"
        )
        await self._memory.store_exchange(
            user_message=user_message,
            assistant_message=assistant_message,
            metadata={
                "memory_type": MemoryType.SESSION_SUMMARY.value,
                "session_id": session_id,
            },
        )
        logger.info(
            f"Stored session summary for {session_id}",
            component=LogComponent.DEV,
            data={"session_id": session_id, "title": title},
        )

    async def store_technical_learning(
        self,
        session_id: str,
        file_path: str,
        learning: str,
        file_content_hash: str,
    ) -> None:
        """Store a technical learning tied to a specific file.

        The file_content_hash is stored so callers can detect whether the
        file has changed (making the learning potentially stale).

        Args:
            session_id: Unique identifier for the dev session.
            file_path: Path to the file this learning concerns.
            learning: The insight or pattern learned about the file/code.
            file_content_hash: sha256 hex[:16] of the file at learning time.
        """
        user_message = (
            f"[DEV TECHNICAL LEARNING] session_id={session_id} file={file_path}"
        )
        assistant_message = (
            f"[DEV TECHNICAL LEARNING]\n"
            f"Session: {session_id}\n"
            f"File: {file_path}\n"
            f"File hash: {file_content_hash}\n"
            f"Learning: {learning}"
        )
        await self._memory.store_exchange(
            user_message=user_message,
            assistant_message=assistant_message,
            metadata={
                "memory_type": MemoryType.TECHNICAL_LEARNING.value,
                "session_id": session_id,
                "file_path": file_path,
                "file_hash": file_content_hash,
            },
        )
        logger.info(
            f"Stored technical learning for {file_path}",
            component=LogComponent.DEV,
            data={"session_id": session_id, "file_path": file_path},
        )

    async def store_failure_pattern(
        self,
        session_id: str,
        approach: str,
        failure_reason: str,
        resolution: str,
    ) -> None:
        """Store a recorded failure pattern and its resolution.

        Args:
            session_id: Unique identifier for the dev session.
            approach: The approach or technique that failed.
            failure_reason: Why the approach failed.
            resolution: How the failure was resolved or worked around.
        """
        user_message = (
            f"[DEV FAILURE PATTERN] session_id={session_id} approach={approach}"
        )
        assistant_message = (
            f"[DEV FAILURE PATTERN]\n"
            f"Session: {session_id}\n"
            f"Approach: {approach}\n"
            f"Failure reason: {failure_reason}\n"
            f"Resolution: {resolution}"
        )
        await self._memory.store_exchange(
            user_message=user_message,
            assistant_message=assistant_message,
            metadata={
                "memory_type": MemoryType.FAILURE_PATTERN.value,
                "session_id": session_id,
            },
        )
        logger.info(
            f"Stored failure pattern for session {session_id}",
            component=LogComponent.DEV,
            data={"session_id": session_id, "approach": approach},
        )

    async def store_codebase_invariant(
        self,
        invariant: str,
        discovered_in: str,
    ) -> None:
        """Store a codebase invariant — an always-inject rule for all agents.

        Invariants are rules that must always be respected regardless of the
        task, such as naming conventions, prohibited patterns, or required
        boilerplate.

        Args:
            invariant: The rule or constraint that must always be observed.
            discovered_in: Session ID or context where the invariant was found.
        """
        user_message = f"[DEV CODEBASE INVARIANT] discovered_in={discovered_in}"
        assistant_message = (
            f"[DEV CODEBASE INVARIANT]\n"
            f"Discovered in: {discovered_in}\n"
            f"Invariant: {invariant}"
        )
        await self._memory.store_exchange(
            user_message=user_message,
            assistant_message=assistant_message,
            metadata={
                "memory_type": MemoryType.CODEBASE_INVARIANT.value,
                "discovered_in": discovered_in,
            },
        )
        logger.info(
            "Stored codebase invariant",
            component=LogComponent.DEV,
            data={"discovered_in": discovered_in},
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve_for_architect(self, task_description: str) -> str:
        """Retrieve relevant memory for the Architect tier via semantic search.

        Args:
            task_description: Description of the task the Architect is planning.

        Returns:
            Context string assembled from semantically matched memories.
        """
        return await self._memory.build_context(
            query=f"[DEV] {task_description}",
        )

    async def retrieve_for_engineer(self, file_paths: List[str]) -> str:
        """Retrieve relevant memory for the Engineer tier via tag-based lookup.

        Args:
            file_paths: List of file paths the Engineer will be working on.

        Returns:
            Context string assembled from memories tagged to those files.
        """
        query = f"[DEV TECHNICAL LEARNING] files: {' '.join(file_paths)}"
        return await self._memory.build_context(query=query)

    async def retrieve_for_researcher(self, topic: str) -> str:
        """Retrieve relevant memory for the Researcher tier.

        Args:
            topic: The research topic or area of investigation.

        Returns:
            Context string assembled from semantically matched memories.
        """
        return await self._memory.build_context(
            query=f"[DEV] research topic: {topic}",
        )

    async def retrieve_invariants(self) -> str:
        """Retrieve all stored codebase invariants.

        Returns:
            Context string containing all known codebase invariants.
        """
        return await self._memory.build_context(
            query="[DEV CODEBASE INVARIANT]",
        )

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_file_hash(content: str) -> str:
        """Compute a short sha256 hash of file content for staleness detection.

        Args:
            content: The full text content of the file.

        Returns:
            First 16 hex characters of the sha256 digest.
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]
