"""
Mode (persona) schemas.
"""

from typing import List

from pydantic import BaseModel, Field

from .common import ModeEnum


class PersonaInfo(BaseModel):
    """Information about a persona."""
    mode: ModeEnum = Field(description="Mode identifier")
    name: str = Field(description="Short name (Tia, Mira, Olly)")
    full_name: str = Field(description="Full name (Hestia, Artemis, Apollo)")
    description: str = Field(description="Mode description")
    traits: List[str] = Field(description="Personality traits")


class ModeResponse(BaseModel):
    """Current mode information."""
    current: PersonaInfo = Field(description="Current active persona")
    available: List[ModeEnum] = Field(description="Available modes")


class ModeSwitchRequest(BaseModel):
    """Request to switch mode."""
    mode: ModeEnum = Field(description="Mode to switch to")


class ModeSwitchResponse(BaseModel):
    """Response after switching mode."""
    previous_mode: ModeEnum = Field(description="Previous mode")
    current_mode: ModeEnum = Field(description="New current mode")
    persona: PersonaInfo = Field(description="New persona information")
