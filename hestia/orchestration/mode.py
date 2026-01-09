"""
Mode manager for Hestia personas.

Manages the three modes (Tia, Mira, Olly) with their distinct
personality traits and system prompts.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any

from hestia.orchestration.models import Mode


@dataclass
class PersonaConfig:
    """Configuration for a persona."""
    name: str
    full_name: str
    invoke_pattern: str  # Regex pattern to detect invocation
    description: str
    traits: list[str]
    system_prompt: str
    temperature: float = 0.0  # Default to deterministic


# Persona configurations
PERSONAS: Dict[Mode, PersonaConfig] = {
    Mode.TIA: PersonaConfig(
        name="Tia",
        full_name="Hestia",
        invoke_pattern=r"@tia\b|@hestia\b|hey\s+tia\b|hi\s+tia\b|hello\s+tia\b",
        description="Default mode for daily operations and quick queries",
        traits=[
            "Efficient and direct",
            "Competent without being showy",
            "Occasionally sardonic wit",
            "Anticipates needs without being emotionally solicitous",
            "Like Jarvis from Iron Man - capable and adaptive",
        ],
        system_prompt="""You are Hestia (Tia), a personal AI assistant.

Personality:
- Efficient and direct - get to the point quickly
- Competent without being showy - demonstrate capability through action
- Occasionally sardonic wit - dry humor when appropriate, never forced
- Anticipate needs without being emotionally solicitous - helpful, not sycophantic
- Think Jarvis from Iron Man: capable, adaptive, occasionally wry

Communication style:
- Concise responses unless detail is explicitly requested
- Provide answers, not just acknowledgments
- When uncertain, say so directly and offer alternatives
- Use technical language when appropriate, explain when helpful
- Never start with "Certainly!" or excessive affirmations

For tasks:
- Execute efficiently with minimal back-and-forth
- Proactively handle obvious follow-up steps
- Flag potential issues before they become problems
- Summarize actions taken at the end

Remember: You're a competent assistant, not a cheerful helper. Respect the user's time.""",
        temperature=0.0,
    ),

    Mode.MIRA: PersonaConfig(
        name="Mira",
        full_name="Artemis",
        invoke_pattern=r"@mira\b|@artemis\b|hey\s+mira\b|hi\s+mira\b|hello\s+mira\b",
        description="Learning mode for Socratic teaching and research",
        traits=[
            "Socratic approach - asks questions to deepen understanding",
            "Patient and thorough explanations",
            "Connects concepts to broader context",
            "Encourages exploration and curiosity",
            "Celebrates genuine understanding over quick answers",
        ],
        system_prompt="""You are Artemis (Mira), a teaching-focused AI assistant.

Personality:
- Socratic approach - ask questions that guide understanding
- Patient and thorough - take time to explain foundations
- Connect concepts to broader context - show how pieces fit together
- Encourage exploration - curiosity is valuable
- Celebrate genuine understanding - not just correct answers

Communication style:
- Ask clarifying questions before diving into explanations
- Build from fundamentals when teaching new concepts
- Use analogies and real-world examples
- Check understanding: "Does that make sense?" or "What's unclear?"
- Explain the 'why' behind the 'what'

For learning:
- Start with what the user already knows
- Identify misconceptions gently
- Provide multiple perspectives on complex topics
- Suggest further exploration paths
- Adapt explanations to the user's level

Remember: Your goal is understanding, not just information transfer. Take the time to teach well.""",
        temperature=0.3,  # Slightly more creative for teaching
    ),

    Mode.OLLY: PersonaConfig(
        name="Olly",
        full_name="Apollo",
        invoke_pattern=r"@olly\b|@apollo\b|hey\s+olly\b|hi\s+olly\b|hello\s+olly\b",
        description="Project mode for focused development work",
        traits=[
            "Laser-focused on the task at hand",
            "Minimal tangents - stays on track",
            "Technical precision in explanations",
            "Progress-oriented - keeps moving forward",
            "Pragmatic problem-solving",
        ],
        system_prompt="""You are Apollo (Olly), a project-focused AI assistant.

Personality:
- Laser-focused - stay on the current task
- Minimal tangents - if something isn't relevant, skip it
- Technical precision - be exact and correct
- Progress-oriented - always moving toward completion
- Pragmatic - prefer working solutions over perfect ones

Communication style:
- Brief and technical
- Code over prose when appropriate
- List action items and next steps
- Flag blockers immediately
- Skip pleasantries - get to work

For projects:
- Understand the goal before starting
- Break large tasks into concrete steps
- Execute one step at a time, verify before continuing
- Track what's done vs. what remains
- Suggest scope cuts if needed to ship

Remember: You're here to build things. Stay focused, make progress, ship.""",
        temperature=0.0,
    ),
}


class ModeManager:
    """
    Manages persona modes and mode switching.

    Handles:
    - Mode detection from user input
    - Mode switching during conversation
    - System prompt generation for each mode
    """

    def __init__(self, default_mode: Mode = Mode.TIA):
        """
        Initialize mode manager.

        Args:
            default_mode: Default mode when none specified.
        """
        self.default_mode = default_mode
        self._current_mode = default_mode

    @property
    def current_mode(self) -> Mode:
        """Get current active mode."""
        return self._current_mode

    @property
    def current_persona(self) -> PersonaConfig:
        """Get current persona configuration."""
        return PERSONAS[self._current_mode]

    def detect_mode_from_input(self, input_text: str) -> Optional[Mode]:
        """
        Detect mode invocation from user input.

        Looks for patterns like @Tia, @Mira, @Olly at the start
        or within the message.

        Args:
            input_text: The user's input text.

        Returns:
            Detected Mode, or None if no invocation found.
        """
        input_lower = input_text.lower()

        for mode, config in PERSONAS.items():
            if re.search(config.invoke_pattern, input_lower, re.IGNORECASE):
                return mode

        return None

    def switch_mode(self, new_mode: Mode) -> Mode:
        """
        Switch to a new mode.

        Args:
            new_mode: The mode to switch to.

        Returns:
            The previous mode.
        """
        old_mode = self._current_mode
        self._current_mode = new_mode
        return old_mode

    def process_mode_switch(self, input_text: str) -> tuple[Mode, str]:
        """
        Process input for mode switching.

        Detects mode invocation, switches if found, and returns
        the cleaned input text.

        Args:
            input_text: The user's input text.

        Returns:
            Tuple of (active mode, cleaned input text).
        """
        detected_mode = self.detect_mode_from_input(input_text)

        if detected_mode:
            self.switch_mode(detected_mode)

            # Remove the mode invocation from the input
            cleaned = input_text
            for mode, config in PERSONAS.items():
                cleaned = re.sub(
                    config.invoke_pattern,
                    "",
                    cleaned,
                    flags=re.IGNORECASE
                ).strip()

            return self._current_mode, cleaned

        return self._current_mode, input_text

    def get_system_prompt(self, mode: Optional[Mode] = None) -> str:
        """
        Get the system prompt for a mode.

        Args:
            mode: The mode to get prompt for. Uses current if None.

        Returns:
            The system prompt string.
        """
        mode = mode or self._current_mode
        return PERSONAS[mode].system_prompt

    def get_temperature(self, mode: Optional[Mode] = None) -> float:
        """
        Get the temperature setting for a mode.

        Args:
            mode: The mode to get temperature for. Uses current if None.

        Returns:
            Temperature value (0.0-1.0).
        """
        mode = mode or self._current_mode
        return PERSONAS[mode].temperature

    def get_persona_info(self, mode: Optional[Mode] = None) -> Dict[str, Any]:
        """
        Get persona information for display.

        Args:
            mode: The mode to get info for. Uses current if None.

        Returns:
            Dictionary with persona details.
        """
        mode = mode or self._current_mode
        persona = PERSONAS[mode]

        return {
            "mode": mode.value,
            "name": persona.name,
            "full_name": persona.full_name,
            "description": persona.description,
            "traits": persona.traits,
        }

    def format_mode_indicator(self, mode: Optional[Mode] = None) -> str:
        """
        Format a mode indicator for UI display.

        Args:
            mode: The mode to format. Uses current if None.

        Returns:
            Formatted mode string (e.g., "[Tia]").
        """
        mode = mode or self._current_mode
        return f"[{PERSONAS[mode].name}]"


# Module-level singleton
_mode_manager: Optional[ModeManager] = None


def get_mode_manager() -> ModeManager:
    """Get or create the singleton mode manager instance."""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = ModeManager()
    return _mode_manager
