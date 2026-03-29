"""DOCX text extraction using python-docx."""

import io

from docx import Document

from artiFACT.modules.import_pipeline.extractors.base import ExtractorBase


class DocxExtractor(ExtractorBase):
    """Extract text from DOCX files."""

    def extract(self, content: bytes) -> str:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
