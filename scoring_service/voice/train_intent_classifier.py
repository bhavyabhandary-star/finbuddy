"""F-007/9 intent classifier: LogisticRegression head on top of frozen
LaBSE multilingual sentence embeddings (109 languages, verified Hindi +
Tamil coverage -- see intent_data.py docstring for why LaBSE was chosen
over the more common MiniLM multilingual model).

This is intentionally NOT a fine-tuned transformer (no gradient updates to
LaBSE's weights) -- with ~80 total training examples across 5 intents in
5-6 language variants each, fine-tuning a full transformer would overfit
badly. A linear head on frozen embeddings is the honest, appropriately
sized model for this amount of data; it's also fast enough to retrain in
seconds as more real intent data comes in.

Run: python -m scoring_service.voice.train_intent_classifier
"""

from __future__ import annotations

import json
from pathlib import Path

from joblib import dump
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from scoring_service.voice.intent_data import flatten

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
EMBEDDING_MODEL_NAME = "sentence-transformers/LaBSE"


def train() -> dict:
    texts, labels = flatten()
    X_train_text, X_test_text, y_train, y_test = train_test_split(
        texts, labels, test_size=0.3, random_state=42, stratify=labels
    )

    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    X_train = embedder.encode(X_train_text, normalize_embeddings=True)
    X_test = embedder.encode(X_test_text, normalize_embeddings=True)

    clf = LogisticRegression(max_iter=2000, C=2.0)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dump(clf, ARTIFACTS_DIR / "intent_classifier_logreg.joblib")

    metrics = {
        "model": "F-007/9 intent classifier (LogisticRegression on frozen LaBSE embeddings)",
        "embedding_model": EMBEDDING_MODEL_NAME,
        "n_train": len(X_train_text),
        "n_test": len(X_test_text),
        "test_accuracy": round(float(accuracy), 4),
        "per_class_report": report,
        "caveat": (
            "Trained on ~80 authored synthetic examples across 5 intents in "
            "Hindi/Tamil/English -- no real WhatsApp conversation data exists "
            "for this project yet. Treat this as a working prototype of the "
            "approach, not a production-validated classifier; production would "
            "need real user queries and a much larger, language-balanced "
            "labeled set."
        ),
    }
    with open(ARTIFACTS_DIR / "intent_classifier_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    return metrics


if __name__ == "__main__":
    result = train()
    print(json.dumps({k: v for k, v in result.items() if k != "per_class_report"}, indent=2, ensure_ascii=False))
    print(f"\nTest accuracy: {result['test_accuracy']} ({result['n_test']} held-out examples)")
