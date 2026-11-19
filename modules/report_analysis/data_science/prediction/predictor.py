"""Cached specialty model loading and guarded probability predictions."""

import logging
import os
from threading import Lock

import joblib

from modules.report_analysis.data_science.preprocessing.text import normalize_clinical_text

logger = logging.getLogger(__name__)

_MODEL_INSTANCE = None
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "specialty_classifier.joblib",
)
_MODEL_LOCK = Lock()


def get_model():
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is not None:
        return _MODEL_INSTANCE
    with _MODEL_LOCK:
        if _MODEL_INSTANCE is None and os.path.isfile(_MODEL_PATH):
            try:
                model = joblib.load(_MODEL_PATH)
                if not callable(getattr(model, "predict_proba", None)) or not hasattr(model, "classes_"):
                    raise TypeError("The specialty model does not support probability predictions.")
                _MODEL_INSTANCE = model
            except Exception as e:
                logger.warning(f"Failed to load specialty model: {e}")
                _MODEL_INSTANCE = None
    return _MODEL_INSTANCE


def warm_up_models():
    """Warm up cached ML models at app startup."""
    return get_model()


def predict_specialty_probabilities(text: str) -> dict:
    """Returns a dict of {specialty_code: probability_float}."""
    model = get_model()
    text = normalize_clinical_text(text)
    if model is None or not text:
        return {}

    try:
        classes = model.classes_
        probs = model.predict_proba([text])[0]
        return {
            str(cls_name): float(prob)
            for cls_name, prob in zip(classes, probs)
            if 0.0 <= float(prob) <= 1.0
        }
    except Exception as e:
        logger.warning(f"Prediction failed: {e}")
        return {}
