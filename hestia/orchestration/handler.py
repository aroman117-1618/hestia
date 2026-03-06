"""
Request handler for Hestia orchestration.

Main entry point for processing requests through the complete pipeline:
Request -> Validation -> Memory Retrieval -> Prompt Building -> Inference -> [Tool Execution] -> Response
"""

import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

from hestia.logging import get_logger, LogComponent
from hestia.inference import get_inference_client, InferenceClient, Message
from hestia.inference.client import InferenceResponse
from hestia.memory import get_memory_manager, MemoryManager
from hestia.orchestration.models import (
    Request,
    RequestSource,
    Response,
    ResponseType,
    Task,
    Conversation,
)
from hestia.orchestration.state import TaskStateMachine, TaskTimeoutError
from hestia.orchestration.mode import ModeManager, get_mode_manager
from hestia.orchestration.prompt import PromptBuilder, get_prompt_builder
from hestia.orchestration.validation import (
    ValidationPipeline,
    get_validation_pipeline,
)
from hestia.execution import (
    ToolExecutor,
    ToolCall,
    ToolResult,
    get_tool_executor,
    get_tool_registry,
    register_builtin_tools,
)
from hestia.council.manager import CouncilManager, get_council_manager
from hestia.council.models import IntentClassification, IntentType
from hestia.orchestration.cache import get_response_cache


# ─────────────────────────────────────────────────────────────────────────────
# TOOL USAGE INSTRUCTIONS
# Injected into every chat system prompt so the LLM knows its capabilities.
# Grouped by domain with clear routing guidance for local models.
# ─────────────────────────────────────────────────────────────────────────────
TOOL_INSTRUCTIONS = """
## Your Tools

You have 34 tools across 7 categories. When the user asks about their data, you MUST call the appropriate tool. NEVER say you lack access — use the tool.

### Notes (Apple Notes)
- **read_note(query)** — READ a specific note by name/topic. Fuzzy-matches the title automatically. USE THIS when the user says "show me", "read", "open", "what does my note say", or names a specific note.
- **search_notes(query)** — SEARCH across all notes for a keyword or phrase.
- **find_note(query)** — FIND a note by title when you need metadata (folder, dates) without full content.
- **list_notes(folder)** — LIST all note titles in a folder (or all folders if omitted).
- **list_note_folders()** — LIST available note folders.
- **create_note(title, body, folder)** — CREATE a new note.

### Calendar
- **get_today_events()** — Get today's schedule. Use for "what's on today?" or "my schedule".
- **list_events(days_ahead)** — List upcoming events for the next N days.
- **find_event(query)** — Find a specific event by name or keyword.
- **create_event(title, start_time, end_time)** — Schedule a new event.
- **list_calendars()** — List available calendars.

### Reminders
- **get_due_reminders()** — Get reminders due today. Use for "what do I need to do?"
- **get_overdue_reminders()** — Get overdue/past-due reminders.
- **list_reminders(list_name)** — List reminders in a specific list.
- **list_reminder_lists()** — List available reminder lists.
- **create_reminder(title, due_date, list_name)** — Create a new reminder.
- **complete_reminder(id)** — Mark a reminder as complete.

### Mail (Apple Mail)
- **get_recent_emails(count)** — Get the most recent emails.
- **search_emails(query, sender, days_back)** — Search emails by keyword, sender, or date range.
- **get_unread_count()** — Get the count of unread emails.
- **get_flagged_emails()** — Get flagged/starred emails.
- **list_mailboxes()** — List available mailboxes.

### Health (Apple HealthKit)
- **get_health_summary(days)** — Overview of recent health metrics.
- **get_health_trend(metric, days)** — Trend data for a specific metric over time.
- **get_sleep_analysis(days)** — Sleep duration and quality analysis.
- **get_activity_report(days)** — Exercise, steps, and activity data.
- **get_vitals(days)** — Heart rate, blood pressure, and other vitals.

### Files & Shell
- **read_file(path)** — Read a file from the filesystem.
- **write_file(path, content)** — Write content to a file.
- **list_directory(path)** — List files in a directory.
- **search_files(query, path)** — Search for files by name.
- **run_command(command)** — Execute a shell command.

### Web Investigation
- **investigate_url(url)** — Analyze a web article or YouTube video.
- **investigate_compare(urls)** — Compare multiple sources.

## Rules
1. ALWAYS use the right tool — never fabricate data or say you can't access something.
2. For notes: use **read_note** to read, **search_notes** to search, **list_notes** to browse.
3. If a tool fails, tell the user what went wrong and suggest an alternative.
4. You can chain tools: e.g., list_notes to find the name, then read_note to get content.
"""


class RequestHandler:
    """
    Main entry point for all requests.

    Orchestrates:
    - Request validation
    - Mode detection and switching
    - Memory retrieval
    - Prompt construction
    - Inference
    - Response validation
    - Memory storage
    """

    def __init__(
        self,
        inference_client: Optional[InferenceClient] = None,
        memory_manager: Optional[MemoryManager] = None,
        mode_manager: Optional[ModeManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        validation_pipeline: Optional[ValidationPipeline] = None,
        tool_executor: Optional[ToolExecutor] = None,
    ):
        """
        Initialize request handler.

        All components are optional and will use singletons if not provided.
        """
        self._inference_client = inference_client
        self._memory_manager = memory_manager
        self._mode_manager = mode_manager or get_mode_manager()
        self._prompt_builder = prompt_builder or get_prompt_builder()
        self._validation_pipeline = validation_pipeline or get_validation_pipeline()
        self._tool_executor = tool_executor
        self._council_manager: Optional[CouncilManager] = None

        self.state_machine = TaskStateMachine()
        self.logger = get_logger()

        # Session conversations cache
        self._conversations: dict[str, Conversation] = {}
        self._handle_count: int = 0

        # Register built-in tools
        self._register_builtin_tools()

    @property
    def inference_client(self) -> InferenceClient:
        """Lazy-load inference client."""
        if self._inference_client is None:
            self._inference_client = get_inference_client()
        return self._inference_client

    async def _get_memory_manager(self) -> MemoryManager:
        """Get or create memory manager instance (async lazy-load)."""
        if self._memory_manager is None:
            self._memory_manager = await get_memory_manager()
        return self._memory_manager

    async def _get_tool_executor(self) -> ToolExecutor:
        """Get or create tool executor."""
        if self._tool_executor is None:
            self._tool_executor = await get_tool_executor()
        return self._tool_executor

    def _get_council_manager(self) -> CouncilManager:
        """Get or create council manager."""
        if self._council_manager is None:
            self._council_manager = get_council_manager()
        return self._council_manager

    def _register_builtin_tools(self) -> None:
        """Register built-in tools with the registry."""
        try:
            registry = get_tool_registry()
            # Only register if not already registered
            if len(registry) == 0:
                register_builtin_tools(registry)
                self.logger.info(
                    f"Registered {len(registry)} built-in tools",
                    component=LogComponent.ORCHESTRATION
                )
        except Exception as e:
            self.logger.warning(
                f"Failed to register built-in tools: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION
            )

    # Default session timeout (minutes) if user settings unavailable
    _DEFAULT_SESSION_TIMEOUT = 30

    # Cleanup runs every N handle() calls
    _CLEANUP_INTERVAL = 20

    def _is_session_expired(
        self, conversation: Conversation, timeout_minutes: int
    ) -> bool:
        """Check if a conversation has exceeded its inactivity timeout."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        elapsed = now - conversation.last_activity
        return elapsed > timedelta(minutes=timeout_minutes)

    async def _get_session_timeout(self) -> int:
        """Get session timeout from user settings, with default fallback."""
        try:
            from hestia.user import get_user_manager
            manager = await get_user_manager()
            settings = await manager.get_settings()
            timeout = settings.auto_lock_timeout_minutes
            if timeout and timeout > 0:
                return timeout
        except Exception:
            pass
        return self._DEFAULT_SESSION_TIMEOUT

    def _get_or_create_conversation(self, session_id: str) -> Conversation:
        """Get or create a conversation for a session."""
        if session_id not in self._conversations:
            self._conversations[session_id] = Conversation(session_id=session_id)
        return self._conversations[session_id]

    async def _get_or_create_conversation_with_ttl(
        self, session_id: str
    ) -> Conversation:
        """
        Get or create a conversation, expiring stale sessions.

        If the existing conversation has exceeded the inactivity timeout,
        it is removed and a fresh one is created.
        """
        timeout = await self._get_session_timeout()

        if session_id in self._conversations:
            existing = self._conversations[session_id]
            if self._is_session_expired(existing, timeout):
                self.logger.info(
                    f"Session expired after {timeout}min inactivity, creating new",
                    component=LogComponent.ORCHESTRATION,
                    data={
                        "session_id": session_id,
                        "turns": existing.turn_count,
                    },
                )
                del self._conversations[session_id]

        return self._get_or_create_conversation(session_id)

    def _cleanup_expired_sessions(self, timeout_minutes: int) -> int:
        """
        Remove expired conversations from the in-memory cache.

        Returns the number of sessions evicted.
        """
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        expired_ids = [
            sid
            for sid, conv in self._conversations.items()
            if (now - conv.last_activity) > timedelta(minutes=timeout_minutes)
        ]

        for sid in expired_ids:
            self.logger.info(
                f"Evicting expired session: {sid}",
                component=LogComponent.ORCHESTRATION,
                data={"turns": self._conversations[sid].turn_count},
            )
            del self._conversations[sid]

        return len(expired_ids)

    def _will_route_to_cloud(self, content: str, force_local: bool = False) -> bool:
        """Predict whether this request will route to cloud.

        Returns True only for enabled_full state. enabled_smart is treated
        as local since routing depends on token count (unpredictable here).

        Args:
            content: Request content (unused currently, reserved for future).
            force_local: If True, always returns False.
        """
        if force_local:
            return False
        try:
            return self.inference_client.router.cloud_routing.state == "enabled_full"
        except Exception:
            return False

    async def _apply_local_persona(self, raw_content: str, request: Request) -> str:
        """Re-render a cloud response with the local persona voice.

        Calls Ollama directly (bypasses router) so this always stays local.
        Used for non-CHAT intents to add Tia/Mira/Olly personality to
        responses generated by a generic cloud prompt.

        Args:
            raw_content: The cloud-generated response text.
            request: Original request (for mode and content).

        Returns:
            Personality-rendered content, or raw_content on failure.
        """
        persona_prompt = self._prompt_builder.build_system_prompt(mode=request.mode)
        messages = [
            Message(role="user", content=request.content),
            Message(role="assistant", content=raw_content),
            Message(role="user", content=(
                "Restate your previous response in your own voice. "
                "Be concise. Do not add new information."
            )),
        ]
        try:
            response = await self.inference_client._call_ollama(
                prompt="",
                model_name=self.inference_client.config.primary_model_name,
                system=persona_prompt,
                messages=messages,
                temperature=self._mode_manager.get_temperature(request.mode),
                max_tokens=1024,
            )
            return response.content
        except Exception as e:
            self.logger.warning(
                f"Local persona re-render failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id},
            )
            return raw_content

    async def handle(self, request: Request) -> Response:
        """
        Main entry point for processing a request.

        Args:
            request: The incoming request.

        Returns:
            Response object.
        """
        start_time = time.time()

        # Create task for state tracking
        task = self.state_machine.create_task(request)

        try:
            # Step 1: Validate request
            validation_result = self._validation_pipeline.validate_request(request)
            if not validation_result.valid:
                return self._create_error_response(
                    request,
                    "validation_error",
                    validation_result.message or "Invalid request",
                    start_time
                )

            # Step 2: Process mode switching
            original_content = request.content
            mode, cleaned_content = self._mode_manager.process_mode_switch(request.content)
            request.mode = mode
            request.content = cleaned_content

            # Step 2.5: Apply default agent from model tier (if no explicit @agent)
            explicit_agent = self._mode_manager.detect_mode_from_input(original_content)
            if explicit_agent is None:
                suggested = self.inference_client.router.get_suggested_agent(
                    prompt=cleaned_content,
                )
                if suggested:
                    try:
                        tier_mode = Mode(suggested.lower())
                        request.mode = tier_mode
                        mode = tier_mode
                    except ValueError:
                        pass  # Unknown agent name in config — ignore

            # Step 3: Move to processing
            self.state_machine.start_processing(task)

            # Step 4: Get conversation context (with TTL enforcement)
            conversation = await self._get_or_create_conversation_with_ttl(
                request.session_id
            )
            conversation.mode = mode

            # Periodic cleanup of expired sessions
            self._handle_count += 1
            if self._handle_count % self._CLEANUP_INTERVAL == 0:
                timeout = await self._get_session_timeout()
                evicted = self._cleanup_expired_sessions(timeout)
                if evicted > 0:
                    self.logger.info(
                        f"Periodic cleanup: evicted {evicted} expired session(s)",
                        component=LogComponent.ORCHESTRATION,
                    )

            # Step 4.5: Check response cache (skip for force_local/private messages)
            force_local = request.force_local
            if not force_local:
                cache = get_response_cache()
                cached = await cache.get(request.content, conversation)
                if cached:
                    self.logger.info(
                        "Serving cached response",
                        component=LogComponent.ORCHESTRATION,
                        data={"request_id": request.id, "cache_hits": cached.hits},
                    )
                    response = Response(
                        request_id=request.id,
                        content=cached.content,
                        response_type=ResponseType.TEXT,
                        mode=request.mode,
                        tokens_in=cached.tokens_in,
                        tokens_out=cached.tokens_out,
                        duration_ms=(time.time() - start_time) * 1000,
                    )
                    self.state_machine.complete(task, response)
                    return response

            # Step 5: Determine routing for privacy controls
            will_use_cloud = self._will_route_to_cloud(request.content, force_local)

            # Step 5.5: Retrieve relevant memory (cloud-safe filtering when routing to cloud)
            memory = await self._get_memory_manager()
            memory_context = await memory.build_context(
                query=request.content,
                max_tokens=4000,
                include_recent=True,
                cloud_safe=will_use_cloud,
            )

            # Step 6: Build prompt with tool behavior guidance
            # Tool schemas are passed via native API (tools parameter), not in the prompt.
            # TOOL_INSTRUCTIONS constant provides the LLM with routing guidance.
            tool_instructions = TOOL_INSTRUCTIONS

            # Step 6.3: Load user profile context (markdown-based identity)
            user_profile_context = ""
            command_system_instructions = ""
            try:
                from hestia.user.config_loader import get_user_config_loader
                from hestia.user.config_models import TOPIC_KEYWORDS, UserConfigFile
                user_loader = await get_user_config_loader()
                user_config = await user_loader.load()

                # Get base context (always-load files)
                if will_use_cloud:
                    user_profile_context = user_config.get_cloud_safe_context()
                else:
                    user_profile_context = user_config.context_block

                # Keyword-based topic detection for selective loading
                msg_lower = request.content.lower()
                topic_files = []
                for config_file, keywords in TOPIC_KEYWORDS.items():
                    if any(kw in msg_lower for kw in keywords):
                        topic_files.append(config_file)
                if topic_files:
                    topic_context = user_config.get_topic_context(topic_files)
                    if topic_context:
                        user_profile_context = f"{user_profile_context}\n\n{topic_context}" if user_profile_context else topic_context

                # Command expansion: detect /command syntax
                if request.content.strip().startswith("/"):
                    parts = request.content.strip().split(None, 1)
                    cmd_name = parts[0].lstrip("/")
                    cmd_args = parts[1] if len(parts) > 1 else ""
                    cmd = await user_loader.get_command(cmd_name)
                    if cmd:
                        command_system_instructions = cmd.system_instructions
                        if cmd_args:
                            request.content = cmd.expand(cmd_args)
                        self.logger.info(
                            f"Expanded command: /{cmd_name}",
                            component=LogComponent.ORCHESTRATION,
                            data={"request_id": request.id, "command": cmd_name},
                        )
            except Exception as e:
                self.logger.warning(
                    f"Failed to load user profile: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )

            # Combine tool + command instructions
            combined_instructions = tool_instructions
            if command_system_instructions:
                combined_instructions = f"{tool_instructions}\n\n## Command Mode\n\n{command_system_instructions}"

            messages, prompt_components = self._prompt_builder.build(
                request=request,
                memory_context=memory_context,
                conversation=conversation,
                additional_system_instructions=combined_instructions,
                cloud_safe=will_use_cloud,
                user_profile_context=user_profile_context,
            )

            # Check token budget
            budget_status = self._prompt_builder.check_budget(prompt_components)
            if budget_status["exceeded"]:
                self.logger.warning(
                    f"Token budget exceeded: {budget_status['total_tokens']}/{budget_status['budget']}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id}
                )

            # Step 6.5: Council pre-inference (intent classification)
            intent = None
            try:
                council = self._get_council_manager()
                intent = await council.classify_intent(request.content)
                task.context["intent"] = {
                    "type": intent.primary_intent.value,
                    "confidence": intent.confidence,
                }
            except Exception as e:
                self.logger.warning(
                    f"Council intent classification failed: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )

            # Step 7: Run inference with retry
            response = await self._run_inference_with_retry(
                task=task,
                request=request,
                messages=messages,
                prompt_components=prompt_components,
                intent=intent,
                will_use_cloud=will_use_cloud,
            )

            # Step 8: Store conversation in memory
            await self._store_conversation(request, response, memory)

            # Step 9: Update conversation history
            conversation.add_turn(request.content, response.content)

            # Step 9.5: Cache successful text responses (skip force_local)
            if (
                response.response_type == ResponseType.TEXT
                and not force_local
            ):
                cache = get_response_cache()
                await cache.put(
                    request.content, conversation, response.content,
                    response.tokens_in or 0, response.tokens_out or 0,
                )

            # Step 10: Complete task
            response.duration_ms = (time.time() - start_time) * 1000
            self.state_machine.complete(task, response)

            return response

        except TaskTimeoutError as e:
            self.state_machine.fail(task, e)
            return self._create_error_response(
                request,
                "timeout",
                "Request timed out. Please try again.",
                start_time
            )

        except Exception as e:
            self.state_machine.fail(task, e)
            self.logger.error(
                f"Request handling failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id, "error_type": type(e).__name__}
            )
            return self._create_error_response(
                request,
                "internal_error",
                "An error occurred processing your request.",
                start_time
            )

    async def handle_streaming(
        self,
        request: Request,
        tool_approval_callback: Optional[Callable] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream a request through the pipeline, yielding WebSocket protocol events.

        Parallel to handle() — reuses the same internal methods but yields events
        instead of returning a complete Response. The existing handle() is untouched.

        Args:
            request: The incoming request.
            tool_approval_callback: Optional async callable that takes (call_id, tool_name, arguments, tier)
                and returns True/False for approval. If None, all tools auto-execute.

        Yields:
            dict: WebSocket protocol events with "type" key.
        """
        start_time = time.time()
        task = self.state_machine.create_task(request)

        try:
            # Step 1: Validate request
            yield {"type": "status", "stage": "validating", "detail": "Validating request"}
            validation_result = self._validation_pipeline.validate_request(request)
            if not validation_result.valid:
                yield {
                    "type": "error",
                    "code": "validation_error",
                    "message": validation_result.message or "Invalid request",
                }
                return

            # Step 2: Process mode switching
            original_content = request.content
            mode, cleaned_content = self._mode_manager.process_mode_switch(request.content)
            request.mode = mode
            request.content = cleaned_content

            # Step 2.5: Apply default agent from model tier (if no explicit @agent)
            explicit_agent = self._mode_manager.detect_mode_from_input(original_content)
            if explicit_agent is None:
                suggested = self.inference_client.router.get_suggested_agent(
                    prompt=cleaned_content,
                )
                if suggested:
                    try:
                        tier_mode = Mode(suggested.lower())
                        request.mode = tier_mode
                        mode = tier_mode
                    except ValueError:
                        pass

            # Step 3: State tracking
            self.state_machine.start_processing(task)

            # Step 3.5: Load trust tiers for tool approval decisions
            trust_tiers = None
            try:
                from hestia.user import get_user_manager
                from hestia.user.models import ToolTrustTiers
                user_mgr = await get_user_manager()
                user_settings = await user_mgr.get_settings()
                trust_tiers = user_settings.get_tool_trust_tiers()
            except Exception as e:
                self.logger.warning(
                    f"Could not load trust tiers: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )

            # Step 4: Session/conversation with TTL
            conversation = await self._get_or_create_conversation_with_ttl(
                request.session_id
            )
            conversation.mode = mode

            # Periodic cleanup
            self._handle_count += 1
            if self._handle_count % self._CLEANUP_INTERVAL == 0:
                timeout = await self._get_session_timeout()
                self._cleanup_expired_sessions(timeout)

            # Step 4.5: Response cache check
            force_local = request.force_local
            if not force_local:
                cache = get_response_cache()
                cached = await cache.get(request.content, conversation)
                if cached:
                    # Stream cached response as tokens
                    yield {"type": "status", "stage": "cache_hit", "detail": "Serving cached response"}
                    # Yield cached content in chunks for streaming feel
                    chunk_size = 50
                    for i in range(0, len(cached.content), chunk_size):
                        yield {"type": "token", "content": cached.content[i:i + chunk_size], "request_id": request.id}
                    self.state_machine.complete(task, Response(
                        request_id=request.id, content=cached.content,
                        response_type=ResponseType.TEXT, mode=request.mode,
                        tokens_in=cached.tokens_in, tokens_out=cached.tokens_out,
                        duration_ms=(time.time() - start_time) * 1000,
                    ))
                    yield {
                        "type": "done", "request_id": request.id,
                        "metrics": {"tokens_in": cached.tokens_in, "tokens_out": cached.tokens_out,
                                    "duration_ms": (time.time() - start_time) * 1000, "cached": True},
                        "mode": request.mode.value,
                    }
                    return

            # Step 5: Privacy routing
            will_use_cloud = self._will_route_to_cloud(request.content, force_local)

            # Step 5.5: Memory retrieval
            yield {"type": "status", "stage": "memory", "detail": "Retrieving memory context"}
            memory = await self._get_memory_manager()
            memory_context = await memory.build_context(
                query=request.content,
                max_tokens=4000,
                include_recent=True,
                cloud_safe=will_use_cloud,
            )

            # Step 6: Build prompt (same as handle())
            yield {"type": "status", "stage": "building_prompt", "detail": "Building prompt"}
            tool_instructions = TOOL_INSTRUCTIONS
            # Load user profile context
            user_profile_context = ""
            command_system_instructions = ""
            try:
                from hestia.user.config_loader import get_user_config_loader
                from hestia.user.config_models import TOPIC_KEYWORDS, UserConfigFile
                user_loader = await get_user_config_loader()
                user_config = await user_loader.load()

                if will_use_cloud:
                    user_profile_context = user_config.get_cloud_safe_context()
                else:
                    user_profile_context = user_config.context_block

                # Keyword-based topic detection
                msg_lower = request.content.lower()
                topic_files = []
                for config_file, keywords in TOPIC_KEYWORDS.items():
                    if any(kw in msg_lower for kw in keywords):
                        topic_files.append(config_file)
                if topic_files:
                    topic_context = user_config.get_topic_context(topic_files)
                    if topic_context:
                        user_profile_context = f"{user_profile_context}\n\n{topic_context}" if user_profile_context else topic_context

                # Command expansion
                if request.content.strip().startswith("/"):
                    parts = request.content.strip().split(None, 1)
                    cmd_name = parts[0].lstrip("/")
                    cmd_args = parts[1] if len(parts) > 1 else ""
                    cmd = await user_loader.get_command(cmd_name)
                    if cmd:
                        command_system_instructions = cmd.system_instructions
                        if cmd_args:
                            request.content = cmd.expand(cmd_args)
            except Exception as e:
                self.logger.warning(
                    f"Failed to load user profile for streaming: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )

            combined_instructions = tool_instructions
            if command_system_instructions:
                combined_instructions = f"{tool_instructions}\n\n## Command Mode\n\n{command_system_instructions}"

            # Inject CLI development context when available
            if request.source == RequestSource.CLI and request.context_hints:
                cli_context_parts = []
                cwd = request.context_hints.get("cwd")
                if cwd:
                    cli_context_parts.append(f"Working directory: {cwd}")
                git_branch = request.context_hints.get("git_branch")
                if git_branch:
                    cli_context_parts.append(f"Git branch: {git_branch}")
                git_status = request.context_hints.get("git_status_summary")
                if git_status:
                    cli_context_parts.append(f"Git status:\n{git_status}")

                # Project file contents for ambient knowledge
                project_files = request.context_hints.get("project_files", {})
                if project_files:
                    for filename, content in project_files.items():
                        cli_context_parts.append(f"### {filename}\n{content}")

                if cli_context_parts:
                    dev_context = "\n\n## Development Context\n\n" + "\n\n".join(cli_context_parts)
                    dev_context += (
                        "\n\nThe user is a developer working in this project via the CLI. "
                        "The project files above (SPRINT.md, CLAUDE.md, etc.) describe the project's current status, roadmap, architecture, and conventions. "
                        "When the user asks about the project, its roadmap, status, or architecture, answer from this context first. "
                        "You still have ALL your tools (Notes, Calendar, Reminders, Mail, Health, Files, Shell) — "
                        "the CLI is just another interface to your full capabilities."
                    )
                    combined_instructions = f"{combined_instructions}\n{dev_context}"

            messages, prompt_components = self._prompt_builder.build(
                request=request,
                memory_context=memory_context,
                conversation=conversation,
                additional_system_instructions=combined_instructions,
                cloud_safe=will_use_cloud,
                user_profile_context=user_profile_context,
            )

            # Token budget check
            budget_status = self._prompt_builder.check_budget(prompt_components)
            if budget_status["exceeded"]:
                self.logger.warning(
                    f"Token budget exceeded: {budget_status['total_tokens']}/{budget_status['budget']}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id}
                )

            # Step 6.5: Council intent classification
            yield {"type": "status", "stage": "council", "detail": "Classifying intent"}
            intent = None
            try:
                council = self._get_council_manager()
                intent = await council.classify_intent(request.content)
                task.context["intent"] = {
                    "type": intent.primary_intent.value,
                    "confidence": intent.confidence,
                }
            except Exception as e:
                self.logger.warning(
                    f"Council intent classification failed: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )

            # Step 7: Streaming inference
            yield {"type": "status", "stage": "inference", "detail": "Generating response"}

            temperature = self._mode_manager.get_temperature(request.mode)
            max_tokens = self._prompt_builder.estimate_response_budget(prompt_components)
            registry = get_tool_registry()
            tool_definitions = registry.get_definitions_as_list()

            # Stream tokens from inference
            content_buffer = ""
            inference_response = None

            async for item in self.inference_client.chat_stream(
                messages=messages,
                system=None,  # System prompt already in messages from prompt_builder
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tool_definitions if tool_definitions else None,
            ):
                if isinstance(item, str):
                    content_buffer += item
                    yield {"type": "token", "content": item, "request_id": request.id}
                elif isinstance(item, InferenceResponse):
                    inference_response = item

            # Fallback if no InferenceResponse received (shouldn't happen but defensive)
            if inference_response is None:
                inference_response = InferenceResponse(
                    content=content_buffer, model="unknown",
                    tokens_in=0, tokens_out=0, duration_ms=0,
                )

            content = inference_response.content

            # Step 7.25: Local persona re-render for cloud responses (non-CHAT only)
            if (
                will_use_cloud
                and intent
                and intent.primary_intent != IntentType.CHAT
                and not self._looks_like_tool_call(content)
                and not inference_response.tool_calls
            ):
                content = await self._apply_local_persona(content, request)

            # Step 7.5: Council post-inference
            council_result = None
            try:
                council = self._get_council_manager()
                council_result = await council.run_council(
                    user_message=request.content,
                    inference_response=content,
                    mode=request.mode.value,
                    intent=intent,
                )
            except Exception:
                pass

            # Step 7.75: Tool execution (3-tier priority — same as handle())
            tool_result = None

            # Priority 1: Native tool calls from Ollama API
            if inference_response.tool_calls:
                yield {"type": "status", "stage": "tools", "detail": "Executing tool calls"}
                tool_result = await self._execute_streaming_tool_calls(
                    inference_response.tool_calls, request, task,
                    tool_approval_callback, trust_tiers,
                )
            # Priority 2: Council Analyzer tool extraction
            elif (
                council_result
                and council_result.tool_extraction
                and council_result.tool_extraction.tool_calls
                and council_result.tool_extraction.confidence > 0.7
            ):
                yield {"type": "status", "stage": "tools", "detail": "Executing tool calls"}
                tool_result = await self._execute_council_tools(
                    council_result.tool_extraction.tool_calls, request, task
                )
            else:
                # Priority 3: Text regex fallback
                tool_result = await self._try_execute_tool_from_response(content, request, task)

            if tool_result is not None:
                # Yield the tool result
                yield {"type": "tool_result", "call_id": "aggregate", "status": "success", "output": tool_result}

                # Synthesize response with personality (non-streaming for v1)
                synthesized = None
                try:
                    if council_result and not council_result.fallback_used:
                        council = self._get_council_manager()
                        synthesized = await council.synthesize_response(
                            user_message=request.content,
                            tool_result=tool_result,
                            mode=request.mode.value,
                        )
                except Exception:
                    pass

                if not synthesized:
                    synthesized = await self._format_tool_result_with_personality(
                        tool_result, request, messages, temperature, max_tokens
                    )

                # Stream the synthesized response as tokens
                chunk_size = 50
                for i in range(0, len(synthesized), chunk_size):
                    yield {"type": "token", "content": synthesized[i:i + chunk_size], "request_id": request.id}

                final_content = synthesized
            else:
                # Handle raw tool call JSON (don't show to user)
                if inference_response.tool_calls or self._looks_like_tool_call(content):
                    fallback_msg = "I tried to help with that, but encountered an issue executing the action. Let me try a different approach - could you rephrase your request?"
                    yield {"type": "token", "content": fallback_msg, "request_id": request.id}
                    final_content = fallback_msg
                else:
                    final_content = content

            # Step 8: Store conversation in memory
            response = Response(
                request_id=request.id,
                content=final_content,
                response_type=ResponseType.TEXT,
                mode=request.mode,
                tokens_in=inference_response.tokens_in,
                tokens_out=inference_response.tokens_out,
                duration_ms=(time.time() - start_time) * 1000,
            )
            await self._store_conversation(request, response, memory)

            # Step 9: Update conversation history
            conversation.add_turn(request.content, final_content)

            # Step 9.5: Cache
            if response.response_type == ResponseType.TEXT and not force_local:
                cache = get_response_cache()
                await cache.put(
                    request.content, conversation, final_content,
                    inference_response.tokens_in or 0, inference_response.tokens_out or 0,
                )

            # Step 10: Complete
            self.state_machine.complete(task, response)

            yield {
                "type": "done",
                "request_id": request.id,
                "metrics": {
                    "tokens_in": inference_response.tokens_in,
                    "tokens_out": inference_response.tokens_out,
                    "duration_ms": response.duration_ms,
                    "model": inference_response.model,
                },
                "mode": request.mode.value,
            }

        except TaskTimeoutError as e:
            self.state_machine.fail(task, e)
            yield {"type": "error", "code": "timeout", "message": "Request timed out. Please try again."}

        except Exception as e:
            self.state_machine.fail(task, e)
            self.logger.error(
                f"Streaming request failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id, "error_type": type(e).__name__}
            )
            yield {"type": "error", "code": "internal_error", "message": "An error occurred processing your request."}

    async def _execute_streaming_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        request: Request,
        task: Task,
        tool_approval_callback: Optional[Callable] = None,
        trust_tiers: Optional["ToolTrustTiers"] = None,
    ) -> Optional[str]:
        """
        Execute native tool calls with optional approval callback for streaming.

        Uses trust_tiers to auto-approve tools in trusted categories.
        Falls back to tool_approval_callback for tools needing explicit approval.

        Similar to _execute_native_tool_calls but yields approval requests
        when a callback is provided.
        """
        import json

        executor = await self._get_tool_executor()
        registry = get_tool_registry()
        results = []

        for tc in tool_calls:
            try:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                arguments = func.get("arguments", {})

                if not tool_name:
                    continue

                # Parse string arguments
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except (json.JSONDecodeError, TypeError):
                        arguments = {}

                # Validate tool exists
                if not registry.has_tool(tool_name):
                    self.logger.warning(
                        f"Streaming: unknown tool: {tool_name}",
                        component=LogComponent.ORCHESTRATION,
                        data={"request_id": request.id},
                    )
                    continue

                tool = registry.get(tool_name)

                # Trust tier check: auto-approve if tier allows it
                if tool and tool.requires_approval:
                    auto_approved = False
                    if trust_tiers:
                        auto_approved = trust_tiers.should_auto_approve(
                            tool.category, tool.requires_approval
                        )

                    if auto_approved:
                        self.logger.info(
                            f"Streaming: auto-approved tool via trust tier: {tool_name}",
                            component=LogComponent.ORCHESTRATION,
                            data={"request_id": request.id, "category": tool.category},
                        )
                    elif tool_approval_callback:
                        call_id = f"tc-{request.id[:8]}-{tool_name}"
                        tier_name = trust_tiers.get_tier_for_tool(
                            tool.category, tool.requires_approval
                        ) if trust_tiers else "unknown"
                        approved = await tool_approval_callback(
                            call_id, tool_name, arguments, tier_name
                        )
                        if not approved:
                            results.append(f"Tool {tool_name} was denied by user.")
                            continue

                self.logger.info(
                    f"Streaming: executing tool: {tool_name}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id, "tool_name": tool_name, "arguments": arguments},
                )

                self.state_machine.await_tool(task, tool_name)
                call = ToolCall.create(tool_name=tool_name, arguments=arguments)
                result = await executor.execute(call, request.id)
                self.state_machine.resume_processing(task)

                if result.success:
                    result_data = result.output
                    if isinstance(result_data, dict):
                        results.append(json.dumps(result_data, indent=2))
                    else:
                        results.append(str(result_data))
                else:
                    error_msg = result.error or "Unknown error"
                    results.append(f"Tool {tool_name} failed: {error_msg}")

            except Exception as e:
                self.logger.warning(
                    f"Error in streaming tool call: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )
                try:
                    self.state_machine.resume_processing(task)
                except Exception:
                    pass

        if results:
            return "\n\n".join(results)
        return None

    async def _run_inference_with_retry(
        self,
        task: Task,
        request: Request,
        messages: list,
        prompt_components,
        max_retries: int = 3,
        intent: Optional[IntentClassification] = None,
        will_use_cloud: bool = False,
    ) -> Response:
        """
        Run inference with validation and retry logic.

        Args:
            task: Current task.
            request: Original request.
            messages: Prompt messages.
            prompt_components: Prompt component details.
            max_retries: Maximum retry attempts.
            intent: Optional intent classification from council.
            will_use_cloud: Whether this request routes to cloud (for persona re-render).

        Returns:
            Validated response.
        """
        temperature = self._mode_manager.get_temperature(request.mode)
        max_tokens = self._prompt_builder.estimate_response_budget(prompt_components)

        # Get native tool definitions once (stable across retries)
        registry = get_tool_registry()
        tool_definitions = registry.get_definitions_as_list()

        for attempt in range(max_retries):
            # Add retry guidance if not first attempt
            current_messages = messages.copy()
            if attempt > 0:
                guidance = self._validation_pipeline.create_retry_guidance(
                    validation_result,
                    attempt
                )
                if guidance:
                    current_messages.append({
                        "role": "user",
                        "content": guidance
                    })

            # Run inference with native tool calling
            inference_response = await self.state_machine.run_with_timeout(
                task,
                self.inference_client.chat,
                messages=current_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tool_definitions if tool_definitions else None,
            )

            # Check if response contains a tool call
            content = inference_response.content

            # Step 7.25: Local persona re-render for cloud responses (non-CHAT only)
            if (
                will_use_cloud
                and intent
                and intent.primary_intent != IntentType.CHAT
                and not self._looks_like_tool_call(content)
                and not inference_response.tool_calls
            ):
                content = await self._apply_local_persona(content, request)
                inference_response = type(inference_response)(
                    content=content,
                    model=inference_response.model,
                    tokens_in=inference_response.tokens_in,
                    tokens_out=inference_response.tokens_out,
                    duration_ms=inference_response.duration_ms,
                    finish_reason=inference_response.finish_reason,
                    raw_response=inference_response.raw_response,
                    tier=inference_response.tier,
                    fallback_used=inference_response.fallback_used,
                    tool_calls=inference_response.tool_calls,
                )

            # Step 7.5: Council post-inference (Analyzer + Validator)
            council_result = None
            try:
                council = self._get_council_manager()
                council_result = await council.run_council(
                    user_message=request.content,
                    inference_response=content,
                    mode=request.mode.value,
                    intent=intent,
                )
                task.context["council"] = {
                    "roles_executed": council_result.roles_executed,
                    "roles_failed": council_result.roles_failed,
                    "fallback_used": council_result.fallback_used,
                }
            except Exception as e:
                self.logger.warning(
                    f"Council post-inference failed: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id},
                )

            # Priority 1: Native tool calls from Ollama API (structured, reliable)
            if inference_response.tool_calls:
                tool_result = await self._execute_native_tool_calls(
                    inference_response.tool_calls, request, task
                )
            # Priority 2: Council Analyzer tool extraction
            elif (
                council_result
                and council_result.tool_extraction
                and council_result.tool_extraction.tool_calls
                and council_result.tool_extraction.confidence > 0.7
            ):
                tool_result = await self._execute_council_tools(
                    council_result.tool_extraction.tool_calls, request, task
                )
            else:
                # Priority 3: Fallback to text regex-based tool parsing
                tool_result = await self._try_execute_tool_from_response(content, request, task)

            if tool_result is not None:
                # Try council Responder first, fall back to existing personality formatter
                synthesized = None
                try:
                    if council_result and not council_result.fallback_used:
                        council = self._get_council_manager()
                        synthesized = await council.synthesize_response(
                            user_message=request.content,
                            tool_result=tool_result,
                            mode=request.mode.value,
                        )
                except Exception:
                    pass

                if synthesized:
                    final_content = synthesized
                else:
                    final_content = await self._format_tool_result_with_personality(
                        tool_result, request, current_messages, temperature, max_tokens
                    )
                response_type = ResponseType.TEXT
            else:
                # Check if native tool calls were attempted but all failed
                if inference_response.tool_calls:
                    final_content = "I tried to help with that, but encountered an issue executing the action. Let me try a different approach - could you rephrase your request?"
                    response_type = ResponseType.TEXT
                # Check if content looks like a raw tool_call JSON that failed to execute
                # Never show raw tool JSON to user
                elif self._looks_like_tool_call(content):
                    final_content = "I tried to help with that, but encountered an issue executing the action. Let me try a different approach - could you rephrase your request?"
                    response_type = ResponseType.TEXT
                else:
                    # No tool call detected - use original response
                    final_content = content
                    response_type = ResponseType.TEXT

            # Create response object
            response = Response(
                request_id=request.id,
                content=final_content,
                response_type=response_type,
                mode=request.mode,
                tokens_in=inference_response.tokens_in,
                tokens_out=inference_response.tokens_out,
            )

            # Validate response
            validation_result = self._validation_pipeline.validate_response(response)

            if validation_result.valid:
                return response

            # Check if we should retry
            if not self._validation_pipeline.should_retry(validation_result, attempt + 1):
                break

            self.logger.info(
                f"Retrying inference (attempt {attempt + 2})",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id}
            )

        # Return last response even if validation failed
        return response

    async def _store_conversation(
        self,
        request: Request,
        response: Response,
        memory: MemoryManager,
    ) -> None:
        """Store the conversation turn in memory."""
        try:
            await memory.store_exchange(
                user_message=request.content,
                assistant_response=response.content,
                mode=request.mode.value,
            )
        except Exception as e:
            # Don't fail the request if memory storage fails
            self.logger.warning(
                f"Failed to store conversation in memory: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id}
            )

    async def _try_execute_tool_from_response(
        self,
        content: str,
        request: Request,
        task: Task,
    ) -> Optional[str]:
        """
        Try to parse and execute a tool call from LLM response.

        Returns the formatted result if a tool was called, or None if no tool call detected.
        """
        import json
        import re

        # Try to find JSON tool call in response
        # Look for {"tool_call": ...} pattern
        try:
            # Try direct JSON parse first
            try:
                data = json.loads(content.strip())
                if "tool_call" in data:
                    tool_call = data["tool_call"]
                    tool_name = tool_call.get("name", "")
                    arguments = tool_call.get("arguments", {})
                elif "tool" in data:
                    # Alternative format
                    tool_name = data.get("tool", "")
                    arguments = data.get("arguments", {})
                else:
                    return None
            except json.JSONDecodeError:
                # Try to extract JSON from mixed content
                # Look for {"tool_call": {...}} pattern with nested braces
                json_match = re.search(r'\{"tool_call":\s*\{[^}]*\}\}', content)
                if not json_match:
                    # Try alternate pattern with "name" inside
                    json_match = re.search(r'\{"tool_call":\s*\{"name":\s*"[^"]+",\s*"arguments":\s*\{[^}]*\}\}\}', content)
                if not json_match:
                    # Try simpler tool format
                    json_match = re.search(r'\{"tool":\s*"[^"]+",\s*"arguments":\s*\{[^}]*\}\}', content)
                if not json_match:
                    # Last resort: find any JSON object with tool_call or tool key
                    for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content):
                        try:
                            potential = json.loads(match.group())
                            if "tool_call" in potential or "tool" in potential:
                                json_match = match
                                break
                        except json.JSONDecodeError:
                            continue
                if not json_match:
                    return None

                data = json.loads(json_match.group())
                if "tool_call" in data:
                    tool_call = data["tool_call"]
                    tool_name = tool_call.get("name", "")
                    arguments = tool_call.get("arguments", {})
                else:
                    tool_name = data.get("tool", "")
                    arguments = data.get("arguments", {})

            if not tool_name:
                return None

            self.logger.info(
                f"Detected tool call: {tool_name}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id, "tool_name": tool_name, "arguments": arguments}
            )

            # Execute the tool
            executor = await self._get_tool_executor()
            call = ToolCall.create(tool_name=tool_name, arguments=arguments)
            result = await executor.execute(call, request.id)

            if result.success:
                # Format the result for the user
                result_data = result.output
                if isinstance(result_data, dict):
                    # Format nicely based on tool type
                    if "events" in result_data:
                        events = result_data.get("events", [])
                        if not events:
                            return "No events found for the requested time period."
                        lines = [f"Found {len(events)} event(s):"]
                        for e in events[:10]:  # Limit to 10
                            title = e.get("title", "Untitled")
                            start = e.get("start", "")
                            if start:
                                start = start.split("T")[0] if "T" in start else start
                            lines.append(f"• {title} ({start})")
                        return "\n".join(lines)
                    elif "reminders" in result_data:
                        reminders = result_data.get("reminders", [])
                        if not reminders:
                            return "No reminders found."
                        lines = [f"Found {len(reminders)} reminder(s):"]
                        for r in reminders[:10]:
                            title = r.get("title", "Untitled")
                            due = r.get("due", "")
                            if due:
                                due = f" (due: {due.split('T')[0]})" if "T" in due else f" (due: {due})"
                            lines.append(f"• {title}{due}")
                        return "\n".join(lines)
                    elif "emails" in result_data:
                        emails = result_data.get("emails", [])
                        if not emails:
                            return "No emails found."
                        lines = [f"Found {len(emails)} email(s):"]
                        for e in emails[:5]:
                            subject = e.get("subject", "No subject")
                            sender = e.get("sender", "Unknown")
                            lines.append(f"• {subject} (from: {sender})")
                        return "\n".join(lines)
                    elif "notes" in result_data:
                        notes = result_data.get("notes", [])
                        if not notes:
                            return "No notes found."
                        lines = [f"Found {len(notes)} note(s):"]
                        for n in notes[:10]:
                            title = n.get("title", "Untitled")
                            lines.append(f"• {title}")
                        return "\n".join(lines)
                    else:
                        return json.dumps(result_data, indent=2)
                else:
                    return str(result_data)
            else:
                # Tool execution failed
                error_msg = result.error or "Unknown error"
                self.logger.warning(
                    f"Tool execution failed: {error_msg}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id, "tool_name": tool_name}
                )
                return f"I tried to check your {tool_name.replace('_', ' ')}, but encountered an error: {error_msg}"

        except Exception as e:
            self.logger.warning(
                f"Error parsing/executing tool call: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id, "content_preview": content[:200]}
            )
            return None

    async def _execute_native_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        request: Request,
        task: Task,
    ) -> Optional[str]:
        """
        Execute tool calls returned natively by Ollama API.

        Ollama returns tool_calls as: [{"function": {"name": "...", "arguments": {...}}}]

        Returns the formatted result if successful, or None on failure.
        """
        import json

        executor = await self._get_tool_executor()
        registry = get_tool_registry()
        results = []

        for tc in tool_calls:
            try:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                arguments = func.get("arguments", {})

                if not tool_name:
                    self.logger.warning(
                        "Native tool call missing tool name, skipping",
                        component=LogComponent.ORCHESTRATION,
                        data={"request_id": request.id, "raw_entry": str(tc)[:200]},
                    )
                    continue

                # Ollama may return arguments as JSON string instead of dict
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except (json.JSONDecodeError, TypeError):
                        self.logger.warning(
                            f"Could not parse arguments string for {tool_name}",
                            component=LogComponent.ORCHESTRATION,
                            data={"request_id": request.id, "raw_args": arguments[:200]},
                        )
                        arguments = {}

                # Validate tool exists in registry
                if not registry.has_tool(tool_name):
                    self.logger.warning(
                        f"Native tool call references unknown tool: {tool_name}",
                        component=LogComponent.ORCHESTRATION,
                        data={"request_id": request.id},
                    )
                    continue

                self.logger.info(
                    f"Executing native tool call: {tool_name}",
                    component=LogComponent.ORCHESTRATION,
                    data={
                        "request_id": request.id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                    },
                )

                # State machine: transition to AWAITING_TOOL
                self.state_machine.await_tool(task, tool_name)

                call = ToolCall.create(tool_name=tool_name, arguments=arguments)
                result = await executor.execute(call, request.id)

                # State machine: resume processing after tool execution
                self.state_machine.resume_processing(task)

                if result.success:
                    result_data = result.output
                    if isinstance(result_data, dict):
                        results.append(json.dumps(result_data, indent=2))
                    else:
                        results.append(str(result_data))
                else:
                    error_msg = result.error or "Unknown error"
                    self.logger.warning(
                        f"Native tool execution failed: {error_msg}",
                        component=LogComponent.ORCHESTRATION,
                        data={"request_id": request.id, "tool_name": tool_name},
                    )
                    results.append(
                        f"Tool {tool_name} failed: {error_msg}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Error executing native tool call: {type(e).__name__}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id, "tool_name": tc.get("function", {}).get("name", "unknown")},
                )
                # Ensure state machine returns to processing on error
                try:
                    self.state_machine.resume_processing(task)
                except Exception:
                    pass

        if results:
            return "\n\n".join(results)
        return None

    async def _execute_council_tools(
        self,
        tool_calls: List[dict],
        request: Request,
        task: Task,
    ) -> Optional[str]:
        """
        Execute pre-parsed tool calls from council Analyzer.

        Returns formatted result string, or None if execution fails.
        """
        import json

        try:
            executor = await self._get_tool_executor()
            registry = get_tool_registry()
            results = []

            for tc in tool_calls:
                tool_name = tc.get("name", "")
                arguments = tc.get("arguments", {})

                # Validate tool exists in registry
                if not registry.has_tool(tool_name):
                    self.logger.warning(
                        f"Council Analyzer suggested unknown tool: {tool_name}",
                        component=LogComponent.ORCHESTRATION,
                        data={"request_id": request.id},
                    )
                    continue

                self.logger.info(
                    f"Executing council-extracted tool: {tool_name}",
                    component=LogComponent.ORCHESTRATION,
                    data={"request_id": request.id, "tool_name": tool_name},
                )

                call = ToolCall.create(tool_name=tool_name, arguments=arguments)
                result = await executor.execute(call, request.id)

                if result.success:
                    output = result.output
                    if isinstance(output, dict):
                        results.append(json.dumps(output, indent=2))
                    else:
                        results.append(str(output))
                else:
                    error_msg = result.error or "Unknown error"
                    results.append(f"Tool {tool_name} failed: {error_msg}")

            if results:
                return "\n\n".join(results)
            return None

        except Exception as e:
            self.logger.warning(
                f"Council tool execution failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": request.id},
            )
            return None

    def _looks_like_tool_call(self, content: str) -> bool:
        """
        Check if content looks like a raw tool_call JSON that shouldn't be shown to user.
        """
        import json

        # Quick substring check first (fast)
        if '"tool_call"' not in content and '"tool":' not in content:
            return False

        # Try to parse as JSON (pure JSON response)
        try:
            data = json.loads(content.strip())
            return "tool_call" in data or "tool" in data
        except json.JSONDecodeError:
            # Mixed content: text + embedded JSON (e.g. "I'll check...\n{"tool_call": ...}")
            # Substring match for the opening of a tool call JSON structure
            return '{"tool_call"' in content or '{"tool":' in content

    async def _format_tool_result_with_personality(
        self,
        tool_result: str,
        request: Request,
        original_messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Send tool results back through the LLM to get a personality-appropriate response.

        Instead of returning raw "Found 3 reminders..." text, this lets Hestia
        present the information in her characteristic voice.
        """
        # Build a follow-up message with the tool result
        # original_messages is List[Message], so we need to append Message objects
        follow_up_messages = original_messages.copy()
        follow_up_messages.append(Message(
            role="assistant",
            content=f"[I retrieved this information: {tool_result}]"
        ))
        follow_up_messages.append(Message(
            role="user",
            content="Now present this information to me naturally, in your own voice. Be concise but personable - don't just list the raw data."
        ))

        try:
            # Run inference to get personality-appropriate response
            formatted_response = await self.inference_client.chat(
                messages=follow_up_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return formatted_response.content
        except Exception as e:
            # Fall back to raw result if formatting fails
            self.logger.warning(
                f"Failed to format tool result with personality: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return tool_result

    async def _execute_tool_calls(
        self,
        tool_calls: List[dict],
        request: Request,
        task: Task,
    ) -> List[ToolResult]:
        """
        Execute a list of tool calls.

        Args:
            tool_calls: Tool call definitions from model response.
            request: Original request for context.
            task: Current task for state management.

        Returns:
            List of tool results.
        """
        executor = await self._get_tool_executor()
        results = []

        # Convert dict tool calls to ToolCall objects
        calls = []
        for tc in tool_calls:
            call = ToolCall.create(
                tool_name=tc.get("name", tc.get("tool_name", "")),
                arguments=tc.get("arguments", tc.get("input", {})),
            )
            calls.append(call)

        # Execute all tools
        for call in calls:
            self.logger.info(
                f"Executing tool: {call.tool_name}",
                component=LogComponent.ORCHESTRATION,
                data={
                    "request_id": request.id,
                    "tool_name": call.tool_name,
                    "call_id": call.id,
                }
            )

            # Transition to AWAITING_TOOL state
            self.state_machine.await_tool(task, call.tool_name)

            # Execute the tool
            result = await executor.execute(call, request.id)
            results.append(result)

            self.logger.info(
                f"Tool execution completed: {call.tool_name} ({result.status.value})",
                component=LogComponent.ORCHESTRATION,
                data={
                    "request_id": request.id,
                    "tool_name": call.tool_name,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                }
            )

            # Resume processing after tool execution
            self.state_machine.resume_processing(task)

        return results

    def get_tool_definitions(self) -> str:
        """
        Get tool definitions for prompt injection.

        Returns:
            JSON string of available tools.
        """
        registry = get_tool_registry()
        return registry.get_definitions_for_prompt()

    def _create_error_response(
        self,
        request: Request,
        error_code: str,
        error_message: str,
        start_time: float,
    ) -> Response:
        """Create an error response."""
        return Response(
            request_id=request.id,
            content=error_message,
            response_type=ResponseType.ERROR,
            mode=request.mode,
            error_code=error_code,
            error_message=error_message,
            duration_ms=(time.time() - start_time) * 1000,
        )

    async def health_check(self) -> dict:
        """
        Check system health.

        Returns:
            Health status dictionary.
        """
        health = {
            "status": "healthy",
            "components": {},
        }

        # Check inference
        try:
            inference_healthy = await self.inference_client.health_check()
            health["components"]["inference"] = {
                "status": "healthy" if inference_healthy else "unhealthy",
            }
        except Exception as e:
            health["components"]["inference"] = {
                "status": "unhealthy",
                "error": type(e).__name__,
            }
            health["status"] = "degraded"

        # Check memory
        try:
            memory = await self._get_memory_manager()
            health["components"]["memory"] = {
                "status": "healthy",
                "vector_count": memory.vector_store.count(),
            }
        except Exception as e:
            health["components"]["memory"] = {
                "status": "unhealthy",
                "error": type(e).__name__,
            }
            health["status"] = "degraded"

        # State machine stats
        health["components"]["state_machine"] = {
            "status": "healthy",
            "active_tasks": self.state_machine.active_task_count,
            "state_summary": self.state_machine.get_state_summary(),
        }

        # Check tool execution
        try:
            registry = get_tool_registry()
            health["components"]["tools"] = {
                "status": "healthy",
                "registered_tools": len(registry),
                "tool_names": registry.list_tool_names(),
            }
        except Exception as e:
            health["components"]["tools"] = {
                "status": "unhealthy",
                "error": type(e).__name__,
            }

        return health


# Module-level singleton
_request_handler: Optional[RequestHandler] = None


async def get_request_handler() -> RequestHandler:
    """Get or create the singleton request handler instance."""
    global _request_handler
    if _request_handler is None:
        _request_handler = RequestHandler()
    return _request_handler
