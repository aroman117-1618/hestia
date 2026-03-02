"""
System health schemas (server health check endpoint).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import HealthStatusEnum


class InferenceHealth(BaseModel):
    """Inference component health."""
    status: HealthStatusEnum = Field(description="Component status")
    ollama_available: Optional[bool] = Field(None, description="Ollama availability")
    primary_model_available: Optional[bool] = Field(None, description="Primary model available")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class MemoryHealth(BaseModel):
    """Memory component health."""
    status: HealthStatusEnum = Field(description="Component status")
    vector_count: Optional[int] = Field(None, description="Number of vectors stored")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class StateMachineHealth(BaseModel):
    """State machine component health."""
    status: HealthStatusEnum = Field(description="Component status")
    active_tasks: int = Field(0, description="Number of active tasks")
    state_summary: Optional[Dict[str, int]] = Field(None, description="State counts")


class ToolsHealth(BaseModel):
    """Tools component health."""
    status: HealthStatusEnum = Field(description="Component status")
    registered_tools: int = Field(0, description="Number of registered tools")
    tool_names: Optional[List[str]] = Field(None, description="List of tool names")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthComponents(BaseModel):
    """Health status of all components."""
    inference: InferenceHealth = Field(description="Inference status")
    memory: MemoryHealth = Field(description="Memory status")
    state_machine: StateMachineHealth = Field(description="State machine status")
    tools: ToolsHealth = Field(description="Tools status")


class HealthResponse(BaseModel):
    """System health response."""
    status: HealthStatusEnum = Field(description="Overall system status")
    timestamp: datetime = Field(description="Health check timestamp")
    components: HealthComponents = Field(description="Component health details")
