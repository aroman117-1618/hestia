"""
Base extractor abstract class for the Investigate module.

All content extractors inherit from BaseExtractor and implement
the extract() method for their specific content type.
"""

from abc import ABC, abstractmethod

from ..models import ContentType, ExtractionResult


class BaseExtractor(ABC):
    """Abstract base class for content extractors."""

    @property
    @abstractmethod
    def content_type(self) -> ContentType:
        """The content type this extractor handles."""
        ...

    @abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """
        Extract content from a URL.

        Args:
            url: The URL to extract content from.

        Returns:
            ExtractionResult with extracted text and metadata.
        """
        ...

    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle a URL.

        Default implementation delegates to classify_url().
        Subclasses can override for custom logic.
        """
        from . import classify_url
        return classify_url(url) == self.content_type
