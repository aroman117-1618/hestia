"""
Orchestration module for Hestia.

Provides request routing, state management, and workflow coordination.

Components:
- Request/Response models
- Task state machine
- Mode manager (Tia/Mira/Olly personas)
- Prompt builder with memory injection
- Validation pipeline
- Main request handler
"""

from hestia.orchestration.models import (
    Request,
    Response,
    ResponseType,
    Task,
    TaskState,
    Mode,
    RequestSource,
    Conversation,
    VALID_TRANSITIONS,
    is_valid_transition,
)

from hestia.orchestration.state import (
    TaskStateMachine,
    InvalidTransitionError,
    TaskTimeoutError,
)

from hestia.orchestration.mode import (
    ModeManager,
    PersonaConfig,
    PERSONAS,
    get_mode_manager,
)

from hestia.orchestration.prompt import (
    PromptBuilder,
    PromptComponents,
    get_prompt_builder,
)

from hestia.orchestration.validation import (
    ValidationPipeline,
    ValidationResult,
    ValidationLevel,
    ValidationErrorType,
    RequestValidator,
    ResponseValidator,
    get_validation_pipeline,
)

from hestia.orchestration.handler import (
    RequestHandler,
    get_request_handler,
)

__all__ = [
    # Models
    "Request",
    "Response",
    "ResponseType",
    "Task",
    "TaskState",
    "Mode",
    "RequestSource",
    "Conversation",
    "VALID_TRANSITIONS",
    "is_valid_transition",
    # State Machine
    "TaskStateMachine",
    "InvalidTransitionError",
    "TaskTimeoutError",
    # Mode Manager
    "ModeManager",
    "PersonaConfig",
    "PERSONAS",
    "get_mode_manager",
    # Prompt Builder
    "PromptBuilder",
    "PromptComponents",
    "get_prompt_builder",
    # Validation
    "ValidationPipeline",
    "ValidationResult",
    "ValidationLevel",
    "ValidationErrorType",
    "RequestValidator",
    "ResponseValidator",
    "get_validation_pipeline",
    # Handler
    "RequestHandler",
    "get_request_handler",
]
