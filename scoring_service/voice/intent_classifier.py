"""F-007/9 intent classifier inference: embed with LaBSE (frozen), predict
with the LogisticRegression head trained in train_intent_classifier.py.

Run: python -m scoring_service.voice.intent_classifier
"""

from __future__ import annotations

import sys
from pathlib import Path

from joblib import load
from sentence_transformers import SentenceTransformer

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252, breaks on Hindi/Tamil text

from scoring_service.voice.train_intent_classifier import ARTIFACTS_DIR, EMBEDDING_MODEL_NAME

_embedder: SentenceTransformer | None = None
_classifier = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


def _get_classifier():
    global _classifier
    if _classifier is None:
        path = ARTIFACTS_DIR / "intent_classifier_logreg.joblib"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing -- run `python -m scoring_service.voice.train_intent_classifier` first")
        _classifier = load(path)
    return _classifier


def predict_intent(text: str) -> dict:
    embedder = _get_embedder()
    clf = _get_classifier()

    embedding = embedder.encode([text], normalize_embeddings=True)
    probs = clf.predict_proba(embedding)[0]
    classes = clf.classes_
    best_idx = probs.argmax()

    return {
        "text": text,
        "intent": classes[best_idx],
        "confidence": round(float(probs[best_idx]), 4),
        "all_probabilities": {c: round(float(p), 4) for c, p in zip(classes, probs)},
    }


if __name__ == "__main__":
    import json

    test_queries = [
        "मेरा लोन कब अप्रूव होगा",
        "என் கடன் வரம்பு ஏன் குறைந்தது",
        "Why do you need my transaction data",
        "namaste",
    ]
    for q in test_queries:
        print(json.dumps(predict_intent(q), indent=2, ensure_ascii=False))
