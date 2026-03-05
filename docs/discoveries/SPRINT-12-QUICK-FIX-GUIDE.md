# Sprint 12 Quick Fix Guide

Copy-paste solutions for all 6 blockers. Implement in this order.

---

## Blocker 1: Add MemorySource Enum (15 min)

**File:** `hestia/memory/models.py` (after line 41)

```python
class MemorySource(Enum):
    """Origin of memory chunk."""
    CONVERSATION = "conversation"
    MAIL = "mail"
    CALENDAR = "calendar"
    REMINDERS = "reminders"
    NOTES = "notes"
    HEALTH = "health"
    BACKGROUND_TASK = "background_task"
    IMPORT = "import"
```

Then update `ChunkMetadata` (line 96):
```python
# OLD:
source: Optional[str] = None

# NEW:
source: Optional[MemorySource] = None
```

And serialization (lines 109, 124):
```python
# to_dict() line 109:
"source": self.source.value if self.source else None,

# from_dict() line 124:
source=MemorySource(data.get("source")) if data.get("source") else None,
```

Add to `MemoryQuery` (line 236):
```python
sources: Optional[List[MemorySource]] = None
```

---

## Blocker 2: Update MemoryManager Signatures (20 min)

**File:** `hestia/memory/manager.py`

**Change 1 — Line 207 (store method):**
```python
# OLD:
async def store(
    self,
    content: str,
    chunk_type: ChunkType = ChunkType.CONVERSATION,
    tags: Optional[ChunkTags] = None,
    metadata: Optional[ChunkMetadata] = None,
    session_id: Optional[str] = None,
    auto_tag: bool = True,
    scope: MemoryScope = MemoryScope.SESSION,
) -> ConversationChunk:

# NEW:
async def store(
    self,
    content: str,
    chunk_type: ChunkType = ChunkType.CONVERSATION,
    tags: Optional[ChunkTags] = None,
    metadata: Optional[ChunkMetadata] = None,
    session_id: Optional[str] = None,
    auto_tag: bool = True,
    scope: MemoryScope = MemoryScope.SESSION,
    source: Optional[MemorySource] = None,  # ADD
) -> ConversationChunk:
```

**Change 2 — Line 243 (chunk creation):**
```python
# OLD:
chunk = ConversationChunk.create(
    content=content,
    session_id=session_id,
    chunk_type=chunk_type,
    tags=tags,
    metadata=metadata,
    scope=scope,
)

# NEW:
chunk = ConversationChunk.create(
    content=content,
    session_id=session_id,
    chunk_type=chunk_type,
    tags=tags,
    metadata=metadata,
    scope=scope,
    source=source,  # ADD
)
```

**Change 3 — Line 299 (store_exchange method):**
```python
# OLD:
async def store_exchange(
    self,
    user_message: str,
    assistant_response: str,
    mode: Optional[str] = None,
) -> tuple[ConversationChunk, ConversationChunk]:

# NEW:
async def store_exchange(
    self,
    user_message: str,
    assistant_response: str,
    mode: Optional[str] = None,
    source: Optional[MemorySource] = None,  # ADD
) -> tuple[ConversationChunk, ConversationChunk]:
```

**Change 4 — Lines 320, 326 (store_exchange calls):**
```python
# OLD:
user_chunk = await self.store(
    content=f"User: {user_message}",
    chunk_type=ChunkType.CONVERSATION,
    tags=tags,
)

assistant_chunk = await self.store(
    content=f"Assistant: {assistant_response}",
    chunk_type=ChunkType.CONVERSATION,
    tags=tags,
    auto_tag=True,
)

# NEW:
user_chunk = await self.store(
    content=f"User: {user_message}",
    chunk_type=ChunkType.CONVERSATION,
    tags=tags,
    source=source,  # ADD
)

assistant_chunk = await self.store(
    content=f"Assistant: {assistant_response}",
    chunk_type=ChunkType.CONVERSATION,
    tags=tags,
    auto_tag=True,
    source=source,  # ADD
)
```

---

## Blocker 3: Update Handler Call (5 min)

**File:** `hestia/orchestration/handler.py` (line 1229)

```python
# OLD:
await memory.store_exchange(
    user_message=request.content,
    assistant_response=response.content,
    mode=request.mode.value,
)

# NEW:
await memory.store_exchange(
    user_message=request.content,
    assistant_response=response.content,
    mode=request.mode.value,
    source=MemorySource.CONVERSATION,  # ADD
)
```

Also add import at top of handler.py:
```python
from hestia.memory.models import MemorySource
```

---

## Blocker 4: Add Database Source Filtering (20 min)

**File:** `hestia/memory/database.py` (after line 296)

Add after status filter condition:
```python
# After line 296 (status filter):
if query.sources:
    source_values = [s.value for s in query.sources]
    placeholders = ",".join("?" * len(source_values))
    conditions.append(f"json_extract(metadata, '$.source') IN ({placeholders})")
    params.extend(source_values)
```

---

## Blocker 5: Make PrincipleStore Async (45 min)

**File:** `hestia/research/principle_store.py`

**Change 1 — Lines 56-74 (initialize method):**
```python
# OLD:
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

# NEW:
async def initialize(self, persist_directory: Optional[Path] = None) -> None:
    """Initialize ChromaDB client and collection."""
    import asyncio
    
    if persist_directory is None:
        persist_directory = Path.home() / "hestia" / "data" / "chromadb"

    persist_directory.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_event_loop()
    
    # Create PersistentClient in executor (blocking operation)
    def _create_client():
        return chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
    
    self._client = await loop.run_in_executor(None, _create_client)

    # Get or create collection (also blocking)
    def _get_collection():
        return self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    
    self._collection = await loop.run_in_executor(None, _get_collection)
```

**Change 2 — Add guards to all methods that use `_collection`:**

At the start of `store_principle()` (line 85):
```python
if self._collection is None:
    raise RuntimeError("PrincipleStore not initialized. Call initialize() first.")
```

At the start of `search_principles()` (line 114):
```python
if self._collection is None:
    raise RuntimeError("PrincipleStore not initialized. Call initialize() first.")
```

At the start of `_distill_principles()` (line 139):
```python
# Already returns empty list on failure, but add guard:
if self._collection is None:
    logger.warning("PrincipleStore not initialized")
    return []
```

At the start of `get_collection_count()` (line 260):
```python
if self._collection is None:
    return 0
```

---

## Blocker 6: Refactor HestiaRenderer + Animation (2-3 hours)

**File:** `hestia-cli/hestia_cli/renderer.py`

Replace entire file with refactored version:

```python
"""
Rich terminal renderer for Hestia CLI — Refactored for async animations.
"""

import asyncio
import sys
from enum import Enum
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.text import Text

from hestia_cli.models import (
    DoneMetrics, PipelineStage, STAGE_LABELS, ToolRequest,
    COMMON_VERBS, TIA_VERBS, OLLY_VERBS, MIRA_VERBS,
    FIRE_FRAMES
)


class RenderState(Enum):
    """Renderer state machine."""
    IDLE = "idle"
    STATUS = "status"
    THINKING = "thinking"
    STREAMING = "streaming"
    DONE = "done"


class ThinkingAnimation:
    """Async animation loop for thinking/generating state."""

    def __init__(self, agent_name: str, agent_color: str):
        self._agent_name = agent_name
        self._agent_color = agent_color
        self._task: Optional[asyncio.Task] = None
        self._frame = 0
        self._verb_index = 0

    async def start(self):
        """Start animation loop."""
        self._task = asyncio.create_task(self._animate_loop())

    async def stop(self):
        """Stop animation and clear line."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _clear_line()

    async def _animate_loop(self):
        """Main animation loop: fire frames + verb rotation."""
        verbs = self._select_verbs()
        verb_cycle_frames = 10  # Change verb every 10 frames
        frame_count = 0

        try:
            while True:
                fire_frame = FIRE_FRAMES[self._frame % len(FIRE_FRAMES)]
                verb_index = (frame_count // verb_cycle_frames) % len(verbs)
                verb = verbs[verb_index]

                _clear_line()
                sys.stdout.write(f"{fire_frame} {verb}...")
                sys.stdout.flush()

                self._frame += 1
                frame_count += 1
                await asyncio.sleep(0.2)  # 200ms per fire frame

        except asyncio.CancelledError:
            pass

    def _select_verbs(self) -> List[str]:
        """Select verb list based on agent."""
        agent_lower = self._agent_name.lower()
        if "tia" in agent_lower:
            return COMMON_VERBS + TIA_VERBS
        elif "olly" in agent_lower:
            return COMMON_VERBS + OLLY_VERBS
        elif "mira" in agent_lower:
            return COMMON_VERBS + MIRA_VERBS
        else:
            return COMMON_VERBS


def _clear_line() -> None:
    """Clear current terminal line using ANSI."""
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


class HestiaRenderer:
    """Renders Hestia events with animation support."""

    def __init__(self, console: Optional[Console] = None, show_metrics: bool = True):
        self.console = console or Console()
        self.show_metrics = show_metrics
        self._streaming_buffer = ""
        self._state = RenderState.IDLE
        self._animation: Optional[ThinkingAnimation] = None
        self._agent_name = "Hestia"
        self._agent_color = "#FF9500"

    def render_event(self, event: Dict[str, Any]) -> None:
        """Dispatch event to appropriate renderer."""
        event_type = event.get("type", "")

        if event_type == "status":
            self._render_status(event)
        elif event_type == "token":
            self._render_token(event)
        elif event_type == "tool_request":
            self._render_tool_request(event)
        elif event_type == "tool_result":
            self._render_tool_result(event)
        elif event_type == "done":
            self._render_done(event)
        elif event_type == "error":
            self._render_error(event)
        elif event_type == "pong":
            pass  # Silent

    def set_agent(self, name: str, color: str) -> None:
        """Set agent for rendering."""
        self._agent_name = name
        self._agent_color = color

    def start_streaming(self) -> None:
        """Begin streaming response."""
        self._streaming_buffer = ""
        self._state = RenderState.IDLE

    def finish_streaming(self) -> None:
        """Finalize streaming output."""
        self._streaming_buffer = ""
        self._state = RenderState.IDLE

    def render_startup_banner(
        self,
        server_url: str,
        mode: str,
        device_id: Optional[str] = None,
        trust_tiers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Render startup banner."""
        self.console.print()
        self.console.print(
            f"[bold]Hestia CLI[/bold] v0.1 — connected to [cyan]{server_url}[/cyan]"
        )
        info_parts = [f"[{self._agent_color}]@{mode}[/]"]
        if device_id:
            info_parts.append(f"device:{device_id[:8]}")
        if trust_tiers:
            tier_summary = " ".join(
                f"{k}={'[green]auto[/green]' if v == 'auto' else '[yellow]prompt[/yellow]'}"
                for k, v in trust_tiers.items()
            )
            info_parts.append(f"trust: {tier_summary}")
        self.console.print(" | ".join(info_parts))
        self.console.print(
            "[dim]Type a message to chat. /help for commands. Ctrl+C to cancel. Ctrl+D to exit.[/dim]"
        )
        self.console.print()

    # --- Private renderers ---

    def _render_status(self, event: Dict[str, Any]) -> None:
        """Show status with animation for inference stage."""
        stage = event.get("stage", "")

        if stage == "inference":
            # Start thinking animation
            self._state = RenderState.THINKING
            self._animation = ThinkingAnimation(self._agent_name, self._agent_color)
            asyncio.create_task(self._animation.start())
        else:
            # Simple status for other stages
            label = STAGE_LABELS.get(stage, event.get("detail", stage))
            _clear_line()
            self.console.print(f"  [dim]⟳ {label}...[/dim]", end="")
            self._state = RenderState.STATUS

    def _render_token(self, event: Dict[str, Any]) -> None:
        """Render streaming token."""
        content = event.get("content", "")
        
        # Stop animation if running
        if self._animation and self._state == RenderState.THINKING:
            asyncio.create_task(self._animation.stop())
            self._animation = None

        if self._state != RenderState.STREAMING:
            _clear_line()
            self.console.print()  # Blank line before response
            self.console.print(f"[{self._agent_color}]{self._agent_name}:[/]")
            self._state = RenderState.STREAMING

        if content:
            self._streaming_buffer += content
            self.console.print(content, end="", highlight=False)

    def _render_tool_request(self, event: Dict[str, Any]) -> None:
        """Render tool approval request."""
        from rich.panel import Panel
        
        req = ToolRequest(**{k: v for k, v in event.items() if k != "type"})
        self.console.print()

        args_display = ""
        if req.arguments:
            args_lines = [f"  {k}: {v}" for k, v in req.arguments.items()]
            args_display = "\n".join(args_lines)

        panel_content = f"[bold]{req.tool_name}[/bold]\n{args_display}\n[dim]tier: {req.tier}[/dim]"
        self.console.print(Panel(
            panel_content,
            title="Tool Request",
            border_style="yellow",
            width=60,
        ))

    def _render_tool_result(self, event: Dict[str, Any]) -> None:
        """Render tool result."""
        status = event.get("status", "")
        output = event.get("output", "")

        if status == "denied":
            self.console.print("[yellow]Tool execution denied.[/yellow]")
        elif status == "error":
            self.console.print(f"[red]Tool error: {output}[/red]")

    def _render_done(self, event: Dict[str, Any]) -> None:
        """Render completion."""
        if self._state == RenderState.THINKING and self._animation:
            asyncio.create_task(self._animation.stop())

        self.console.print()  # Newline after streaming
        self._state = RenderState.DONE

        if self.show_metrics:
            metrics = event.get("metrics", {})
            tokens_out = metrics.get("tokens_out", 0)
            duration = metrics.get("duration_ms", 0)
            model = metrics.get("model", "")
            cached = metrics.get("cached", False)

            parts = []
            if tokens_out:
                parts.append(f"{tokens_out} tokens")
            if duration:
                parts.append(f"{duration/1000:.1f}s")
            if model:
                parts.append(model)
            if cached:
                parts.append("cached")

            if parts:
                self.console.print(f"[dim]  {' · '.join(parts)}[/dim]")
        self.console.print()

    def _render_error(self, event: Dict[str, Any]) -> None:
        """Render error message."""
        if self._state == RenderState.THINKING and self._animation:
            asyncio.create_task(self._animation.stop())

        code = event.get("code", "error")
        message = event.get("message", "Unknown error")
        self.console.print(f"\n[red]Error ({code}): {message}[/red]\n")
        self._state = RenderState.IDLE
```

---

## After All Blockers Fixed

Run verification:
```bash
mypy hestia/memory/ --strict
python -m pytest tests/memory/ tests/research/ -v
python -c "from hestia.memory import MemoryManager, MemorySource"
```

If all pass, you're ready for Sprint 12A/B feature work!

---

## Time Breakdown

- Blocker 1 (enum): 15 min
- Blocker 2 (signatures): 20 min
- Blocker 3 (handler): 5 min ← **TOTAL SO FAR: 40 min**
- Blocker 4 (database): 20 min ← **TOTAL SO FAR: 60 min**
- Blocker 5 (PrincipleStore): 45 min ← **TOTAL SO FAR: 105 min**
- Blocker 6 (Renderer): 2-3 hours ← **GRAND TOTAL: 3-3.5 hours**

All 6 blockers can be fixed in one focused session.

