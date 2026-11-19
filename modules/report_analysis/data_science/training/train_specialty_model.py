"""Train and atomically save the specialty classifier from the local JSON dataset."""

import json
import os
import tempfile

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from modules.report_analysis.data_science.preprocessing.text import normalize_clinical_text


def train_model():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, "datasets", "specialties_training_data.json")
    model_dir = os.path.join(base_dir, "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "specialty_classifier.joblib")

    if not os.path.isfile(dataset_path):
        raise FileNotFoundError(f"Specialty training dataset not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("The specialty dataset must be a JSON list.")
    examples = [
        (normalize_clinical_text(item.get("text")), str(item.get("specialty", "")).strip())
        for item in data
        if isinstance(item, dict)
    ]
    examples = [(text, label) for text, label in examples if text and label]
    if len(examples) < 2 or len({label for _, label in examples}) < 2:
        raise ValueError("At least two valid examples and two specialty labels are required.")
    texts, labels = zip(*examples)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english")),
        ("clf", MultinomialNB(alpha=0.5)),
    ])

    pipeline.fit(texts, labels)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=model_dir, suffix=".joblib", delete=False) as temporary_file:
            temporary_path = temporary_file.name
        joblib.dump(pipeline, temporary_path)
        os.replace(temporary_path, model_path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
    return pipeline


if __name__ == "__main__":
    train_model()
