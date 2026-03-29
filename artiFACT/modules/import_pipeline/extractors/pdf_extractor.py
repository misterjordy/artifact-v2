"""PDF text extraction using pdfminer.six."""

import io

from pdfminer.high_level import extract_text

from artiFACT.modules.import_pipeline.extractors.base import ExtractorBase


class PdfExtractor(ExtractorBase):
    """Extract text from PDF files."""

    def extract(self, content: bytes) -> str:
        return extract_text(io.BytesIO(content)).strip()
