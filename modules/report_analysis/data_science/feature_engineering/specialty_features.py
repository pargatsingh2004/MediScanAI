"""Rule features that can be inspected alongside ML specialty predictions."""

from backend.core.healthcare_intelligence.backend.services.specialty_recommender import SPECIALTY_RULES
from modules.report_analysis.data_science.preprocessing.text import normalize_clinical_text


def extract_specialty_keyword_features(text):
    """Return each specialty's matching configured keywords for transparent review."""
    normalized = normalize_clinical_text(text).casefold()
    return {
        code: [keyword for keyword in meta["keywords"] if keyword.casefold() in normalized]
        for code, meta in SPECIALTY_RULES.items()
        if any(keyword.casefold() in normalized for keyword in meta["keywords"])
    }
