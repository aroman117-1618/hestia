"""
Hestia Council Module.

Multi-role LLM council for enhanced intent classification,
tool extraction, response validation, and personality synthesis.

Dual-path execution:
  - Cloud active: all roles run in parallel via cloud API
  - Cloud disabled: Coordinator only via SLM (qwen2.5:0.5b)
"""

from .models import (
    IntentType,
    IntentClassification,
    ToolExtraction,
    ValidationReport,
    RoleResult,
    CouncilResult,
    CouncilConfig,
)
from .roles import (
    CouncilRole,
    Coordinator,
    Analyzer,
    Validator,
    Responder,
)
from .manager import CouncilManager, get_council_manager

__all__ = [
    # Models
    "IntentType",
    "IntentClassification",
    "ToolExtraction",
    "ValidationReport",
    "RoleResult",
    "CouncilResult",
    "CouncilConfig",
    # Roles
    "CouncilRole",
    "Coordinator",
    "Analyzer",
    "Validator",
    "Responder",
    # Manager
    "CouncilManager",
    "get_council_manager",
]
