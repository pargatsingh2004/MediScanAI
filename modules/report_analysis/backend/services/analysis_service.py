"""Public module API around the established report analysis pipeline."""

from backend.core.healthcare_intelligence.backend.workspace_analysis import (
    analyze_extracted_report,
    generate_ai_comparison,
    normalize_language,
)


def analyze_report(text, raw_text="", filename="Report", file_bytes=b"", language="en"):
    """Analyze OCR text and return the stable workspace payload shape."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("Readable report text is required for analysis.")
    return analyze_extracted_report(
        text,
        raw_text=str(raw_text or ""),
        filename=str(filename or "Report"),
        file_bytes=bytes(file_bytes or b""),
        language=normalize_language(language),
    )


def generate_comparison_summary(reports, metrics, language="en"):
    """Generate a report-grounded plain-language comparison summary."""
    return generate_ai_comparison(reports, metrics, normalize_language(language))
