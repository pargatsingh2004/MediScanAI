"""Text normalization shared by specialty training and inference."""

import re
import unicodedata


def normalize_clinical_text(value):
    """Normalize whitespace and control characters without changing clinical terms."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
