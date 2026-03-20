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
