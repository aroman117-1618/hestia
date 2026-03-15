# Hestia Evolution — Sprint 13 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Hestia from a chat assistant into a self-developing AI with rich memory, streamlined apps, and agentic coding capability.

**Architecture:** Four workstreams executed sequentially. WS1 completes the Graphiti-inspired knowledge graph on SQLite (no Neo4j). WS2 trims iOS to essentials and fills macOS gaps. WS3 imports Claude conversation history through the existing memory pipeline. WS4 builds the iterative tool loop and coding tools that enable Hestia to function as her own developer.

**Tech Stack:** Python/FastAPI (backend), Swift/SwiftUI (iOS + macOS), SQLite + ChromaDB (storage), Anthropic Claude API (cloud inference), pytest (testing)

**Enhances (does not replace):**
- Sprint 9-KG knowledge graph (ADR-041) — we extend it
- Agentic self-development discovery — we implement Phases 0-3
- Sprint 11.5 memory pipeline — we add import sources
- Sprint 11B MetaMonitor — memory backfill feeds Gate 2

**Estimated effort:** 6-8 sessions (~12-16 hours)

**Audit conditions (integrated from plan-audit 2026-03-15):**
1. Add `ImportChunk → ConversationChunk` adapter in WS3 parser
2. Exclude `hestia/security/` from edit_file allowlist in WS4
3. `handle_agentic()` is a NEW method — never modify existing `handle()`
4. Add `user_id` column to `episodic_nodes` table from the start
5. Add `[hestia-auto]` prefix to automated git commits
6. Add credential-stripping step to import preprocessor
7. Run WS4 proof-of-concept (multi-tool API call) before building full loop
8. Add relevance penalty (0.9x) for imported chunks in memory search
9. Add `MemorySource.CLAUDE_HISTORY` to enum before import
10. Validate JSON1 extension at database init

---

## Workstream 1: Complete Knowledge Graph (Graphiti-Inspired, SQLite-Native)

**Context:** Sprint 9-KG built bi-temporal facts, entity registry, and communities on SQLite. The Graphiti MCP evaluation (discovery report 2026-03-15) deferred full Graphiti due to Neo4j requirements. This workstream completes the remaining Graphiti-inspired features using our existing SQLite infrastructure.

**What Sprint 9-KG already built:**
- `Fact` model with `valid_at`, `invalid_at`, `expired_at`
- `EntityRegistry` with canonical dedup + label propagation communities
- `FactExtractor` with LLM triplet extraction + contradiction detection
- `GraphBuilder` with `mode=facts` (entity-relationship graph)
- 6 API endpoints (facts, entities, communities)

**What's missing (from Graphiti feature set):**
- Episodic memory nodes (conversation summaries as first-class graph entities)
- Temporal queries ("what did I believe about X in January?")
- Fact invalidation UI (mark facts as expired from the app)
- Auto-extraction on chat (currently on-demand only)
- Entity search endpoint (find entities by name/type)

**Files overview:**
- Modify: `hestia/research/models.py` (add EpisodicNode model)
- Modify: `hestia/research/database.py` (add episodic_nodes table, temporal query methods)
- Modify: `hestia/research/manager.py` (add episodic storage, temporal search)
- Modify: `hestia/research/fact_extractor.py` (add auto-extraction hook)
- Modify: `hestia/orchestration/handler.py` (wire auto-extraction after chat)
- Modify: `hestia/api/routes/research.py` (add endpoints)
- Modify: `hestia/api/schemas/research.py` (add request/response models)
- Create: `tests/test_research_episodic.py`

---

### Task 1.1: Episodic Memory Nodes

Episodic nodes store conversation summaries as graph entities — linking what was discussed to the entities and facts mentioned. This gives the knowledge graph a "when did we talk about X?" capability.

**Files:**
- Modify: `hestia/research/models.py`
- Modify: `hestia/research/database.py`
- Modify: `hestia/research/manager.py`
- Create: `tests/test_research_episodic.py`

- [ ] **Step 1: Write failing tests for EpisodicNode model**

```python
# tests/test_research_episodic.py
"""Tests for episodic memory nodes in the knowledge graph."""
import pytest
from datetime import datetime, timezone
from hestia.research.models import EpisodicNode


class TestEpisodicNodeModel:
    """Test EpisodicNode dataclass."""

    def test_create_episodic_node(self):
        node = EpisodicNode(
            id="ep-001",
            session_id="sess-abc",
            summary="Discussed home automation with Matter protocol",
            entity_ids=["ent-001", "ent-002"],
            fact_ids=["fact-001"],
            created_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        assert node.id == "ep-001"
        assert node.session_id == "sess-abc"
        assert len(node.entity_ids) == 2
        assert len(node.fact_ids) == 1

    def test_episodic_node_defaults(self):
        node = EpisodicNode(
            id="ep-002",
            session_id="sess-def",
            summary="Quick chat about weather",
        )
        assert node.entity_ids == []
        assert node.fact_ids == []
        assert node.created_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_episodic.py::TestEpisodicNodeModel -v --timeout=30`
Expected: FAIL — `cannot import name 'EpisodicNode'`

- [ ] **Step 3: Implement EpisodicNode model**

Add to `hestia/research/models.py`:

```python
@dataclass
class EpisodicNode:
    """A conversation episode in the knowledge graph.

    Links a session summary to the entities and facts mentioned,
    providing temporal 'when did we discuss X?' queries.
    """
    id: str
    session_id: str
    summary: str
    user_id: str = "default"  # Audit condition #4: scope by user from the start
    entity_ids: List[str] = field(default_factory=list)
    fact_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_research_episodic.py::TestEpisodicNodeModel -v --timeout=30`
Expected: PASS

- [ ] **Step 5: Write failing tests for episodic DB operations**

```python
# In tests/test_research_episodic.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

class TestEpisodicDatabase:
    """Test episodic node storage and retrieval."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a test research database."""
        from hestia.research.database import ResearchDatabase
        db = ResearchDatabase(str(tmp_path / "test.db"))
        asyncio.get_event_loop().run_until_complete(db.initialize())
        return db

    def test_store_episodic_node(self, db):
        node = EpisodicNode(
            id="ep-001",
            session_id="sess-abc",
            summary="Discussed Hestia architecture decisions",
            entity_ids=["ent-001"],
            fact_ids=["fact-001", "fact-002"],
        )
        asyncio.get_event_loop().run_until_complete(
            db.store_episodic_node(node)
        )
        result = asyncio.get_event_loop().run_until_complete(
            db.get_episodic_nodes(limit=10)
        )
        assert len(result) == 1
        assert result[0].session_id == "sess-abc"
        assert result[0].entity_ids == ["ent-001"]

    def test_get_episodic_nodes_for_entity(self, db):
        """Find episodes that mention a specific entity."""
        for i in range(3):
            node = EpisodicNode(
                id=f"ep-{i}",
                session_id=f"sess-{i}",
                summary=f"Episode {i}",
                entity_ids=["ent-shared"] if i < 2 else ["ent-other"],
            )
            asyncio.get_event_loop().run_until_complete(
                db.store_episodic_node(node)
            )
        results = asyncio.get_event_loop().run_until_complete(
            db.get_episodic_nodes_for_entity("ent-shared")
        )
        assert len(results) == 2
```

- [ ] **Step 6: Implement episodic DB table and methods**

Add to `hestia/research/database.py` `_create_tables()`:

```sql
-- Audit condition #10: validate JSON1 at init
SELECT json('[]');  -- Raises error if JSON1 not available

CREATE TABLE IF NOT EXISTS episodic_nodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'default',  -- Audit condition #4
    summary TEXT NOT NULL,
    entity_ids TEXT NOT NULL DEFAULT '[]',
    fact_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic_nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_episodic_user ON episodic_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_episodic_created ON episodic_nodes(created_at);
```

Add methods: `store_episodic_node()`, `get_episodic_nodes()`, `get_episodic_nodes_for_entity()`.

Entity lookup uses `json_each(entity_ids)` for SQLite JSON array queries.

- [ ] **Step 7: Run tests, verify pass**

Run: `python -m pytest tests/test_research_episodic.py -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add hestia/research/models.py hestia/research/database.py tests/test_research_episodic.py
git commit -m "feat: episodic memory nodes for knowledge graph (Sprint 13 WS1)"
```

---

### Task 1.2: Temporal Fact Queries

Enable "what did I believe about X in January?" queries by adding point-in-time fact retrieval.

**Files:**
- Modify: `hestia/research/database.py` (add `get_facts_at_time()`)
- Modify: `hestia/research/manager.py` (expose temporal query)
- Modify: `hestia/api/routes/research.py` (add endpoint)
- Modify: `tests/test_research_episodic.py` (add temporal tests)

- [ ] **Step 1: Write failing test for temporal fact query**

```python
class TestTemporalFactQueries:
    """Test point-in-time fact retrieval."""

    @pytest.fixture
    def db_with_facts(self, db):
        """Seed DB with facts that have temporal bounds."""
        from hestia.research.models import Fact
        facts = [
            Fact(id="f1", subject="Hestia", relation="uses", object="Mixtral 8x7B",
                 confidence=0.9, valid_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                 invalid_at=datetime(2026, 3, 5, tzinfo=timezone.utc)),
            Fact(id="f2", subject="Hestia", relation="uses", object="Qwen 3.5 9B",
                 confidence=0.95, valid_at=datetime(2026, 3, 5, tzinfo=timezone.utc)),
            Fact(id="f3", subject="Andrew", relation="works_at", object="Postman",
                 confidence=0.9, valid_at=datetime(2025, 6, 1, tzinfo=timezone.utc)),
        ]
        for f in facts:
            asyncio.get_event_loop().run_until_complete(db.store_fact(f))
        return db

    def test_facts_at_january_2026(self, db_with_facts):
        """In Jan 2026, Hestia used Mixtral, not Qwen."""
        results = asyncio.get_event_loop().run_until_complete(
            db_with_facts.get_facts_at_time(
                point_in_time=datetime(2026, 1, 15, tzinfo=timezone.utc),
                subject="Hestia",
            )
        )
        objects = [f.object for f in results]
        assert "Mixtral 8x7B" in objects
        assert "Qwen 3.5 9B" not in objects

    def test_facts_at_march_2026(self, db_with_facts):
        """In Mar 2026, Hestia uses Qwen, Mixtral is expired."""
        results = asyncio.get_event_loop().run_until_complete(
            db_with_facts.get_facts_at_time(
                point_in_time=datetime(2026, 3, 10, tzinfo=timezone.utc),
                subject="Hestia",
            )
        )
        objects = [f.object for f in results]
        assert "Qwen 3.5 9B" in objects
        assert "Mixtral 8x7B" not in objects
```

- [ ] **Step 2: Implement `get_facts_at_time()` in database.py**

SQL query logic:
```sql
SELECT * FROM facts
WHERE subject = ?
  AND valid_at <= ?
  AND (invalid_at IS NULL OR invalid_at > ?)
  AND expired_at IS NULL
ORDER BY valid_at DESC
```

- [ ] **Step 3: Add API endpoint `GET /v1/research/facts/at-time`**

Query params: `subject` (optional), `point_in_time` (ISO datetime, defaults to now).

- [ ] **Step 4: Run full research tests, commit**

```bash
python -m pytest tests/test_research.py tests/test_research_episodic.py -v --timeout=30
git add hestia/research/ hestia/api/routes/research.py tests/
git commit -m "feat: temporal fact queries — point-in-time knowledge retrieval"
```

---

### Task 1.3: Auto-Extract Facts from Chat

Currently fact extraction is on-demand (`POST /v1/research/facts/extract`). Wire it to run automatically after qualifying chat messages (long messages, messages mentioning entities).

**Files:**
- Modify: `hestia/orchestration/handler.py` (add post-chat extraction hook)
- Modify: `hestia/research/manager.py` (add `maybe_extract_facts()` gating method)
- Modify: `tests/test_handler.py` (add extraction test)

- [ ] **Step 1: Write failing test for auto-extraction gating**

```python
class TestAutoFactExtraction:
    def test_short_messages_skip_extraction(self):
        """Messages under 50 chars should not trigger extraction."""
        manager = create_mock_research_manager()
        result = asyncio.get_event_loop().run_until_complete(
            manager.should_extract_facts("Hello, how are you?")
        )
        assert result is False

    def test_long_messages_trigger_extraction(self):
        """Messages over 100 chars with entity-like content trigger extraction."""
        manager = create_mock_research_manager()
        msg = "I've been thinking about switching from Mixtral to Qwen for the primary model because the benchmarks show better performance on coding tasks."
        result = asyncio.get_event_loop().run_until_complete(
            manager.should_extract_facts(msg)
        )
        assert result is True
```

- [ ] **Step 2: Implement gating logic in ResearchManager**

`should_extract_facts(text)` returns True if:
- Text > 100 chars AND
- Contains at least one known entity name (from entity registry) OR
- Contains factual language patterns (dates, "uses", "works at", "switched to", etc.)

- [ ] **Step 3: Wire into handler.py as fire-and-forget**

After `store_exchange()` in `handle()`, add:
```python
# Fire-and-forget fact extraction (don't block response)
if research_manager and len(response.content) > 100:
    asyncio.create_task(
        self._maybe_extract_facts(user_message, response.content)
    )
```

- [ ] **Step 4: Run handler tests + research tests, commit**

```bash
python -m pytest tests/test_handler.py tests/test_research.py tests/test_research_episodic.py -v --timeout=30
git commit -m "feat: auto-extract facts from qualifying chat messages"
```

---

### Task 1.4: Entity Search Endpoint + Fact Invalidation

**Files:**
- Modify: `hestia/api/routes/research.py`
- Modify: `hestia/research/database.py`
- Modify: `hestia/research/manager.py`

- [ ] **Step 1: Add `GET /v1/research/entities/search?q=<name>`**

Returns entities matching name (fuzzy, using existing canonical dedup).

- [ ] **Step 2: Add `POST /v1/research/facts/{id}/invalidate`**

Sets `invalid_at` to now and optionally `expired_at`. Body: `{"reason": "...", "superseded_by": "fact-id"}`.

- [ ] **Step 3: Tests + commit**

```bash
git commit -m "feat: entity search + fact invalidation endpoints"
```

---

## Workstream 2: App Strategy — Trim iOS, Complete macOS

**Strategic decision:** iOS becomes a focused companion (Chat + Voice + Settings). macOS becomes the full-featured primary application with all dashboards, explorer, wiki, research, and management features.

**Rationale:**
- Andrew's primary usage is Mac-based (Claude Code + Xcode)
- iOS strength is mobile: quick chats, voice input, on-the-go settings
- macOS has screen real estate for dashboards, graphs, multi-pane layouts
- Reduces maintenance burden (don't wire every feature into both UIs)

---

### Task 2.1: iOS App Trimming

Remove non-essential tabs/views from iOS to focus on Chat, Voice, and Settings. The removed features remain accessible via macOS.

**Files:**
- Modify: `HestiaApp/Shared/App/ContentView.swift` (remove tabs)
- Remove from iOS target: Command Center views, Explorer views, Wiki views, Neural Net views
- Keep: ChatView, SettingsView (with all sub-views), Auth/Onboarding
- Modify: `HestiaApp/project.yml` (exclude removed iOS views)

- [ ] **Step 1: Audit current iOS tab structure**

Read `HestiaApp/Shared/App/ContentView.swift` to identify all tabs.

- [ ] **Step 2: Reduce iOS to 3 tabs: Chat, Voice, Settings**

Modify ContentView to show only:
1. **Chat** (with streaming, mode switching, forceLocal toggle)
2. **Voice** (voice recording + journaling — iOS's unique strength)
3. **Settings** (Cloud, Integrations, Device Management, Proactive, Health Coaching, Profile, Agents)

Remove from iOS tab bar: Command Center, Explorer, Wiki, Neural Net.

- [ ] **Step 3: Update project.yml excludes if needed**

Ensure removed views don't bloat the iOS binary. Views can remain in Shared/ but excluded from the iOS target via project.yml.

- [ ] **Step 4: Build iOS target, verify clean**

```bash
xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build 2>&1 | grep -E 'error:|BUILD'
```

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(iOS): trim to Chat + Voice + Settings — macOS is primary app"
```

---

### Task 2.2: macOS Feature Gaps

Fill the identified gaps in the macOS app.

**Priority gaps (from parity analysis):**
1. Memory approve/reject UI (neither app has this)
2. Proactive Intelligence settings
3. Health coaching preferences view
4. Neural Net rendering (ViewModel exists, rendering not wired)
5. Draft management in Explorer

**Files:**
- Create: `HestiaApp/macOS/Views/Memory/MacMemoryReviewView.swift`
- Create: `HestiaApp/macOS/ViewModels/MacMemoryReviewViewModel.swift`
- Modify: `HestiaApp/macOS/Views/Settings/` (add proactive + health coaching)
- Modify: `HestiaApp/macOS/Views/Command/MacNeuralNetView.swift` (wire rendering)

- [ ] **Step 1: Memory Review View**

Create a macOS view that shows pending memory chunks with approve/reject actions.
The ViewModel calls `getPendingMemoryReviews()`, `approveMemory()`, `rejectMemory()` — all already on `HestiaClientProtocol`.

- [ ] **Step 2: Proactive Settings View**

Add proactive intelligence settings panel to macOS Settings.
Wire to existing `ProactiveSettingsViewModel` patterns from iOS.

- [ ] **Step 3: Health Coaching Preferences**

Add health coaching preferences to macOS Health view.
Wire to `getCoachingPreferences()` / `updateCoachingPreferences()` on APIClient.

- [ ] **Step 4: Wire Neural Net Rendering**

Connect `MacNeuralNetViewModel` to a SceneKit view in the Command Center.
Port the iOS `NeuralNetSceneView` approach to macOS.

- [ ] **Step 5: Build both targets, commit**

```bash
xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -destination 'platform=macOS' build
xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build
git commit -m "feat(macOS): memory review, proactive settings, health coaching, neural net"
```

---

## Workstream 3: Claude History Import

**Context:** Andrew exported his Claude.ai data (78 conversations, 796 messages, ~1.7MB text). We import this through the existing memory pipeline so it gets proper tagging, embedding, and knowledge graph integration.

**Data format (from analysis):**
```json
// conversations.json — array of:
{
  "uuid": "...",
  "name": "Conversation title",
  "summary": "Claude-generated overview (16 of 78 have this)",
  "created_at": "2025-12-05T03:34:03Z",
  "chat_messages": [
    {
      "uuid": "...",
      "text": "raw message text",
      "content": [
        {"type": "text", "text": "..."},
        {"type": "thinking", "thinking": "Claude's reasoning...",
         "summaries": [{"summary": "one-line reasoning step"}]},
        {"type": "tool_use", "name": "web_search", "input": {"query": "..."}},
        {"type": "tool_result", "content": "...", "is_error": false}
      ],
      "sender": "human" | "assistant",
      "created_at": "2025-12-05T03:34:04Z",
      "files": [...],   // 116 file refs (images, docs)
      "attachments": [...] // 20 attachments
    }
  ]
}

// memories.json — array of:
{
  "conversations_memory": "Claude's synthesized user profile (2.8K chars)",
  "project_memories": {"project-uuid": "project-specific memory (2.8K chars)"}
}

// projects.json — array of:
{
  "uuid": "...",
  "name": "Hestia",
  "description": "...",
  "prompt_template": "...",
  "docs": [{"filename": "api-contract.md", "content": "..."}]  // 11 docs for Hestia
}
```

**Content inventory:**

| Layer | Count | Volume | Import As |
|---|---|---|---|
| Conversation text | 796 msgs | 1.7MB | `CONVERSATION` chunks (turn pairs, split at 2K chars) |
| Thinking blocks | 563 | 348K chars | `INSIGHT` chunks tagged `claude_thinking` |
| Thinking summaries | 1,026 | ~50K chars | Metadata tags on parent chunks + standalone `INSIGHT` |
| Conversation summaries | 16 | 21K chars | `INSIGHT` chunks tagged `summary` |
| Claude memory | 1 | 5.7K chars | `INSIGHT` chunks tagged `memory_summary` |
| Project memories | 1 | 2.8K chars | `INSIGHT` chunks tagged `project_memory` |
| Tool use patterns | 551 | N/A | Metadata tags only (search queries as topic signals) |
| Project docs | 11 | varies | Skip (outdated — already in codebase) |
| Files/attachments | 136 | N/A | Skip (binary, no text) |

**Pipeline:**
```
Parse JSON → Extract layers (text + thinking + summaries + tool patterns)
  → Chunk conversations (turn pairs + thinking interleaved)
  → Tag source → Dedup check → Store in memory
  → Embed in ChromaDB → Auto-extract facts → Build episodic nodes
```

---

### Task 3.1: Claude History Parser

**Files:**
- Create: `hestia/memory/importers/__init__.py`
- Create: `hestia/memory/importers/claude.py`
- Create: `tests/test_import_claude.py`

- [ ] **Step 1: Write failing tests for Claude JSON parsing**

```python
# tests/test_import_claude.py
"""Tests for Claude conversation history import."""
import pytest
import json
from datetime import datetime, timezone
from hestia.memory.importers.claude import ClaudeHistoryParser


SAMPLE_CONVERSATION = {
    "uuid": "conv-001",
    "name": "Discuss home automation",
    "summary": "Explored Matter protocol options for smart home",
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
            "text": "The top Matter-compatible hubs include Apple HomePod, Amazon Echo, and Google Nest Hub...",
            "sender": "assistant",
            "created_at": "2026-01-15T10:30:45Z",
            "content": [{"type": "text", "text": "The top Matter-compatible hubs include..."}],
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
        # Should produce at least one chunk per conversation
        assert any("Matter" in c.content for c in chunks)

    def test_chunk_has_correct_source(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        for chunk in chunks:
            assert chunk.metadata.get("source") == "claude_history"

    def test_chunk_preserves_timestamp(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        # Chunks should carry the conversation timestamp
        for chunk in chunks:
            assert chunk.metadata.get("original_timestamp") is not None

    def test_chunk_includes_conversation_context(self):
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(SAMPLE_CONVERSATION)
        # Each chunk should reference the conversation title
        for chunk in chunks:
            assert chunk.metadata.get("conversation_name") == "Discuss home automation"

    def test_long_conversation_splits_into_multiple_chunks(self):
        """Conversations with many messages split on turn boundaries."""
        long_conv = {
            **SAMPLE_CONVERSATION,
            "chat_messages": [
                {"uuid": f"msg-{i}", "text": f"Message {i} " * 200,
                 "sender": "human" if i % 2 == 0 else "assistant",
                 "created_at": f"2026-01-15T10:{i:02d}:00Z",
                 "content": [], "files": [], "attachments": []}
                for i in range(20)
            ],
        }
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(long_conv)
        assert len(chunks) > 1  # Should split

    def test_parse_full_export(self):
        parser = ClaudeHistoryParser()
        conversations = [SAMPLE_CONVERSATION]
        all_chunks = parser.parse_export(conversations)
        assert len(all_chunks) >= 1

    def test_extracts_thinking_blocks(self):
        """Thinking blocks become INSIGHT chunks tagged claude_thinking."""
        conv = {
            **SAMPLE_CONVERSATION,
            "chat_messages": [
                {
                    "uuid": "msg-t1",
                    "text": "What model should I use?",
                    "sender": "human",
                    "created_at": "2026-01-15T10:30:05Z",
                    "content": [{"type": "text", "text": "What model should I use?"}],
                    "files": [], "attachments": [],
                },
                {
                    "uuid": "msg-t2",
                    "text": "I recommend Qwen 3.5 9B for your use case.",
                    "sender": "assistant",
                    "created_at": "2026-01-15T10:30:45Z",
                    "content": [
                        {"type": "thinking", "thinking": "The user is asking about model selection. Given their M1 Mac Mini with 16GB RAM, they need a model that fits in memory while maintaining quality. Qwen 3.5 9B is the best fit because it balances quality with memory footprint. Mixtral 8x7B would require too much RAM.",
                         "summaries": [{"summary": "Evaluating model options for M1 16GB constraint"}]},
                        {"type": "text", "text": "I recommend Qwen 3.5 9B for your use case."},
                    ],
                    "files": [], "attachments": [],
                },
            ],
        }
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(conv)
        thinking_chunks = [c for c in chunks if "claude_thinking" in c.tags]
        assert len(thinking_chunks) >= 1
        assert "model selection" in thinking_chunks[0].content.lower()

    def test_extracts_tool_use_patterns(self):
        """Web search queries become topic tags on conversation chunks."""
        conv = {
            **SAMPLE_CONVERSATION,
            "chat_messages": [
                {
                    "uuid": "msg-s1",
                    "text": "Tell me about Matter protocol",
                    "sender": "human",
                    "created_at": "2026-01-15T10:30:05Z",
                    "content": [{"type": "text", "text": "Tell me about Matter protocol"}],
                    "files": [], "attachments": [],
                },
                {
                    "uuid": "msg-s2",
                    "text": "Matter is a smart home standard...",
                    "sender": "assistant",
                    "created_at": "2026-01-15T10:30:45Z",
                    "content": [
                        {"type": "tool_use", "name": "web_search",
                         "input": {"query": "Matter protocol smart home 2026"},
                         "id": "t1", "message": "Searching"},
                        {"type": "tool_result", "content": "...", "tool_use_id": "t1",
                         "name": "web_search", "is_error": False},
                        {"type": "text", "text": "Matter is a smart home standard..."},
                    ],
                    "files": [], "attachments": [],
                },
            ],
        }
        parser = ClaudeHistoryParser()
        chunks = parser.parse_conversation(conv)
        # At least one chunk should have the research topic tag
        all_tags = [tag for c in chunks for tag in c.tags]
        assert any("researched:" in tag for tag in all_tags)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_import_claude.py -v --timeout=30`
Expected: FAIL — `cannot import name 'ClaudeHistoryParser'`

- [ ] **Step 3: Implement ClaudeHistoryParser**

```python
# hestia/memory/importers/claude.py
"""Parser for Claude.ai conversation export data."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger
from hestia.memory.models import ChunkType, MemoryScope

logger = get_logger()

# Max chars per memory chunk before splitting
MAX_CHUNK_CHARS = 2000
# Prefix tag for all imported chunks
SOURCE_TAG = "claude_history"


@dataclass
class ImportChunk:
    """A chunk ready for memory pipeline ingestion."""
    content: str
    chunk_type: ChunkType
    scope: MemoryScope
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClaudeHistoryParser:
    """Parse Claude.ai exported conversations into memory chunks.

    Chunking strategy:
    - Group human+assistant turn pairs
    - Split when accumulated text exceeds MAX_CHUNK_CHARS
    - Preserve conversation context (title, timestamp) in metadata
    - Tag with source='claude_history' for dedup and filtering
    """

    def parse_export(
        self,
        conversations: List[Dict[str, Any]],
        memories: Optional[Dict[str, Any]] = None,
        projects: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ImportChunk]:
        """Parse a full Claude export into import chunks."""
        all_chunks: List[ImportChunk] = []

        for conv in conversations:
            all_chunks.extend(self.parse_conversation(conv))

        # Parse Claude's memory summaries as high-value context
        if memories:
            all_chunks.extend(self._parse_memories(memories))

        # Parse project docs as reference material
        if projects:
            all_chunks.extend(self._parse_projects(projects))

        logger.info(
            "Parsed Claude export",
            extra={
                "conversations": len(conversations),
                "total_chunks": len(all_chunks),
            },
        )
        return all_chunks

    def parse_conversation(self, conv: Dict[str, Any]) -> List[ImportChunk]:
        """Parse a single conversation into chunks.

        Extracts 4 content layers:
        1. Conversation text (human/assistant turn pairs)
        2. Thinking blocks (Claude's extended reasoning)
        3. Thinking summaries (distilled reasoning steps)
        4. Tool use patterns (search queries as topic metadata)
        """
        messages = conv.get("chat_messages", [])
        if not messages:
            return []

        conv_name = conv.get("name", "Untitled")
        conv_id = conv.get("uuid", "unknown")
        created_at = conv.get("created_at", "")
        summary = conv.get("summary", "")

        base_metadata = {
            "source": SOURCE_TAG,
            "conversation_id": conv_id,
            "conversation_name": conv_name,
            "original_timestamp": created_at,
        }

        chunks: List[ImportChunk] = []
        current_text = ""
        current_start = created_at
        tool_queries: List[str] = []  # Collect search queries as topic signals

        for msg in messages:
            sender = msg.get("sender", "unknown")
            content_parts = msg.get("content", [])

            # Extract text content
            text = msg.get("text", "")
            if not text:
                text = " ".join(
                    p.get("text", "") for p in content_parts
                    if isinstance(p, dict) and p.get("type") == "text"
                )

            # Extract thinking blocks (Claude's reasoning)
            for part in content_parts:
                if not isinstance(part, dict):
                    continue

                if part.get("type") == "thinking":
                    thinking_text = part.get("thinking", "")
                    if thinking_text and len(thinking_text) > 100:
                        # Store significant thinking as insight chunks
                        chunks.append(ImportChunk(
                            content=f"[CLAUDE REASONING — {conv_name}]:\n{thinking_text[:MAX_CHUNK_CHARS]}",
                            chunk_type=ChunkType.INSIGHT,
                            scope=MemoryScope.LONG_TERM,
                            tags=["claude_history", "claude_thinking", "imported"],
                            metadata={
                                **base_metadata,
                                "chunk_role": "thinking",
                                "chunk_timestamp": msg.get("created_at", created_at),
                            },
                        ))

                    # Extract thinking summaries as lightweight insights
                    for s in part.get("summaries", []):
                        if isinstance(s, dict) and s.get("summary"):
                            summary_text = s["summary"]
                            # Collect summaries — batch into chunks later
                            pass  # Summaries are short; we tag them on parent chunks

                elif part.get("type") == "tool_use":
                    # Capture search queries as topic signals
                    tool_name = part.get("name", "")
                    tool_input = part.get("input", {})
                    if tool_name == "web_search" and isinstance(tool_input, dict):
                        query = tool_input.get("query", "")
                        if query:
                            tool_queries.append(query)

            # Build conversation text chunks (same as before)
            if not text.strip():
                continue

            role = "User" if sender == "human" else "Assistant"
            turn = f"[{role}]: {text.strip()}\n\n"

            if len(current_text) + len(turn) > MAX_CHUNK_CHARS and current_text:
                chunks.append(self._make_chunk(
                    current_text, conv_name, base_metadata, current_start,
                ))
                current_text = ""
                current_start = msg.get("created_at", created_at)

            current_text += turn

        # Flush remaining conversation text
        if current_text.strip():
            chunks.append(self._make_chunk(
                current_text, conv_name, base_metadata, current_start,
            ))

        # Add conversation summary as insight chunk
        if summary and len(summary) > 50:
            chunks.append(ImportChunk(
                content=f"[CLAUDE CONVERSATION SUMMARY — {conv_name}]: {summary}",
                chunk_type=ChunkType.INSIGHT,
                scope=MemoryScope.LONG_TERM,
                tags=["claude_history", "summary", "imported"],
                metadata={**base_metadata, "chunk_role": "summary"},
            ))

        # Attach tool query topics as metadata on all chunks from this conversation
        if tool_queries:
            topic_tags = [f"researched:{q[:60]}" for q in tool_queries[:10]]
            for chunk in chunks:
                chunk.tags.extend(topic_tags)

        return chunks

    def _make_chunk(
        self, text: str, conv_name: str,
        base_metadata: Dict, timestamp: str,
    ) -> ImportChunk:
        return ImportChunk(
            content=f"[IMPORTED CLAUDE HISTORY — {conv_name}]:\n{text.strip()}",
            chunk_type=ChunkType.CONVERSATION,
            scope=MemoryScope.LONG_TERM,
            tags=["claude_history", "imported"],
            metadata={**base_metadata, "chunk_timestamp": timestamp},
        )

    def _parse_memories(self, memories: Dict[str, Any]) -> List[ImportChunk]:
        """Parse Claude's conversation memory summary."""
        chunks = []
        conv_memory = memories.get("conversations_memory", "")
        if conv_memory and len(conv_memory) > 50:
            chunks.append(ImportChunk(
                content=f"[CLAUDE MEMORY SUMMARY]: {conv_memory}",
                chunk_type=ChunkType.INSIGHT,
                scope=MemoryScope.LONG_TERM,
                tags=["claude_history", "memory_summary", "imported"],
                metadata={"source": SOURCE_TAG, "chunk_role": "memory_summary"},
            ))

        # Project-specific memories
        for project_id, content in memories.get("project_memories", {}).items():
            if content and len(content) > 50:
                chunks.append(ImportChunk(
                    content=f"[CLAUDE PROJECT MEMORY]: {content}",
                    chunk_type=ChunkType.INSIGHT,
                    scope=MemoryScope.LONG_TERM,
                    tags=["claude_history", "project_memory", "imported"],
                    metadata={
                        "source": SOURCE_TAG,
                        "project_id": project_id,
                        "chunk_role": "project_memory",
                    },
                ))
        return chunks

    def _parse_projects(self, projects: List[Dict[str, Any]]) -> List[ImportChunk]:
        """Parse project docs as reference chunks."""
        chunks = []
        for project in projects:
            name = project.get("name", "Unknown")
            for doc in project.get("docs", []):
                content = doc.get("content", "")
                filename = doc.get("filename", "unknown")
                if content and len(content) > 100:
                    chunks.append(ImportChunk(
                        content=f"[CLAUDE PROJECT DOC — {name}/{filename}]:\n{content[:MAX_CHUNK_CHARS]}",
                        chunk_type=ChunkType.FACT,
                        scope=MemoryScope.LONG_TERM,
                        tags=["claude_history", "project_doc", "imported", name.lower()],
                        metadata={
                            "source": SOURCE_TAG,
                            "project_name": name,
                            "filename": filename,
                            "chunk_role": "project_doc",
                        },
                    ))
        return chunks
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `python -m pytest tests/test_import_claude.py -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/memory/importers/ tests/test_import_claude.py
git commit -m "feat: Claude history parser — converts export to memory chunks"
```

---

### Task 3.2: Import Pipeline Endpoint + Audit Conditions

Wire the parser into the memory pipeline via a new API endpoint. This task also addresses audit conditions #1, #6, #8, #9.

**Pre-requisite steps (audit conditions):**

- [ ] **Step 0a: Add `CLAUDE_HISTORY` to MemorySource enum** (audit #9)

In `hestia/memory/models.py`, add to `MemorySource`:
```python
CLAUDE_HISTORY = "claude_history"
OPENAI_HISTORY = "openai_history"  # Future-proof for OpenAI import
```

- [ ] **Step 0b: Add ImportChunk → ConversationChunk adapter** (audit #1)

In `hestia/memory/importers/claude.py`, add:
```python
def to_conversation_chunk(self, import_chunk: ImportChunk, user_id: str) -> ConversationChunk:
    """Convert ImportChunk to ConversationChunk for memory pipeline storage."""
    return ConversationChunk(
        id=f"import-{uuid4().hex[:12]}",
        session_id=f"claude-import-{import_chunk.metadata.get('conversation_id', 'unknown')}",
        content=import_chunk.content,
        chunk_type=import_chunk.chunk_type,
        scope=import_chunk.scope,
        tags=Tags(topics=import_chunk.tags),
        metadata=import_chunk.metadata,
        timestamp=datetime.fromisoformat(
            import_chunk.metadata.get("original_timestamp", datetime.now(timezone.utc).isoformat())
        ),
    )
```

- [ ] **Step 0c: Add credential-stripping preprocessor** (audit #6)

In `hestia/memory/importers/claude.py`, add:
```python
import re

# Patterns that look like API keys, tokens, passwords
CREDENTIAL_PATTERNS = [
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),          # OpenAI/Anthropic API keys
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),            # GitHub PATs
    re.compile(r'xox[bprs]-[a-zA-Z0-9\-]+'),       # Slack tokens
    re.compile(r'-----BEGIN [A-Z ]+ KEY-----'),     # PEM keys
    re.compile(r'password\s*[:=]\s*\S+', re.I),     # password=... patterns
    re.compile(r'api[_-]?key\s*[:=]\s*\S+', re.I),  # api_key=... patterns
]

def strip_credentials(text: str) -> str:
    """Remove potential credentials from imported text."""
    for pattern in CREDENTIAL_PATTERNS:
        text = pattern.sub('[CREDENTIAL_REDACTED]', text)
    return text
```

Call `strip_credentials()` on all chunk content before storage.

- [ ] **Step 0d: Add relevance penalty for imported chunks** (audit #8)

In `hestia/memory/manager.py`, modify the search scoring to apply 0.9x multiplier for imported sources:
```python
# In search results scoring
if chunk.metadata.get("source") in ("claude_history", "openai_history"):
    score *= 0.9  # Imported history ranks below fresh conversation
```

**Files:**
- Create: `hestia/memory/importers/pipeline.py` (orchestrates parse → dedup → store → embed)
- Modify: `hestia/api/routes/memory.py` (add `POST /v1/memory/import/claude`)
- Modify: `hestia/api/schemas/memory.py` (add import request/response schemas)
- Create: `tests/test_import_pipeline.py`

- [ ] **Step 1: Write failing tests for import pipeline**

```python
# tests/test_import_pipeline.py
"""Tests for the conversation history import pipeline."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

class TestImportPipeline:
    def test_import_deduplicates(self):
        """Importing the same data twice should not create duplicates."""
        # First import: N chunks stored
        # Second import: 0 new chunks (all deduped)
        pass

    def test_import_stores_in_chromadb(self):
        """Imported chunks get ChromaDB embeddings."""
        pass

    def test_import_triggers_fact_extraction(self):
        """Qualifying chunks trigger fact extraction."""
        pass

    def test_import_creates_episodic_nodes(self):
        """Each conversation creates an episodic node."""
        pass

    def test_import_returns_batch_stats(self):
        """Import returns items_processed, items_stored, items_skipped."""
        pass
```

- [ ] **Step 2: Implement ImportPipeline**

```python
# hestia/memory/importers/pipeline.py
"""Orchestrates conversation history import through the memory pipeline."""

class ImportPipeline:
    """Import external conversation history into Hestia's memory.

    Flow: parse → dedup → store (SQLite + ChromaDB) → tag → extract facts → create episodic nodes
    """

    async def import_claude_history(
        self, conversations_path: str,
        memories_path: Optional[str] = None,
        projects_path: Optional[str] = None,
        user_id: str = "default",
    ) -> ImportResult:
        ...
```

- [ ] **Step 3: Add API endpoint `POST /v1/memory/import/claude`**

Accepts multipart file upload OR JSON body with file paths.
Returns batch stats: `{batch_id, conversations_processed, chunks_stored, chunks_skipped, facts_extracted, episodic_nodes_created}`.

- [ ] **Step 4: Run full test suite, commit**

```bash
python -m pytest tests/ -v --timeout=30
git commit -m "feat: Claude history import pipeline with dedup + fact extraction"
```

---

### Task 3.3: Execute the Import

Run the actual import of Andrew's Claude data.

- [ ] **Step 1: Start server**

```bash
lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
python -m hestia.api.server &
sleep 5
```

- [ ] **Step 2: Run import via API or CLI**

```bash
curl -X POST https://localhost:8443/v1/memory/import/claude \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{
    "conversations_path": "/Users/andrewlonati/Downloads/data-2026-03-15-22-44-27-batch-0000/conversations.json",
    "memories_path": "/Users/andrewlonati/Downloads/data-2026-03-15-22-44-27-batch-0000/memories.json",
    "projects_path": "/Users/andrewlonati/Downloads/data-2026-03-15-22-44-27-batch-0000/projects.json"
  }' -k
```

- [ ] **Step 3: Verify import results**

Check batch stats. Verify chunks appear in memory search. Verify facts were extracted. Verify episodic nodes were created for conversations.

- [ ] **Step 4: Commit any pipeline fixes**

---

## Workstream 4: Agentic Self-Development (Hestia as Her Own Developer)

**Context:** The agentic self-development discovery (2026-03-15) identified 8 gaps and proposed a 4-phase approach. This workstream implements Phases 0-2. Phase 3 (Learning Cycle) deferred until data from WS3 import populates OutcomeTracker.

**Key constraint:** Agentic coding REQUIRES cloud models (Sonnet/Opus). Local 9B is insufficient for reliable tool chaining.

**Security model:** Defense-in-depth:
1. Sandbox allowlist (path-level control)
2. Soft delete (no permanent file destruction)
3. Test verification (pre/post for self-modification)
4. Git diff review (stream to client)
5. Human approval gate (always for code changes)

---

### Task 4.0: Proof-of-Concept — Multi-Tool API Call (Audit #7)

Before building the full loop, validate that Anthropic's API reliably chains Hestia's tool definitions.

- [ ] **Step 1: Send multi-tool prompt to Anthropic API**

Create a test script that sends a prompt like "Read hestia/memory/models.py, find the MemorySource enum, and tell me what values it has" with Hestia's file tool definitions. Verify the model:
- Correctly calls `read_file` with the right path
- Parses the result
- Produces a coherent summary
- Does NOT hallucinate tool names

- [ ] **Step 2: Test 3-step chain**

Send: "Read hestia/memory/models.py, then read hestia/memory/database.py, then tell me which models are stored in which tables."
Verify: Model chains 2 read_file calls and synthesizes correctly.

- [ ] **Step 3: Document findings**

If model chains reliably: proceed with WS4.
If model hallucinates or fails: adjust tool definitions, add few-shot examples, or constrain to simpler patterns.

---

### Task 4.1: Phase 0 — Tool Foundation

Expand Hestia's tool palette to match Claude Code's capabilities.

**Files:**
- Create: `hestia/execution/tools/code_tools.py` (edit_file, glob, grep)
- Create: `hestia/execution/tools/git_tools.py` (status, diff, add, commit, log)
- Modify: `hestia/config/execution.yaml` (add ~/hestia to allowlist)
- Modify: `hestia/execution/registry.py` (register new tools)
- Create: `tests/test_code_tools.py`
- Create: `tests/test_git_tools.py`

- [ ] **Step 1: Write failing tests for edit_file tool**

```python
# tests/test_code_tools.py
"""Tests for code editing tools."""
import pytest
import asyncio
import tempfile
import os


class TestEditFileTool:
    def test_edit_replaces_exact_match(self, tmp_path):
        """edit_file replaces old_string with new_string."""
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")
        # call edit_file tool
        from hestia.execution.tools.code_tools import edit_file
        result = asyncio.get_event_loop().run_until_complete(
            edit_file(str(f), "return 'world'", "return 'hello world'")
        )
        assert "return 'hello world'" in f.read_text()
        assert result["success"] is True

    def test_edit_fails_if_old_string_not_found(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")
        from hestia.execution.tools.code_tools import edit_file
        result = asyncio.get_event_loop().run_until_complete(
            edit_file(str(f), "nonexistent string", "replacement")
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_edit_fails_if_old_string_not_unique(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\nx = 1\n")
        from hestia.execution.tools.code_tools import edit_file
        result = asyncio.get_event_loop().run_until_complete(
            edit_file(str(f), "x = 1", "x = 2")
        )
        assert result["success"] is False
        assert "not unique" in result["error"].lower() or "multiple" in result["error"].lower()
```

- [ ] **Step 2: Implement edit_file, glob_files, grep_files tools**

```python
# hestia/execution/tools/code_tools.py
"""Code editing tools for agentic development."""

async def edit_file(file_path: str, old_string: str, new_string: str) -> Dict:
    """Replace old_string with new_string in file. Fails if not unique."""
    ...

async def glob_files(pattern: str, path: str = ".") -> Dict:
    """Find files matching glob pattern."""
    ...

async def grep_files(pattern: str, path: str = ".", file_glob: str = "*") -> Dict:
    """Search file contents with regex."""
    ...
```

All tools go through PathValidator for sandbox enforcement.

- [ ] **Step 3: Write failing tests for git tools**

```python
# tests/test_git_tools.py
class TestGitTools:
    def test_git_status(self, tmp_path):
        """git_status returns current repo state."""
        ...

    def test_git_diff_shows_changes(self, tmp_path):
        """git_diff returns unstaged changes."""
        ...

    def test_git_commit_creates_commit(self, tmp_path):
        """git_commit stages and commits."""
        ...

    def test_git_commit_rejects_force_push(self, tmp_path):
        """No force push allowed."""
        ...
```

- [ ] **Step 4: Implement git tools**

```python
# hestia/execution/tools/git_tools.py
"""Git tools for agentic development. No force operations allowed."""

BLOCKED_GIT_OPERATIONS = {"push --force", "reset --hard", "clean -f", "branch -D"}

async def git_status() -> Dict: ...
async def git_diff(staged: bool = False) -> Dict: ...
async def git_add(files: List[str]) -> Dict: ...
async def git_commit(message: str) -> Dict:
    # Audit condition #5: prefix automated commits
    prefixed = f"[hestia-auto] {message}"
    ...
async def git_log(count: int = 10) -> Dict: ...
```

- [ ] **Step 5: Update execution.yaml — add ~/hestia to allowlist (audit #2)**

```yaml
allowed_directories:
  - ~/hestia/data
  - ~/hestia/logs
  - ~/hestia          # NEW: source code access for agentic development
  - /tmp/hestia
  # ... existing entries

# Audit condition #2: paths that edit_file must NEVER write to
agentic_denied_paths:
  - hestia/security/     # Security module is never self-modifiable
  - hestia/config/       # Config changes require human review
  - .env                 # Environment files
  - .claude/             # Claude Code config
```

- [ ] **Step 6: Register tools in registry**

Update `hestia/execution/registry.py` to register code_tools and git_tools.

- [ ] **Step 7: Run all new tests + existing tool tests**

```bash
python -m pytest tests/test_code_tools.py tests/test_git_tools.py tests/test_tools.py -v --timeout=30
```

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: code editing + git tools for agentic development (Phase 0)"
```

---

### Task 4.2: Phase 1 — Iterative Tool Loop

The single biggest architectural gap. Add `handle_agentic()` that implements the while(tool_call) loop.

**Files:**
- Modify: `hestia/orchestration/handler.py` (add `handle_agentic()`)
- Modify: `hestia/api/routes/chat.py` (add agentic endpoint or mode)
- Modify: `hestia/council/manager.py` (add CODING intent that forces cloud)
- Create: `tests/test_agentic_handler.py`

- [ ] **Step 1: Write failing tests for iterative loop**

```python
# tests/test_agentic_handler.py
"""Tests for the agentic tool loop."""

class TestAgenticHandler:
    def test_single_tool_call_returns(self):
        """Model calls one tool, sees result, produces final response."""
        ...

    def test_multi_step_tool_chain(self):
        """Model chains: read_file → edit_file → read_file (verify)."""
        ...

    def test_loop_terminates_at_max_iterations(self):
        """Loop stops after max_iterations even if model wants more tools."""
        ...

    def test_loop_terminates_on_natural_stop(self):
        """Loop stops when model produces text response with no tool calls."""
        ...

    def test_loop_tracks_token_budget(self):
        """Token usage is tracked and loop warns at 70% budget."""
        ...

    def test_coding_intent_forces_cloud(self):
        """CODING intent routes to cloud model, not local."""
        ...
```

- [ ] **Step 2: Add CODING intent to council**

Modify `hestia/council/manager.py` — add `IntentType.CODING` that the fast-path and SLM can classify. When detected, force cloud routing.

- [ ] **Step 3: Implement handle_agentic() as NEW method (audit #3)**

This is a NEW method — never modify existing `handle()` or `handle_streaming()`.
The production chat pipeline must remain untouched.

Core loop structure:
```python
async def handle_agentic(self, request: Request) -> AsyncGenerator[StreamEvent, None]:
    """Agentic tool loop — iterates until model stops calling tools.

    NOTE: This is a separate method from handle()/handle_streaming().
    The production chat pipeline is not modified. (Audit condition #3)
    """
    messages = self._build_initial_messages(request)
    iteration = 0

    while iteration < self.max_agentic_iterations:
        response = await self._call_inference(messages, tools=self.tool_definitions)

        # Yield any text content as streaming tokens
        if response.content:
            yield StreamEvent(type="token", content=response.content)

        # Check for tool calls
        if not response.tool_calls:
            break  # Natural termination

        # Execute tools and feed results back
        for tool_call in response.tool_calls:
            yield StreamEvent(type="tool_start", tool=tool_call.name)
            result = await self.tool_executor.execute(tool_call)
            yield StreamEvent(type="tool_result", result=result)
            messages.append(tool_call_message(tool_call, result))

        iteration += 1

    yield StreamEvent(type="done", iterations=iteration)
```

- [ ] **Step 4: Wire into streaming endpoint**

Add `POST /v1/chat/agentic` or add `agentic: true` flag to existing `/v1/chat/stream`.

- [ ] **Step 5: Run tests, commit**

```bash
python -m pytest tests/test_agentic_handler.py tests/test_handler.py -v --timeout=30
git commit -m "feat: iterative tool loop for agentic coding (Phase 1)"
```

---

### Task 4.3: Phase 2 — Self-Aware Coding

Add verification layer for when Hestia modifies her own source code.

**Files:**
- Create: `hestia/execution/verification.py` (self-modification detection + test runner)
- Modify: `hestia/orchestration/handler.py` (wire verification into agentic loop)
- Create: `tests/test_verification.py`

- [ ] **Step 1: Write failing tests for self-modification detection**

```python
class TestSelfModificationDetection:
    def test_detects_own_source_code(self):
        """Edits to ~/hestia/hestia/ trigger verification."""
        from hestia.execution.verification import is_self_modification
        assert is_self_modification("/Users/andrewlonati/hestia/hestia/memory/manager.py")
        assert is_self_modification("/Users/andrewlonati/hestia/tests/test_memory.py")

    def test_ignores_data_files(self):
        """Edits to ~/hestia/data/ do not trigger verification."""
        from hestia.execution.verification import is_self_modification
        assert not is_self_modification("/Users/andrewlonati/hestia/data/user/MEMORY.md")

    def test_runs_matching_test_file(self):
        """Editing memory/manager.py runs tests/test_memory.py."""
        from hestia.execution.verification import find_test_file
        assert find_test_file("hestia/memory/manager.py") == "tests/test_memory.py"
```

- [ ] **Step 2: Implement verification layer**

```python
# hestia/execution/verification.py
"""Verification layer for self-modification safety."""

SELF_PATHS = ["hestia/hestia/", "hestia/tests/", "hestia/hestia-cli/"]

def is_self_modification(file_path: str) -> bool: ...
def find_test_file(source_path: str) -> Optional[str]: ...

async def verify_self_modification(
    file_path: str,
    pre_content: str,
    post_content: str,
) -> VerificationResult:
    """Run matching tests before and after edit. Return diff + test results."""
    ...
```

- [ ] **Step 3: Add context compaction**

When accumulated tokens exceed 60% of context window, summarize older messages:
```python
async def compact_context(messages: List[Dict], inference_client) -> List[Dict]:
    """Summarize older messages while preserving recent tool results."""
    ...
```

- [ ] **Step 4: Wire into agentic loop**

In `handle_agentic()`, after each edit_file tool call:
1. Check `is_self_modification()`
2. If yes, run `verify_self_modification()`
3. Stream verification results to client
4. If tests fail, yield approval request event

- [ ] **Step 5: Run full test suite, commit**

```bash
python -m pytest tests/ -v --timeout=30
git commit -m "feat: self-modification verification layer (Phase 2)"
```

---

### Task 4.4: CLI Agentic Mode

Wire the CLI to support agentic sessions.

**Files:**
- Modify: `hestia-cli/hestia_cli/commands.py` (add `/agentic` or `/code` command)
- Modify: `hestia-cli/hestia_cli/renderer.py` (render tool call chain)
- Modify: `hestia-cli/hestia_cli/models.py` (add agentic event types)

- [ ] **Step 1: Add agentic event types to CLI models**

```python
class ServerEventType(str, Enum):
    # ... existing ...
    TOOL_START = "tool_start"
    AGENTIC_DONE = "agentic_done"
    VERIFICATION = "verification"
    APPROVAL_REQUEST = "approval_request"
```

- [ ] **Step 2: Add `/code` command to CLI**

```
/code fix the typo in hestia/memory/manager.py line 42
```

Routes to agentic endpoint with CODING intent forced.

- [ ] **Step 3: Render tool chains in CLI**

Show each tool call with result in a Rich panel:
```
[Tool] read_file → hestia/memory/manager.py (245 lines)
[Tool] edit_file → replaced "teh" with "the" ✓
[Tool] git_diff → 1 file changed, 1 insertion, 1 deletion
[Verify] test_memory.py: 42 passed, 0 failed ✓
```

- [ ] **Step 4: Run CLI tests, commit**

```bash
cd hestia-cli && python -m pytest tests/ -v --timeout=30
git commit -m "feat: CLI agentic mode with /code command (Phase 2)"
```

---

## Sprint 13 Summary

| WS | Tasks | Est. Sessions | Key Deliverable |
|----|-------|--------------|-----------------|
| 1 | 1.1-1.4 | 1-2 | Complete knowledge graph (episodic nodes, temporal queries, auto-extraction) |
| 2 | 2.1-2.2 | 1-2 | iOS trimmed, macOS gaps filled (memory review, proactive, health, neural net) |
| 3 | 3.1-3.3 | 1-2 | Claude history imported (78 convos, 796 msgs → memory + facts + episodic nodes) |
| 4 | 4.1-4.4 | 2-3 | Agentic coding (tool loop, code tools, git tools, verification, CLI /code) |

**Total:** ~6-8 sessions (~12-16 hours)

**Dependencies:**
- WS3 depends on WS1 (episodic nodes for conversation → graph linkage)
- WS4 is independent and can be parallelized with WS1-2

**Gate 2 (Sprint 11B MetaMonitor) readiness after Sprint 13:**
- Memory corpus dramatically enriched (78 Claude conversations + Apple ecosystem + ongoing chat)
- Knowledge graph has temporal queries + auto-extraction
- OutcomeTracker has more diverse signal
- Decision: evaluate after WS3 completes

**What this does NOT include (deferred):**
- Phase 3 Learning Cycle (PrincipleStore for coding patterns) — needs data from WS3+WS4
- OpenAI history import (Andrew will pull data later — same parser pattern, different format)
- Sprint 11B MetaMonitor (Gate 2 evaluation after memory backfill)
- O5 MLX benchmark (independent, low priority)
- Google Workspace CLI integration (approved but independent)
- Bright Data MCP (independent, low effort)
