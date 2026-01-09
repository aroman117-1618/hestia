"""
Validation pipeline for Hestia.

Validates incoming requests and outgoing responses.
Handles retry logic with guidance on validation failures.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from hestia.logging import get_logger, LogComponent
from hestia.orchestration.models import Request, Response, ResponseType


class ValidationLevel(Enum):
    """Validation strictness levels."""
    LENIENT = "lenient"   # Allow most inputs, minimal checks
    STANDARD = "standard"  # Reasonable validation
    STRICT = "strict"      # Maximum validation


class ValidationErrorType(Enum):
    """Types of validation errors."""
    EMPTY_INPUT = "empty_input"
    INPUT_TOO_LONG = "input_too_long"
    INVALID_MODE = "invalid_mode"
    FORBIDDEN_PATTERN = "forbidden_pattern"
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_RESPONSE = "malformed_response"
    INCOMPLETE_RESPONSE = "incomplete_response"
    UNSAFE_CONTENT = "unsafe_content"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    error_type: Optional[ValidationErrorType] = None
    message: Optional[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(valid=True)

    @classmethod
    def failure(
        cls,
        error_type: ValidationErrorType,
        message: str,
        **details
    ) -> "ValidationResult":
        """Create a failed validation result."""
        return cls(
            valid=False,
            error_type=error_type,
            message=message,
            details=details
        )


class RequestValidator:
    """
    Validates incoming requests.
    """

    # Limits
    MAX_INPUT_LENGTH = 32000  # Characters
    MIN_INPUT_LENGTH = 1

    # Patterns to reject (security)
    FORBIDDEN_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+instructions",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"pretend\s+you\s+are\s+(?:jailbroken|unrestricted)",
    ]

    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        """
        Initialize validator.

        Args:
            level: Validation strictness level.
        """
        self.level = level
        self.logger = get_logger()

    def validate(self, request: Request) -> ValidationResult:
        """
        Validate a request.

        Args:
            request: The request to validate.

        Returns:
            Validation result.
        """
        # Check empty input
        if not request.content or not request.content.strip():
            return ValidationResult.failure(
                ValidationErrorType.EMPTY_INPUT,
                "Request content cannot be empty"
            )

        # Check length
        if len(request.content) > self.MAX_INPUT_LENGTH:
            return ValidationResult.failure(
                ValidationErrorType.INPUT_TOO_LONG,
                f"Request exceeds maximum length of {self.MAX_INPUT_LENGTH} characters",
                length=len(request.content),
                max_length=self.MAX_INPUT_LENGTH
            )

        # Check for forbidden patterns (prompt injection attempts)
        if self.level != ValidationLevel.LENIENT:
            content_lower = request.content.lower()
            for pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    self.logger.warning(
                        "Forbidden pattern detected in request",
                        component=LogComponent.ORCHESTRATION,
                        data={"pattern": pattern, "request_id": request.id}
                    )
                    return ValidationResult.failure(
                        ValidationErrorType.FORBIDDEN_PATTERN,
                        "Request contains disallowed content",
                        pattern=pattern
                    )

        return ValidationResult.success()


class ResponseValidator:
    """
    Validates model responses.
    """

    # Response limits
    MIN_RESPONSE_LENGTH = 1
    MAX_RESPONSE_LENGTH = 32000

    # Patterns that indicate incomplete/error responses
    INCOMPLETE_PATTERNS = [
        r"I\s+cannot\s+complete\s+this",
        r"I\s+don't\s+have\s+enough\s+information",
        r"Error:\s*$",
        r"^\s*\.\.\.\s*$",
    ]

    # Patterns that indicate unsafe content (rare with good models)
    UNSAFE_PATTERNS = [
        r"(?:api|secret)_?key\s*[=:]\s*['\"]?[a-zA-Z0-9]{20,}",
        r"password\s*[=:]\s*['\"][^'\"]{4,}['\"]",
    ]

    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        """
        Initialize validator.

        Args:
            level: Validation strictness level.
        """
        self.level = level
        self.logger = get_logger()

    def validate(self, response: Response) -> ValidationResult:
        """
        Validate a response.

        Args:
            response: The response to validate.

        Returns:
            Validation result.
        """
        # Check empty response
        if not response.content or not response.content.strip():
            return ValidationResult.failure(
                ValidationErrorType.EMPTY_RESPONSE,
                "Response content cannot be empty"
            )

        # Check length
        if len(response.content) > self.MAX_RESPONSE_LENGTH:
            return ValidationResult.failure(
                ValidationErrorType.MALFORMED_RESPONSE,
                f"Response exceeds maximum length of {self.MAX_RESPONSE_LENGTH}",
                length=len(response.content)
            )

        # Check for incomplete responses (in strict mode)
        if self.level == ValidationLevel.STRICT:
            content_lower = response.content.lower()
            for pattern in self.INCOMPLETE_PATTERNS:
                if re.search(pattern, response.content, re.IGNORECASE):
                    return ValidationResult.failure(
                        ValidationErrorType.INCOMPLETE_RESPONSE,
                        "Response appears incomplete",
                        pattern=pattern
                    )

        # Check for leaked credentials (always check)
        for pattern in self.UNSAFE_PATTERNS:
            if re.search(pattern, response.content, re.IGNORECASE):
                self.logger.error(
                    "Potential credential leak in response",
                    component=LogComponent.ORCHESTRATION,
                    data={"response_id": response.request_id}
                )
                return ValidationResult.failure(
                    ValidationErrorType.UNSAFE_CONTENT,
                    "Response contains potentially sensitive content"
                )

        return ValidationResult.success()


class ValidationPipeline:
    """
    Orchestrates request and response validation with retry logic.
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        request_level: ValidationLevel = ValidationLevel.STANDARD,
        response_level: ValidationLevel = ValidationLevel.STANDARD,
    ):
        """
        Initialize validation pipeline.

        Args:
            request_level: Validation level for requests.
            response_level: Validation level for responses.
        """
        self.request_validator = RequestValidator(request_level)
        self.response_validator = ResponseValidator(response_level)
        self.logger = get_logger()

    def validate_request(self, request: Request) -> ValidationResult:
        """Validate an incoming request."""
        result = self.request_validator.validate(request)

        if not result.valid:
            self.logger.warning(
                f"Request validation failed: {result.message}",
                component=LogComponent.ORCHESTRATION,
                data={
                    "request_id": request.id,
                    "error_type": result.error_type.value if result.error_type else None
                }
            )

        return result

    def validate_response(self, response: Response) -> ValidationResult:
        """Validate a model response."""
        result = self.response_validator.validate(response)

        if not result.valid:
            self.logger.warning(
                f"Response validation failed: {result.message}",
                component=LogComponent.ORCHESTRATION,
                data={
                    "request_id": response.request_id,
                    "error_type": result.error_type.value if result.error_type else None
                }
            )

        return result

    def create_retry_guidance(
        self,
        validation_result: ValidationResult,
        attempt: int,
    ) -> Optional[str]:
        """
        Create guidance for retry based on validation failure.

        Args:
            validation_result: The failed validation result.
            attempt: Current attempt number.

        Returns:
            Guidance string for retry, or None if should not retry.
        """
        if attempt >= self.MAX_RETRIES:
            return None

        error_type = validation_result.error_type

        guidance_map = {
            ValidationErrorType.EMPTY_RESPONSE: (
                "Your previous response was empty. Please provide a complete response."
            ),
            ValidationErrorType.INCOMPLETE_RESPONSE: (
                "Your previous response appeared incomplete. Please provide a full answer."
            ),
            ValidationErrorType.MALFORMED_RESPONSE: (
                "Your previous response had formatting issues. Please respond clearly."
            ),
        }

        return guidance_map.get(error_type)

    def should_retry(
        self,
        validation_result: ValidationResult,
        attempt: int,
    ) -> bool:
        """
        Determine if a validation failure should trigger a retry.

        Args:
            validation_result: The failed validation result.
            attempt: Current attempt number.

        Returns:
            True if should retry, False otherwise.
        """
        if attempt >= self.MAX_RETRIES:
            return False

        # Only retry for certain error types
        retriable_errors = {
            ValidationErrorType.EMPTY_RESPONSE,
            ValidationErrorType.INCOMPLETE_RESPONSE,
            ValidationErrorType.MALFORMED_RESPONSE,
        }

        return (
            validation_result.error_type is not None and
            validation_result.error_type in retriable_errors
        )


# Module-level singleton
_validation_pipeline: Optional[ValidationPipeline] = None


def get_validation_pipeline() -> ValidationPipeline:
    """Get or create the singleton validation pipeline instance."""
    global _validation_pipeline
    if _validation_pipeline is None:
        _validation_pipeline = ValidationPipeline()
    return _validation_pipeline
