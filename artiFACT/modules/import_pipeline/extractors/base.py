"""Base extractor ABC."""

from abc import ABC, abstractmethod


class ExtractorBase(ABC):
    """Abstract base for document text extractors."""

    @abstractmethod
    def extract(self, content: bytes) -> str:
        """Extract text from file content bytes."""
        ...
