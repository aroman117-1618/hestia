# OpenAI History Parser + Dry-Run Review Tool

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an OpenAI/ChatGPT history parser and dry-run review pipeline that outputs proposed memory chunks for human review without committing anything to the memory system.

**Architecture:** New `openai.py` parser mirrors the Claude importer pattern (DAG flattener, turn extractor, credential stripper, chunker). Pipeline extension adds `dry_run_openai_history()` that outputs proposed chunks with projected importance scores to a JSON review file. All chunks typed as OBSERVATION (no DECISION/PREFERENCE promotion). Hestia-related conversations excluded via configurable keyword filter.

**Tech Stack:** Python 3.12, existing memory models (ConversationChunk, ChunkType, MemorySource), pytest

---

### Task 1: OpenAI Parser — Core Module

**Files:**
- Create: `hestia/memory/importers/openai.py`
- Test: `tests/test_import_openai.py`

- [ ] **Step 1: Write failing test for DAG flattening**

```python
# tests/test_import_openai.py
"""Tests for OpenAI/ChatGPT conversation history import."""
import pytest
from datetime import datetime, timezone

from hestia.memory.importers.openai import (
    OpenAIHistoryParser,
    flatten_message_dag,
    MAX_CHUNK_CHARS,
)
from hestia.memory.models import ChunkType, MemoryScope


# ChatGPT export uses a mapping dict with parent/children pointers
SAMPLE_LINEAR_CONVERSATION = {
    "title": "Python debugging help",
    "create_time": 1700000000.0,  # Unix float
    "update_time": 1700001000.0,
    "current_node": "msg-003",
    "mapping": {
        "msg-001": {
            "id": "msg-001",
            "parent": None,
            "children": ["msg-002"],
            "message": {
                "id": "msg-001",
                "role": "system",
                "content": {"content_type": "text", "parts": ["You are ChatGPT."]},
                "create_time": 1700000000.0,
                "metadata": {},
            },
        },
        "msg-002": {
            "id": "msg-002",
            "parent": "msg-001",
            "children": ["msg-003"],
            "message": {
                "id": "msg-002",
                "role": "user",
                "content": {"content_type": "text", "parts": ["How do I debug a Python segfault?"]},
                "create_time": 1700000010.0,
                "metadata": {},
            },
        },
        "msg-003": {
            "id": "msg-003",
            "parent": "msg-002",
            "children": [],
            "message": {
                "id": "msg-003",
                "role": "assistant",
                "content": {"content_type": "text", "parts": ["Use faulthandler module and gdb to trace segfaults."]},
                "create_time": 1700000020.0,
                "metadata": {"model_slug": "gpt-4"},
            },
        },
    },
}


class TestFlattenMessageDAG:
    def test_flattens_linear_thread(self):
        messages = flatten_message_dag(SAMPLE_LINEAR_CONVERSATION["mapping"], "msg-003")
        assert len(messages) == 3
        assert messages[0]["message"]["role"] == "system"
        assert messages[1]["message"]["role"] == "user"
        assert messages[2]["message"]["role"] == "assistant"

    def test_skips_orphan_branches(self):
        """When user edits a message, old branch should be ignored."""
        mapping = {
            **SAMPLE_LINEAR_CONVERSATION["mapping"],
            "msg-branch": {
                "id": "msg-branch",
                "parent": "msg-001",
                "children": [],
                "message": {
                    "id": "msg-branch",
                    "role": "user",
                    "content": {"content_type": "text", "parts": ["This is an old edited branch"]},
                    "create_time": 1700000005.0,
                    "metadata": {},
                },
            },
        }
        # msg-001 now has two children but only msg-002 is on the active path
        mapping["msg-001"]["children"] = ["msg-002", "msg-branch"]
        messages = flatten_message_dag(mapping, "msg-003")
        texts = [m["message"]["content"]["parts"][0] for m in messages]
        assert "old edited branch" not in " ".join(texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestFlattenMessageDAG -v --timeout=30`
Expected: FAIL with "ModuleNotFoundError: No module named 'hestia.memory.importers.openai'"

- [ ] **Step 3: Implement DAG flattener and parser skeleton**

```python
# hestia/memory/importers/openai.py
"""Parser for ChatGPT/OpenAI conversation export data.

Converts ChatGPT's JSON export into memory chunks ready for the
Hestia memory pipeline. Key differences from Claude exports:
- Messages stored as a DAG (mapping dict), not a flat list
- Timestamps are Unix floats, not ISO strings
- No thinking blocks or tool_use metadata
- current_node pointer identifies the active thread leaf
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from hestia.logging import get_logger
from hestia.memory.importers.claude import (
    CREDENTIAL_PATTERNS,
    MAX_CHUNK_CHARS,
    strip_credentials,
)
from hestia.memory.models import (
    ChunkMetadata,
    ChunkTags,
    ChunkType,
    ConversationChunk,
    MemoryScope,
    MemorySource,
)

logger = get_logger()

SOURCE_TAG = MemorySource.OPENAI_HISTORY.value

# Keywords that identify Hestia-related conversations (excluded from dry-run)
HESTIA_KEYWORDS = [
    "hestia", "tia", "mac mini", "ollama", "fastapi",
    "claude code", "hestia-cli", "swiftui", "chromadb",
    "memory pipeline", "council", "orchestrat",
]


def flatten_message_dag(
    mapping: Dict[str, Any], current_node: str
) -> List[Dict[str, Any]]:
    """Walk from current_node to root via parent pointers, return ordered list.

    ChatGPT stores messages as a DAG with parent/children pointers.
    When users edit messages, branches form. We only want the active
    thread: the path from root to current_node.
    """
    if current_node not in mapping:
        return []

    # Walk backward from leaf to root
    path: List[Dict[str, Any]] = []
    node_id: Optional[str] = current_node
    visited: Set[str] = set()

    while node_id and node_id in mapping and node_id not in visited:
        visited.add(node_id)
        node = mapping[node_id]
        path.append(node)
        node_id = node.get("parent")

    # Reverse to get root → leaf order
    path.reverse()
    return path


class OpenAIHistoryParser:
    """Parse ChatGPT exported conversations into ConversationChunks.

    Chunking strategy:
    - Flatten message DAG to active thread
    - Group user+assistant turn pairs
    - Split when accumulated text exceeds MAX_CHUNK_CHARS
    - All chunks typed as OBSERVATION (not DECISION/PREFERENCE)
    - Strip credentials before storage
    - Skip system messages
    """

    def __init__(self, exclude_keywords: Optional[List[str]] = None) -> None:
        self._exclude_keywords = [
            kw.lower() for kw in (exclude_keywords or HESTIA_KEYWORDS)
        ]

    def should_exclude(self, conversation: Dict[str, Any]) -> bool:
        """Check if conversation matches exclusion keywords."""
        title = (conversation.get("title") or "").lower()
        return any(kw in title for kw in self._exclude_keywords)

    def parse_export(
        self,
        conversations: List[Dict[str, Any]],
        exclude_hestia: bool = True,
    ) -> List[ConversationChunk]:
        """Parse a full ChatGPT export into ConversationChunks.

        Args:
            conversations: List of conversation dicts from ChatGPT export.
            exclude_hestia: If True, skip conversations matching Hestia keywords.

        Returns:
            List of ConversationChunks ready for pipeline.
        """
        all_chunks: List[ConversationChunk] = []
        skipped = 0

        for conv in conversations:
            if exclude_hestia and self.should_exclude(conv):
                skipped += 1
                continue
            all_chunks.extend(self.parse_conversation(conv))

        logger.info(
            "Parsed OpenAI export: %d conversations (%d excluded), %d chunks",
            len(conversations), skipped, len(all_chunks),
        )
        return all_chunks

    def parse_conversation(
        self, conv: Dict[str, Any]
    ) -> List[ConversationChunk]:
        """Parse a single ChatGPT conversation into chunks."""
        mapping = conv.get("mapping", {})
        current_node = conv.get("current_node")
        if not mapping or not current_node:
            return []

        # Flatten DAG to active thread
        thread = flatten_message_dag(mapping, current_node)
        if not thread:
            return []

        title = conv.get("title") or "Untitled"
        conv_id = conv.get("id", conv.get("conversation_id", "unknown"))
        create_time = conv.get("create_time", 0.0)

        # Extract model slug from any assistant message
        model_slug = self._extract_model_slug(thread)

        base_tags = ["openai_history", "imported"]
        if model_slug:
            base_tags.append(f"model:{model_slug}")

        chunks: List[ConversationChunk] = []
        current_text = ""
        current_ts = create_time

        for node in thread:
            msg = node.get("message")
            if not msg:
                continue

            role = msg.get("role", "")
            if role == "system":
                continue  # Skip system prompts

            # Extract text from content.parts
            content = msg.get("content", {})
            parts = content.get("parts", [])
            text = " ".join(
                str(p) for p in parts if isinstance(p, str) and p.strip()
            )
            if not text.strip():
                continue

            label = "User" if role == "user" else "Assistant"
            turn = f"[{label}]: {text.strip()}\n\n"

            if len(current_text) + len(turn) > MAX_CHUNK_CHARS and current_text:
                chunks.append(self._make_chunk(
                    current_text, title, conv_id, current_ts, base_tags,
                ))
                current_text = ""
                current_ts = msg.get("create_time", create_time)

            current_text += turn
            if not current_ts:
                current_ts = msg.get("create_time", create_time)

        # Flush remaining text
        if current_text.strip():
            chunks.append(self._make_chunk(
                current_text, title, conv_id, current_ts, base_tags,
            ))

        return chunks

    def _make_chunk(
        self, text: str, title: str, conv_id: str,
        timestamp: float, tags: List[str],
    ) -> ConversationChunk:
        content = strip_credentials(
            f"[IMPORTED CHATGPT HISTORY — {title}]:\n{text.strip()}"
        )
        return ConversationChunk(
            id=f"import-{uuid.uuid4().hex[:12]}",
            session_id=f"openai-import-{str(conv_id)[:12]}",
            timestamp=self._parse_unix_timestamp(timestamp),
            content=content,
            chunk_type=ChunkType.OBSERVATION,
            scope=MemoryScope.LONG_TERM,
            tags=ChunkTags(topics=list(tags)),
            metadata=ChunkMetadata(
                source=SOURCE_TAG,
                confidence=0.6,  # Lower confidence for imported observations
            ),
        )

    @staticmethod
    def _extract_model_slug(thread: List[Dict[str, Any]]) -> Optional[str]:
        """Extract model slug from assistant message metadata."""
        for node in thread:
            msg = node.get("message", {})
            if msg.get("role") == "assistant":
                slug = msg.get("metadata", {}).get("model_slug")
                if slug:
                    return slug
        return None

    @staticmethod
    def _parse_unix_timestamp(ts: Any) -> datetime:
        """Parse Unix float timestamp to datetime."""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return datetime.now(timezone.utc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestFlattenMessageDAG -v --timeout=30`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/memory/importers/openai.py tests/test_import_openai.py
git commit -m "feat: OpenAI history parser — DAG flattener and core module"
```

---

### Task 2: Parser Tests — Conversation Parsing

**Files:**
- Modify: `tests/test_import_openai.py`

- [ ] **Step 1: Write failing tests for conversation parsing**

Add to `tests/test_import_openai.py`:

```python
class TestOpenAIHistoryParser:
    def test_parse_single_conversation(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        assert len(chunks) >= 1
        assert any("debug" in c.content.lower() for c in chunks)

    def test_chunk_has_correct_source(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert chunk.metadata.source == "openai_history"

    def test_chunk_type_is_observation(self):
        """All imported chunks should be OBSERVATION, not DECISION/PREFERENCE."""
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert chunk.chunk_type == ChunkType.OBSERVATION

    def test_chunk_is_long_term_scope(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert chunk.scope == MemoryScope.LONG_TERM

    def test_chunk_has_import_tags(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert "openai_history" in chunk.tags.topics
            assert "imported" in chunk.tags.topics

    def test_chunk_has_model_tag(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        all_tags = [t for c in chunks for t in c.tags.topics]
        assert "model:gpt-4" in all_tags

    def test_skips_system_messages(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert "You are ChatGPT" not in chunk.content

    def test_chunk_preserves_unix_timestamp(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert chunk.timestamp.year == 2023  # 1700000000 = Nov 2023

    def test_includes_conversation_title(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert "Python debugging help" in chunk.content

    def test_empty_conversation_returns_no_chunks(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation({"mapping": {}, "current_node": None})
        assert chunks == []

    def test_chunk_ids_are_unique(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_export(
            [SAMPLE_LINEAR_CONVERSATION, SAMPLE_LINEAR_CONVERSATION],
            exclude_hestia=False,
        )
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_credential_stripping(self):
        conv = {
            **SAMPLE_LINEAR_CONVERSATION,
            "current_node": "msg-cred",
            "mapping": {
                "msg-cred": {
                    "id": "msg-cred",
                    "parent": None,
                    "children": [],
                    "message": {
                        "id": "msg-cred",
                        "role": "user",
                        "content": {
                            "content_type": "text",
                            "parts": ["My API key is sk-abc123def456ghi789jkl012mno345pqr"],
                        },
                        "create_time": 1700000000.0,
                        "metadata": {},
                    },
                },
            },
        }
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(conv)
        for chunk in chunks:
            assert "sk-abc" not in chunk.content
            assert "[CREDENTIAL_REDACTED]" in chunk.content

    def test_confidence_is_observation_level(self):
        """Observation chunks should have 0.6 confidence, not 0.85."""
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_LINEAR_CONVERSATION)
        for chunk in chunks:
            assert chunk.metadata.confidence == 0.6
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestOpenAIHistoryParser -v --timeout=30`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_import_openai.py
git commit -m "test: OpenAI parser — conversation parsing, tags, credentials, timestamps"
```

---

### Task 3: Hestia Exclusion Filter Tests

**Files:**
- Modify: `tests/test_import_openai.py`

- [ ] **Step 1: Write failing tests for exclusion filter**

Add to `tests/test_import_openai.py`:

```python
class TestHestiaExclusion:
    def test_excludes_hestia_titled_conversations(self):
        hestia_conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "Hestia API design"}
        parser = OpenAIHistoryParser()  # Default keywords
        assert parser.should_exclude(hestia_conv) is True

    def test_excludes_case_insensitive(self):
        conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "HESTIA memory pipeline"}
        parser = OpenAIHistoryParser()
        assert parser.should_exclude(conv) is True

    def test_excludes_ollama_conversations(self):
        conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "Setting up Ollama on Mac"}
        parser = OpenAIHistoryParser()
        assert parser.should_exclude(conv) is True

    def test_allows_non_hestia_conversations(self):
        conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "Python debugging help"}
        parser = OpenAIHistoryParser()
        assert parser.should_exclude(conv) is False

    def test_parse_export_skips_excluded(self):
        hestia_conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "Hestia council design"}
        safe_conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "SQL query optimization"}
        parser = OpenAIHistoryParser()
        chunks = parser.parse_export([hestia_conv, safe_conv], exclude_hestia=True)
        for chunk in chunks:
            assert "Hestia council" not in chunk.content
            assert "SQL query" in chunk.content or "debug" in chunk.content.lower()

    def test_custom_exclude_keywords(self):
        conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "My secret project"}
        parser = OpenAIHistoryParser(exclude_keywords=["secret"])
        assert parser.should_exclude(conv) is True

    def test_no_exclusion_when_disabled(self):
        hestia_conv = {**SAMPLE_LINEAR_CONVERSATION, "title": "Hestia API design"}
        parser = OpenAIHistoryParser()
        chunks = parser.parse_export([hestia_conv], exclude_hestia=False)
        assert len(chunks) >= 1
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestHestiaExclusion -v --timeout=30`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_import_openai.py
git commit -m "test: Hestia exclusion filter — keyword matching, case insensitive, custom keywords"
```

---

### Task 4: Long Conversation Splitting + Edge Cases

**Files:**
- Modify: `tests/test_import_openai.py`

- [ ] **Step 1: Write tests for chunking and edge cases**

Add to `tests/test_import_openai.py`:

```python
SAMPLE_BRANCHING_CONVERSATION = {
    "title": "Branching conversation",
    "create_time": 1700000000.0,
    "update_time": 1700001000.0,
    "current_node": "msg-b3",
    "mapping": {
        "root": {
            "id": "root",
            "parent": None,
            "children": ["msg-b1"],
            "message": None,  # Root node sometimes has no message
        },
        "msg-b1": {
            "id": "msg-b1",
            "parent": "root",
            "children": ["msg-b2", "msg-b2-alt"],
            "message": {
                "id": "msg-b1",
                "role": "user",
                "content": {"content_type": "text", "parts": ["Original question"]},
                "create_time": 1700000010.0,
                "metadata": {},
            },
        },
        "msg-b2": {
            "id": "msg-b2",
            "parent": "msg-b1",
            "children": ["msg-b3"],
            "message": {
                "id": "msg-b2",
                "role": "assistant",
                "content": {"content_type": "text", "parts": ["Active branch response"]},
                "create_time": 1700000020.0,
                "metadata": {},
            },
        },
        "msg-b2-alt": {
            "id": "msg-b2-alt",
            "parent": "msg-b1",
            "children": [],
            "message": {
                "id": "msg-b2-alt",
                "role": "assistant",
                "content": {"content_type": "text", "parts": ["Abandoned branch response"]},
                "create_time": 1700000015.0,
                "metadata": {},
            },
        },
        "msg-b3": {
            "id": "msg-b3",
            "parent": "msg-b2",
            "children": [],
            "message": {
                "id": "msg-b3",
                "role": "user",
                "content": {"content_type": "text", "parts": ["Follow-up on active branch"]},
                "create_time": 1700000030.0,
                "metadata": {},
            },
        },
    },
}


class TestEdgeCases:
    def test_branching_conversation_follows_active_path(self):
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_BRANCHING_CONVERSATION)
        all_text = " ".join(c.content for c in chunks)
        assert "Active branch response" in all_text
        assert "Abandoned branch response" not in all_text

    def test_null_message_nodes_skipped(self):
        """Root nodes sometimes have message=None."""
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(SAMPLE_BRANCHING_CONVERSATION)
        assert len(chunks) >= 1  # Should not crash on None message

    def test_long_conversation_splits_chunks(self):
        # Build a conversation with many messages to exceed MAX_CHUNK_CHARS
        mapping = {
            "root": {"id": "root", "parent": None, "children": ["msg-0"], "message": None},
        }
        prev_id = "root"
        for i in range(20):
            msg_id = f"msg-{i}"
            next_id = f"msg-{i+1}" if i < 19 else None
            mapping[msg_id] = {
                "id": msg_id,
                "parent": prev_id,
                "children": [next_id] if next_id else [],
                "message": {
                    "id": msg_id,
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": {
                        "content_type": "text",
                        "parts": [f"Message {i} with padding content. " * 15],
                    },
                    "create_time": 1700000000.0 + i * 10,
                    "metadata": {},
                },
            }
            prev_id = msg_id

        conv = {
            "title": "Long conversation",
            "create_time": 1700000000.0,
            "current_node": "msg-19",
            "mapping": mapping,
        }
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(conv)
        assert len(chunks) > 1  # Must split across multiple chunks

    def test_image_content_parts_skipped(self):
        """Non-string parts (image refs) should be skipped gracefully."""
        conv = {
            **SAMPLE_LINEAR_CONVERSATION,
            "current_node": "msg-img",
            "mapping": {
                "msg-img": {
                    "id": "msg-img",
                    "parent": None,
                    "children": [],
                    "message": {
                        "id": "msg-img",
                        "role": "user",
                        "content": {
                            "content_type": "multimodal_text",
                            "parts": [
                                "Check this image",
                                {"content_type": "image_asset_pointer", "asset_pointer": "file-service://abc"},
                            ],
                        },
                        "create_time": 1700000000.0,
                        "metadata": {},
                    },
                },
            },
        }
        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_conversation(conv)
        assert len(chunks) >= 1
        assert "Check this image" in chunks[0].content
        assert "file-service" not in chunks[0].content
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestEdgeCases -v --timeout=30`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_import_openai.py
git commit -m "test: edge cases — branching DAG, null nodes, chunking, image parts"
```

---

### Task 5: Dry-Run Review Pipeline

**Files:**
- Modify: `hestia/memory/importers/pipeline.py`
- Create: `hestia/memory/importers/review.py`
- Test: `tests/test_import_openai.py` (add dry-run tests)

- [ ] **Step 1: Write failing test for dry-run review output**

Add to `tests/test_import_openai.py`:

```python
import json
import tempfile
from pathlib import Path

from hestia.memory.importers.review import DryRunReview, DryRunChunkEntry


class TestDryRunReview:
    def test_generates_review_entries(self):
        from hestia.memory.importers.openai import OpenAIHistoryParser

        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_export(
            [SAMPLE_LINEAR_CONVERSATION], exclude_hestia=False,
        )
        review = DryRunReview.from_chunks(chunks, [SAMPLE_LINEAR_CONVERSATION])
        assert len(review.entries) >= 1

    def test_entry_has_required_fields(self):
        from hestia.memory.importers.openai import OpenAIHistoryParser

        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_export(
            [SAMPLE_LINEAR_CONVERSATION], exclude_hestia=False,
        )
        review = DryRunReview.from_chunks(chunks, [SAMPLE_LINEAR_CONVERSATION])
        entry = review.entries[0]
        assert entry.conversation_title == "Python debugging help"
        assert entry.chunk_type == "observation"
        assert 0.0 <= entry.confidence <= 1.0
        assert entry.projected_importance >= 0.0
        assert entry.content_preview  # Not empty

    def test_writes_json_file(self):
        from hestia.memory.importers.openai import OpenAIHistoryParser

        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_export(
            [SAMPLE_LINEAR_CONVERSATION], exclude_hestia=False,
        )
        review = DryRunReview.from_chunks(chunks, [SAMPLE_LINEAR_CONVERSATION])
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            review.write_json(f.name)
            data = json.loads(Path(f.name).read_text())
        assert "summary" in data
        assert "entries" in data
        assert data["summary"]["total_chunks"] >= 1
        assert data["summary"]["conversations_processed"] >= 1

    def test_summary_includes_type_breakdown(self):
        from hestia.memory.importers.openai import OpenAIHistoryParser

        parser = OpenAIHistoryParser(exclude_keywords=[])
        chunks = parser.parse_export(
            [SAMPLE_LINEAR_CONVERSATION], exclude_hestia=False,
        )
        review = DryRunReview.from_chunks(chunks, [SAMPLE_LINEAR_CONVERSATION])
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            review.write_json(f.name)
            data = json.loads(Path(f.name).read_text())
        assert "by_type" in data["summary"]
        assert "observation" in data["summary"]["by_type"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestDryRunReview -v --timeout=30`
Expected: FAIL with "ModuleNotFoundError: No module named 'hestia.memory.importers.review'"

- [ ] **Step 3: Implement DryRunReview**

```python
# hestia/memory/importers/review.py
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
_TYPE_BONUSES = {
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
        # Build conversation metadata lookup
        conv_meta: Dict[str, Dict[str, Any]] = {}
        for conv in conversations:
            conv_id = str(conv.get("id", conv.get("conversation_id", "unknown")))[:12]
            mapping = conv.get("mapping", {})
            msg_count = sum(
                1 for node in mapping.values()
                if node.get("message") and node["message"].get("role") in ("user", "assistant")
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
            meta = conv_meta.get(session_key, {
                "title": "Unknown",
                "date": "",
                "message_count": 0,
            })

            # Extract model slug from tags
            model_slug = None
            for tag in chunk.tags.topics:
                if tag.startswith("model:"):
                    model_slug = tag.split(":", 1)[1]
                    break

            entries.append(DryRunChunkEntry(
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
            ))

        review = cls(
            entries=entries,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        return review

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

        output = {
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestDryRunReview -v --timeout=30`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/memory/importers/review.py tests/test_import_openai.py
git commit -m "feat: dry-run review tool — outputs proposed chunks with projected importance"
```

---

### Task 6: Pipeline Integration + CLI Entry Point

**Files:**
- Modify: `hestia/memory/importers/pipeline.py`
- Test: `tests/test_import_openai.py` (add pipeline test)

- [ ] **Step 1: Write failing test for pipeline dry-run**

Add to `tests/test_import_openai.py`:

```python
class TestPipelineDryRun:
    def test_dry_run_produces_review_file(self):
        """Pipeline dry-run should output JSON without touching memory."""
        import tempfile
        from hestia.memory.importers.pipeline import ImportPipeline

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as conv_file:
            json.dump([SAMPLE_LINEAR_CONVERSATION], conv_file)
            conv_path = conv_file.name

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out_file:
            out_path = out_file.name

        result = ImportPipeline.dry_run_openai(
            export_path=conv_path,
            output_path=out_path,
            exclude_hestia=True,
        )
        assert result["total_chunks"] >= 1
        data = json.loads(Path(out_path).read_text())
        assert "summary" in data
        assert "entries" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestPipelineDryRun -v --timeout=30`
Expected: FAIL with "AttributeError: type object 'ImportPipeline' has no attribute 'dry_run_openai'"

- [ ] **Step 3: Add dry_run_openai static method to pipeline**

Add to `hestia/memory/importers/pipeline.py`:

```python
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
```

Also add missing imports at the top of `pipeline.py`:
```python
from typing import Any, Dict, List, Optional
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestPipelineDryRun -v --timeout=30`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest tests/ --timeout=30 -q`
Expected: All pass, 0 failures

- [ ] **Step 6: Commit**

```bash
git add hestia/memory/importers/pipeline.py tests/test_import_openai.py
git commit -m "feat: dry-run pipeline — parse ChatGPT export, output review JSON"
```

---

### Task 7: Multi-File Export Support + Integration Test

**Files:**
- Modify: `tests/test_import_openai.py`

- [ ] **Step 1: Write integration test for multi-file directory loading**

Add to `tests/test_import_openai.py`:

```python
class TestMultiFileExport:
    def test_loads_from_directory_with_numbered_files(self):
        """ChatGPT exports split across conversations-000.json through conversations-005.json."""
        import tempfile
        import os
        from hestia.memory.importers.pipeline import ImportPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two numbered files
            for i in range(2):
                conv = {
                    **SAMPLE_LINEAR_CONVERSATION,
                    "title": f"Conversation from file {i}",
                    "id": f"conv-file-{i}",
                }
                with open(os.path.join(tmpdir, f"conversations-{i:03d}.json"), "w") as f:
                    json.dump([conv], f)

            out_path = os.path.join(tmpdir, "review.json")
            result = ImportPipeline.dry_run_openai(
                export_path=tmpdir,
                output_path=out_path,
                exclude_hestia=False,
            )
            assert result["total_chunks"] >= 2
            data = json.loads(Path(out_path).read_text())
            assert data["summary"]["conversations_processed"] == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_import_openai.py::TestMultiFileExport -v --timeout=30`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest tests/ --timeout=30 -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_import_openai.py
git commit -m "test: multi-file ChatGPT export loading from directory"
```

---

### Post-Implementation

After all tasks complete:
1. Run `@hestia-tester` on full test suite
2. Run `@hestia-reviewer` on changed files
3. Update `CLAUDE.md` project structure if needed (new files in importers/)
4. Update `scripts/auto-test.sh` mapping for new test file
