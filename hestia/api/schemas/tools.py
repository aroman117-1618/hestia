"""
Tool definition schemas.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """A tool parameter definition."""
    type: str = Field(description="Parameter type")
    description: str = Field(description="Parameter description")
    required: bool = Field(description="Whether parameter is required")
    default: Optional[Any] = Field(None, description="Default value")
    enum_values: Optional[List[str]] = Field(None, description="Allowed values")


class ToolDefinition(BaseModel):
    """A tool definition."""
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    category: str = Field(description="Tool category")
    requires_approval: bool = Field(description="Whether tool requires approval")
    parameters: Dict[str, ToolParameter] = Field(
        default_factory=dict,
        description="Tool parameters"
    )


class ToolsResponse(BaseModel):
    """Response listing available tools."""
    tools: List[ToolDefinition] = Field(description="Available tools")
    count: int = Field(description="Total tool count")
