"""Safe file and byte entry points for the existing PDF/image OCR engine."""

import os
import tempfile

from backend.core.healthcare_intelligence.backend.services.report_extractor import ReportExtractor
from modules.medical_ocr.data_science.text_quality import assess_extracted_text


def extract_from_path(file_path, mime_type=""):
    """Extract OCR text from a local PDF or supported image path."""
    if not file_path or not os.path.isfile(file_path):
        raise ValueError("The report file could not be found.")
    result = ReportExtractor.extract(os.fspath(file_path), str(mime_type or ""))
    result["quality"] = assess_extracted_text(result.get("cleaned_text", ""))
    return result


def extract_from_bytes(content, filename="report.pdf", mime_type=""):
    """Extract from uploaded bytes while always removing the temporary copy."""
    if not content:
        raise ValueError("The report file is empty.")
    suffix = os.path.splitext(os.path.basename(str(filename or "report.pdf")))[1].lower() or ".pdf"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_file.write(bytes(content))
            temporary_path = temporary_file.name
        return extract_from_path(temporary_path, mime_type)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
