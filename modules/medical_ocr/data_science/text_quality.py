"""Basic extraction-quality signals for OCR text review."""

import re


def assess_extracted_text(text):
    """Estimate readability from OCR output without treating it as clinical certainty."""
    text = str(text or "").strip()
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    alpha_tokens = [token for token in tokens if any(char.isalpha() for char in token)]
    word_like = [token for token in alpha_tokens if len(token) >= 2]
    ratio = len(word_like) / max(1, len(alpha_tokens))
    return {
        "character_count": len(text),
        "token_count": len(tokens),
        "readability_score": round(ratio, 3),
        "sufficient_text": len(text) >= 20 and len(word_like) >= 3,
    }
