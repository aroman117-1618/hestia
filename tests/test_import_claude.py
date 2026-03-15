"""Tests for Claude conversation history import."""
import pytest
from datetime import datetime, timezone

from hestia.memory.importers.claude import (
    ClaudeHistoryParser,
    strip_credentials,
    MAX_CHUNK_CHARS,
)
from hestia.memory.models import ChunkType, MemoryScope


SAMPLE_CONVERSATION = {
    "uuid": "conv-001",
    "name": "Discuss home automation",
    "summary": "Explored Matter protocol options for smart home setup including Apple HomePod and Google Nest Hub compatibility",
    "created_at": "2026-01-15T10:30:00Z",
    "chat_messages": [
        {
            "uuid": "msg-001",
            "text": "What are the best Matter-compatible smart home hubs?",
            "sender": "human",
            "created_at": "2026-01-15T10:30:05Z",
            "content": [{"type": "text", "text": "What are the best Matter-compatible smart home hubs?"}],
            "files": [],
            "attachments": [],
        },
        {
            "uuid": "msg-002",
            "text": "The top Matter-compatible hubs include Apple HomePod, Amazon Echo, and Google Nest Hub.",
            "sender": "assistant",
            "created_at": "2026-01-15T10:30:45Z",
            "content": [{"type": "text", "text": "The top Matter-compatible hubs include Apple HomePod, Amazon Echo, and Google Nest Hub."}],
            "files": [],
            "attachments": [],
        },
    ],
}


class TestClaudeHistoryParser:
    def test_parse_single_conversation(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        assert len(chunks) >= 1
        assert any("Matter" in c.content for c in chunks)

    def test_chunk_has_correct_source(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        for chunk in chunks:
            assert chunk.metadata.source == "claude_history"

    def test_chunk_preserves_timestamp(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        for chunk in chunks:
            assert chunk.timestamp is not None
            assert isinstance(chunk.timestamp, datetime)

    def test_chunk_includes_conversation_context(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        conv_chunks = [c for c in chunks if c.chunk_type == ChunkType.CONVERSATION]
        for chunk in conv_chunks:
            assert "Discuss home automation" in chunk.content

    def test_chunk_is_long_term_scope(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        for chunk in chunks:
            assert chunk.scope == MemoryScope.LONG_TERM

    def test_chunk_has_import_tags(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        for chunk in chunks:
            assert "claude_history" in chunk.tags.topics
            assert "imported" in chunk.tags.topics

    def test_conversation_summary_creates_insight_chunk(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        summary_chunks = [c for c in chunks if c.chunk_type == ChunkType.INSIGHT and "summary" in c.tags.topics]
        assert len(summary_chunks) == 1
        assert "Matter protocol" in summary_chunks[0].content

    def test_long_conversation_splits_into_multiple_chunks(self):
        long_conv = {
            **SAMPLE_CONVERSATION,
            "uuid": "conv-long",
            "summary": "",
            "chat_messages": [
                {
                    "uuid": f"msg-{i}",
                    "text": f"Message {i} with enough content to fill space. " * 20,
                    "sender": "human" if i % 2 == 0 else "assistant",
                    "created_at": f"2026-01-15T10:{i:02d}:00Z",
                    "content": [],
                    "files": [],
                    "attachments": [],
                }
                for i in range(20)
            ],
        }
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(long_conv)
        conv_chunks = [c for c in chunks if c.chunk_type == ChunkType.CONVERSATION]
        assert len(conv_chunks) > 1

    def test_parse_full_export(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_export([SAMPLE_CONVERSATION])
        assert len(chunks) >= 1

    def test_extracts_thinking_blocks(self):
        conv = {
            **SAMPLE_CONVERSATION,
            "uuid": "conv-think",
            "summary": "",
            "chat_messages": [
                {
                    "uuid": "msg-t1",
                    "text": "What model should I use?",
                    "sender": "human",
                    "created_at": "2026-01-15T10:30:05Z",
                    "content": [{"type": "text", "text": "What model should I use?"}],
                    "files": [],
                    "attachments": [],
                },
                {
                    "uuid": "msg-t2",
                    "text": "I recommend Qwen 3.5 9B for your use case.",
                    "sender": "assistant",
                    "created_at": "2026-01-15T10:30:45Z",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "The user is asking about model selection. Given their M1 Mac Mini with 16GB RAM, they need a model that fits in memory while maintaining quality. Qwen 3.5 9B is the best fit because it balances quality with memory footprint.",
                            "summaries": [{"summary": "Evaluating model options for M1 16GB constraint"}],
                        },
                        {"type": "text", "text": "I recommend Qwen 3.5 9B for your use case."},
                    ],
                    "files": [],
                    "attachments": [],
                },
            ],
        }
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(conv)
        thinking_chunks = [c for c in chunks if "claude_thinking" in c.tags.topics]
        assert len(thinking_chunks) >= 1
        assert "model selection" in thinking_chunks[0].content.lower()

    def test_extracts_tool_use_patterns(self):
        conv = {
            **SAMPLE_CONVERSATION,
            "uuid": "conv-tools",
            "summary": "",
            "chat_messages": [
                {
                    "uuid": "msg-s1",
                    "text": "Tell me about Matter protocol",
                    "sender": "human",
                    "created_at": "2026-01-15T10:30:05Z",
                    "content": [{"type": "text", "text": "Tell me about Matter protocol"}],
                    "files": [],
                    "attachments": [],
                },
                {
                    "uuid": "msg-s2",
                    "text": "Matter is a smart home standard...",
                    "sender": "assistant",
                    "created_at": "2026-01-15T10:30:45Z",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "web_search",
                            "input": {"query": "Matter protocol smart home 2026"},
                            "id": "t1",
                            "message": "Searching",
                        },
                        {
                            "type": "tool_result",
                            "content": "...",
                            "tool_use_id": "t1",
                            "name": "web_search",
                            "is_error": False,
                        },
                        {"type": "text", "text": "Matter is a smart home standard..."},
                    ],
                    "files": [],
                    "attachments": [],
                },
            ],
        }
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(conv)
        all_tags = [tag for c in chunks for tag in c.tags.topics]
        assert any("researched:" in tag for tag in all_tags)

    def test_parse_memories(self):
        parser = ClaudeHistoryParser()
        memories = [{
            "conversations_memory": "Andrew is a software engineer building Hestia, a personal AI assistant. He values efficiency and learning-while-building.",
            "project_memories": {
                "proj-001": "Hestia is a locally-hosted AI assistant on Mac Mini M1.",
            },
            "account_uuid": "user-001",
        }]
        chunks = parser.parse_export([], memories=memories)
        assert len(chunks) == 2
        mem_chunks = [c for c in chunks if "memory_summary" in c.tags.topics]
        assert len(mem_chunks) == 1
        proj_chunks = [c for c in chunks if "project_memory" in c.tags.topics]
        assert len(proj_chunks) == 1

    def test_parse_projects(self):
        parser = ClaudeHistoryParser()
        projects = [{
            "uuid": "proj-001",
            "name": "Hestia",
            "description": "Locally-hosted personal AI assistant on Mac Mini M1 with three operational modes.",
            "docs": [],
            "created_at": "2025-12-01T00:00:00Z",
        }]
        chunks = parser.parse_export([], projects=projects)
        assert len(chunks) == 1
        assert "project_context" in chunks[0].tags.topics

    def test_empty_conversation_returns_no_chunks(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation({"uuid": "empty", "chat_messages": []})
        assert chunks == []

    def test_chunk_ids_are_unique(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_export([SAMPLE_CONVERSATION, SAMPLE_CONVERSATION])
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))


class TestCredentialStripping:
    def test_strips_api_keys(self):
        text = "My key is sk-abc123def456ghi789jkl012mno345"
        result = strip_credentials(text)
        assert "sk-abc" not in result
        assert "[CREDENTIAL_REDACTED]" in result

    def test_strips_github_pats(self):
        text = "Token: ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        result = strip_credentials(text)
        assert "ghp_" not in result

    def test_strips_password_patterns(self):
        text = "Set password=MySuperSecret123"
        result = strip_credentials(text)
        assert "MySuperSecret" not in result

    def test_strips_api_key_patterns(self):
        text = "api_key: some_secret_value_here"
        result = strip_credentials(text)
        assert "some_secret" not in result

    def test_preserves_normal_text(self):
        text = "The sk model performs well on benchmarks."
        result = strip_credentials(text)
        assert result == text
