"""
Tests for PromptBuilder principles injection.

Verifies that approved behavioral principles are injected into the system
message when cloud_safe=False, and excluded when cloud_safe=True.
"""

import pytest
from unittest.mock import MagicMock

from hestia.orchestration.prompt import PromptBuilder


@pytest.fixture
def prompt_builder():
    mode_manager = MagicMock()
    mode_manager.get_system_prompt.return_value = "You are Tia."
    return PromptBuilder(mode_manager=mode_manager)


def test_principles_injected_when_not_cloud_safe(prompt_builder):
    """Approved principles appear in the system message when cloud_safe=False."""
    request = MagicMock()
    request.content = "hello"
    request.mode = MagicMock()
    request.context = None

    messages, components = prompt_builder.build(
        request=request,
        memory_context="",
        principles="[scheduling] User prefers bullet summaries",
        cloud_safe=False,
    )

    # Principles are appended to full_system and appear in messages[0].content
    # (NOT in components.system_prompt, which is the base persona prompt only)
    system_message_content = messages[0].content
    assert "Behavioral Principles" in system_message_content
    assert "[scheduling]" in system_message_content


def test_principles_excluded_when_cloud_safe(prompt_builder):
    """Approved principles are NOT in the system message when cloud_safe=True."""
    request = MagicMock()
    request.content = "hello"
    request.mode = MagicMock()
    request.context = None

    messages, components = prompt_builder.build(
        request=request,
        memory_context="",
        principles="[scheduling] User prefers bullet summaries",
        cloud_safe=True,
    )

    system_message_content = messages[0].content
    assert "Behavioral Principles" not in system_message_content
