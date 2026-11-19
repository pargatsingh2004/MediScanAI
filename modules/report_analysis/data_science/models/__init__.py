"""On-disk trained specialty model artifacts."""

from pathlib import Path

MODEL_PATH = Path(__file__).with_name("specialty_classifier.joblib")

__all__ = ["MODEL_PATH"]
