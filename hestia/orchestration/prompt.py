"""
Prompt builder for Hestia.

Constructs prompts with system instructions, memory context,
conversation history, and workspace context while respecting
token budgets.

Supports two prompt sources:
- Legacy mode system (hardcoded PERSONAS in mode.py) — used by v1 API
- .md config system (ANIMA.md + AGENT.md + USER.md) — used by v2 API
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from hestia.inference import get_inference_client, Message
from hestia.orchestration.models import Request, Mode, Conversation
from hestia.orchestration.mode import ModeManager, get_mode_manager


@dataclass
class PromptComponents:
    """Components used to build a prompt."""
    system_prompt: str
    memory_context: str = ""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    user_message: str = ""

    # Token counts (populated after building)
    system_tokens: int = 0
    memory_tokens: int = 0
    history_tokens: int = 0
    user_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total estimated tokens."""
        return (
            self.system_tokens +
            self.memory_tokens +
            self.history_tokens +
            self.user_tokens
        )


class PromptBuilder:
    """
    Builds prompts for inference with proper token management.

    Handles:
    - System prompt generation based on mode
    - Memory context injection
    - Conversation history management
    - Token budget enforcement (ADR-011: 32K context)
    - Cloud-safe prompt stripping (no personality sent to cloud providers)
    """

    # Token budget allocation (ADR-011)
    TOTAL_BUDGET = 32768
    SYSTEM_BUDGET = 2000      # Fixed system prompt
    TOOL_BUDGET = 1000        # Tool definitions
    USER_MODEL_BUDGET = 2000  # User model summary
    HISTORY_BUDGET = 20000    # Conversation history
    MEMORY_BUDGET = 4000      # RAG-retrieved memory
    USER_INPUT_BUDGET = 3000  # User's current message
    CONTEXT_BUDGET = 4000     # Workspace context (@ mentions, files, etc.)

    # Warning threshold
    WARNING_THRESHOLD = 0.9  # Warn at 90% usage

    def __init__(
        self,
        mode_manager: Optional[ModeManager] = None,
    ):
        """
        Initialize prompt builder.

        Args:
            mode_manager: Mode manager for persona prompts.
        """
        self.mode_manager = mode_manager or get_mode_manager()
        self._inference_client = None

    @property
    def inference_client(self):
        """Lazy-load inference client for token counting."""
        if self._inference_client is None:
            self._inference_client = get_inference_client()
        return self._inference_client

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return self.inference_client.token_counter.count(text)

    def _truncate_to_budget(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token budget.

        Uses word-level truncation with ellipsis.
        """
        tokens = self._count_tokens(text)
        if tokens <= max_tokens:
            return text

        # Estimate characters per token and truncate
        chars_per_token = len(text) / max(tokens, 1)
        target_chars = int(max_tokens * chars_per_token * 0.9)  # 90% buffer

        if target_chars < len(text):
            return text[:target_chars] + "..."

        return text

    def build_system_prompt(
        self,
        mode: Mode,
        additional_instructions: Optional[str] = None,
    ) -> str:
        """
        Build the system prompt for a mode.

        Args:
            mode: The active persona mode.
            additional_instructions: Optional extra instructions.

        Returns:
            Complete system prompt.
        """
        base_prompt = self.mode_manager.get_system_prompt(mode)

        parts = [base_prompt]

        if additional_instructions:
            parts.append(f"\nAdditional Instructions:\n{additional_instructions}")

        return "\n".join(parts)

    def build_system_prompt_from_config(
        self,
        agent_config: Any,
        additional_instructions: Optional[str] = None,
    ) -> str:
        """
        Build system prompt from an AgentConfig (.md-based system).

        Assembles the prompt from ANIMA.md (personality) + AGENT.md (rules)
        + USER.md (preferences) + TOOLS.md (environment) + MEMORY.md (long-term).

        This is the v2 replacement for build_system_prompt() which uses
        hardcoded PERSONAS. Falls back to legacy PERSONAS if agent_config
        is None or has no content.

        Args:
            agent_config: AgentConfig object with loaded .md content.
            additional_instructions: Optional extra instructions.

        Returns:
            Complete system prompt assembled from .md files.
        """
        if agent_config is None:
            # Fall back to legacy system
            return self.build_system_prompt(Mode.TIA, additional_instructions)

        # AgentConfig.system_prompt assembles from .md files
        base_prompt = agent_config.system_prompt

        parts = [base_prompt]

        if additional_instructions:
            parts.append(f"\n## Additional Instructions\n\n{additional_instructions}")

        return "\n".join(parts)

    def build_context_block(
        self,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Build workspace context block from chat context payload.

        Formats @ mentions, attached files, referenced items, and
        panel context into a structured block for the system prompt.

        Args:
            context: Chat context dict from v2 API (active_tab,
                     selected_text, attached_files, referenced_items,
                     panel_context).
            max_tokens: Maximum tokens for context block.

        Returns:
            Formatted context block, or empty string if no context.
        """
        max_tokens = max_tokens or self.CONTEXT_BUDGET

        if not context:
            return ""

        parts = ["## Workspace Context\n"]

        # Active tab
        active_tab = context.get("active_tab")
        if active_tab:
            parts.append(f"The user is currently viewing the **{active_tab}** tab.\n")

        # Selected text
        selected_text = context.get("selected_text")
        if selected_text:
            truncated = selected_text[:1000] + "..." if len(selected_text) > 1000 else selected_text
            parts.append(f"### Selected Text\n\n> {truncated}\n")

        # Attached files
        attached_files = context.get("attached_files", [])
        if attached_files:
            parts.append("### Referenced Files\n")
            for f in attached_files[:5]:  # Max 5 files
                path = f.get("path", "unknown")
                preview = f.get("content_preview", "")
                if preview:
                    # Smart truncation for file content
                    if len(preview) > 2000:
                        preview = preview[:2000] + "\n\n[...truncated, ask to see more]"
                    parts.append(f"**{path}:**\n```\n{preview}\n```\n")
                else:
                    parts.append(f"- {path}\n")

        # Referenced items (calendar events, notes, etc.)
        referenced_items = context.get("referenced_items", [])
        if referenced_items:
            parts.append("### Referenced Items\n")
            for item in referenced_items[:10]:  # Max 10 items
                item_type = item.get("type", "unknown")
                summary = item.get("summary") or item.get("title") or item.get("id", "")
                parts.append(f"- [{item_type}] {summary}\n")

        # Panel context (soft context from visible panels)
        panel_context = context.get("panel_context", {})
        if panel_context:
            visible = panel_context.get("visible_panels", [])
            if visible:
                parts.append(f"\nVisible panels: {', '.join(visible)}\n")
            date_range = panel_context.get("calendar_date_range")
            if date_range:
                parts.append(f"Calendar showing: {date_range}\n")

        full_context = "\n".join(parts)

        # Truncate to budget
        return self._truncate_to_budget(full_context, max_tokens)

    def build_memory_context(
        self,
        memory_content: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Build memory context section.

        Args:
            memory_content: Raw memory content from retrieval.
            max_tokens: Maximum tokens for memory section.

        Returns:
            Formatted memory context.
        """
        max_tokens = max_tokens or self.MEMORY_BUDGET

        if not memory_content:
            return ""

        # Truncate if needed
        truncated = self._truncate_to_budget(memory_content, max_tokens)

        return f"""## Relevant Memory

{truncated}

---"""

    def build_conversation_context(
        self,
        conversation: Optional[Conversation] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        max_turns: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Build conversation history context.

        Args:
            conversation: Conversation object with history.
            messages: Optional direct list of messages.
            max_turns: Maximum conversation turns to include.

        Returns:
            List of message dicts for context.
        """
        if messages:
            history = messages
        elif conversation:
            history = conversation.get_recent_context(max_turns)
        else:
            history = []

        # Calculate tokens and truncate if needed
        total_tokens = 0
        truncated_history = []

        for msg in reversed(history):  # Start from most recent
            msg_tokens = self._count_tokens(msg.get("content", ""))
            if total_tokens + msg_tokens > self.HISTORY_BUDGET:
                break
            truncated_history.insert(0, msg)
            total_tokens += msg_tokens

        return truncated_history

    def build(
        self,
        request: Request,
        memory_context: str = "",
        conversation: Optional[Conversation] = None,
        additional_system_instructions: Optional[str] = None,
        agent_config: Any = None,
        chat_context: Optional[Dict[str, Any]] = None,
        cloud_safe: bool = False,
        user_profile_context: str = "",
        principles: str = "",
        budget_override: Optional[int] = None,
    ) -> tuple[List[Message], PromptComponents]:
        """
        Build complete prompt for inference.

        Args:
            request: The incoming request.
            memory_context: Retrieved memory content.
            conversation: Optional conversation for history.
            additional_system_instructions: Extra system instructions.
            agent_config: Optional AgentConfig for .md-based prompt assembly.
                          If provided, overrides the legacy PERSONAS system.
            chat_context: Optional workspace context from v2 chat API
                          (active_tab, selected_text, attached_files, etc.).
            cloud_safe: If True, use minimal system prompt without personality.
                        Tool definitions are still included (functional, not private).
            principles: Pre-formatted approved behavioral principles string.
                        Injected as a "## Behavioral Principles" section.
                        Excluded when cloud_safe=True (same policy as user identity).

        Returns:
            Tuple of (messages list, prompt components).
        """
        mode = request.mode

        if cloud_safe:
            # Persona included, PII excluded (user profile filtered upstream)
            system_prompt = self.build_system_prompt(
                mode=mode,
                additional_instructions=additional_system_instructions,
            )
        elif agent_config is not None:
            # Build system prompt — prefer .md config if available
            system_prompt = self.build_system_prompt_from_config(
                agent_config=agent_config,
                additional_instructions=additional_system_instructions,
            )
        else:
            system_prompt = self.build_system_prompt(
                mode=mode,
                additional_instructions=additional_system_instructions,
            )

        # Build memory context
        formatted_memory = self.build_memory_context(memory_context)

        # Build conversation history
        history = self.build_conversation_context(conversation)

        # Create components for tracking
        components = PromptComponents(
            system_prompt=system_prompt,
            memory_context=formatted_memory,
            conversation_history=history,
            user_message=request.content,
        )

        # Count tokens for each component
        components.system_tokens = self._count_tokens(system_prompt)
        components.memory_tokens = self._count_tokens(formatted_memory)
        components.history_tokens = sum(
            self._count_tokens(m.get("content", ""))
            for m in history
        )
        components.user_tokens = self._count_tokens(request.content)

        # Build workspace context (v2 API)
        formatted_context = self.build_context_block(chat_context)

        # Build user profile context (markdown-based identity system)
        # Uses USER_MODEL_BUDGET (2K tokens) for user profile injection.
        # When cloud_safe, excludes PII-sensitive files (USER-IDENTITY.md, BODY.md).
        formatted_user_profile = ""
        if user_profile_context:
            formatted_user_profile = self._truncate_to_budget(
                user_profile_context, self.USER_MODEL_BUDGET
            )

        # Build messages list
        messages = []

        # System message (includes user profile + workspace context + memory)
        full_system = system_prompt
        if formatted_user_profile:
            full_system = f"{full_system}\n\n{formatted_user_profile}"
        if formatted_context:
            full_system = f"{full_system}\n\n{formatted_context}"
        if formatted_memory:
            full_system = f"{full_system}\n\n{formatted_memory}"
        # Inject approved behavioral principles (excluded from cloud-safe builds)
        if principles and not cloud_safe:
            full_system = f"{full_system}\n\n## Behavioral Principles\n{principles}"

        messages.append(Message(role="system", content=full_system))

        # Add conversation history
        for msg in history:
            messages.append(Message(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))

        # Add current user message
        messages.append(Message(role="user", content=request.content))

        return messages, components

    def check_budget(self, components: PromptComponents, budget_override: Optional[int] = None) -> Dict[str, Any]:
        """
        Check token budget usage.

        Args:
            components: Prompt components with token counts.
            budget_override: Optional budget ceiling (e.g. 200K for cloud routes).

        Returns:
            Budget status dictionary.
        """
        budget = budget_override or self.TOTAL_BUDGET
        total = components.total_tokens
        percentage = total / budget

        return {
            "total_tokens": total,
            "budget": budget,
            "percentage": percentage,
            "warning": percentage >= self.WARNING_THRESHOLD,
            "exceeded": total > budget,
            "breakdown": {
                "system": components.system_tokens,
                "memory": components.memory_tokens,
                "history": components.history_tokens,
                "user": components.user_tokens,
            }
        }

    def estimate_response_budget(self, components: PromptComponents, budget_override: Optional[int] = None) -> int:
        """
        Estimate available tokens for response.

        Args:
            components: Prompt components with token counts.
            budget_override: Optional budget ceiling (e.g. 200K for cloud routes).

        Returns:
            Available tokens for response.
        """
        budget = budget_override or self.TOTAL_BUDGET
        used = components.total_tokens
        available = budget - used

        # Cap at reasonable response length (higher for cloud)
        max_response = 8192 if budget_override and budget_override > self.TOTAL_BUDGET else 4096
        return min(available, max_response)


# Module-level singleton
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get or create the singleton prompt builder instance."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
