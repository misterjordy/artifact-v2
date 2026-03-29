"""Extractor dispatcher: pick extractor by file extension."""

from artiFACT.modules.import_pipeline.extractors.base import ExtractorBase
from artiFACT.modules.import_pipeline.extractors.docx_extractor import DocxExtractor
from artiFACT.modules.import_pipeline.extractors.pdf_extractor import PdfExtractor
from artiFACT.modules.import_pipeline.extractors.pptx_extractor import PptxExtractor
from artiFACT.modules.import_pipeline.extractors.text_extractor import TextExtractor

_EXTRACTORS: dict[str, type[ExtractorBase]] = {
    "docx": DocxExtractor,
    "pptx": PptxExtractor,
    "pdf": PdfExtractor,
    "txt": TextExtractor,
    "md": TextExtractor,
}


def get_extractor(filename: str) -> ExtractorBase:
    """Return the appropriate extractor for the given filename."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    extractor_cls = _EXTRACTORS.get(ext)
    if extractor_cls is None:
        raise ValueError(f"No extractor for extension: .{ext}")
    return extractor_cls()
