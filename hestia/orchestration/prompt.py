"""
Prompt builder for Hestia.

Constructs prompts with system instructions, memory context,
and conversation history while respecting token budgets.
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
    """

    # Token budget allocation (ADR-011)
    TOTAL_BUDGET = 32768
    SYSTEM_BUDGET = 2000      # Fixed system prompt
    TOOL_BUDGET = 1000        # Tool definitions
    USER_MODEL_BUDGET = 2000  # User model summary
    HISTORY_BUDGET = 20000    # Conversation history
    MEMORY_BUDGET = 4000      # RAG-retrieved memory
    USER_INPUT_BUDGET = 3000  # User's current message

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
    ) -> tuple[List[Message], PromptComponents]:
        """
        Build complete prompt for inference.

        Args:
            request: The incoming request.
            memory_context: Retrieved memory content.
            conversation: Optional conversation for history.
            additional_system_instructions: Extra system instructions.

        Returns:
            Tuple of (messages list, prompt components).
        """
        mode = request.mode

        # Build system prompt
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

        # Build messages list
        messages = []

        # System message (includes memory context)
        if formatted_memory:
            full_system = f"{system_prompt}\n\n{formatted_memory}"
        else:
            full_system = system_prompt

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

    def check_budget(self, components: PromptComponents) -> Dict[str, Any]:
        """
        Check token budget usage.

        Args:
            components: Prompt components with token counts.

        Returns:
            Budget status dictionary.
        """
        total = components.total_tokens
        percentage = total / self.TOTAL_BUDGET

        return {
            "total_tokens": total,
            "budget": self.TOTAL_BUDGET,
            "percentage": percentage,
            "warning": percentage >= self.WARNING_THRESHOLD,
            "exceeded": total > self.TOTAL_BUDGET,
            "breakdown": {
                "system": components.system_tokens,
                "memory": components.memory_tokens,
                "history": components.history_tokens,
                "user": components.user_tokens,
            }
        }

    def estimate_response_budget(self, components: PromptComponents) -> int:
        """
        Estimate available tokens for response.

        Args:
            components: Prompt components with token counts.

        Returns:
            Available tokens for response.
        """
        used = components.total_tokens
        available = self.TOTAL_BUDGET - used

        # Cap at reasonable response length
        return min(available, 4096)


# Module-level singleton
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get or create the singleton prompt builder instance."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
