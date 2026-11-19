"""Evaluation summaries for a trained specialty classifier."""

from sklearn.metrics import accuracy_score, classification_report, f1_score


def evaluate_classifier(model, texts, expected_labels):
    """Return stable scalar and per-label metrics for a fitted classifier."""
    texts = list(texts)
    expected_labels = list(expected_labels)
    if not texts or len(texts) != len(expected_labels):
        raise ValueError("Texts and expected labels must be non-empty and have equal lengths.")
    predicted = model.predict(texts)
    return {
        "accuracy": float(accuracy_score(expected_labels, predicted)),
        "macro_f1": float(f1_score(expected_labels, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(expected_labels, predicted, average="weighted", zero_division=0)),
        "classification_report": classification_report(
            expected_labels, predicted, output_dict=True, zero_division=0
        ),
    }
