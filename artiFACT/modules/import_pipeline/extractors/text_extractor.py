"""Plain text / markdown passthrough extractor."""

from artiFACT.modules.import_pipeline.extractors.base import ExtractorBase


class TextExtractor(ExtractorBase):
    """Pass through plain text and markdown files."""

    def extract(self, content: bytes) -> str:
        return content.decode("utf-8", errors="replace").strip()
