"""FinBERT sentiment model (a local text classifier, loaded once and shared).

Loading takes about 10 seconds, so `load_model` is also called in the background at startup (see
app/warmup.py) and the first user request does not have to wait for it.
"""

from __future__ import annotations

import threading

SENTIMENT_LABELS = ("positive", "neutral", "negative")
MAX_TOKENS_PER_TEXT = 128
BATCH_SIZE = 16

_model_lock = threading.Lock()   # guards loading and running: the model is not meant for parallel threads
_classifier = None
_loaded_model_name: str | None = None


def load_model(model_name: str):
    """Load the model on first use. Safe to call from several threads."""
    global _classifier, _loaded_model_name
    with _model_lock:
        if _classifier is None or _loaded_model_name != model_name:
            # Imported here so the API starts fast and tests can run without torch.
            from transformers import pipeline

            _classifier = pipeline(
                "text-classification",
                model=model_name,
                top_k=None,  # return the probability of every label
                truncation=True,
                max_length=MAX_TOKENS_PER_TEXT,
            )
            _loaded_model_name = model_name
        return _classifier


def score_texts(texts: list[str], model_name: str) -> list[dict]:
    """Score each text. Returns, per text:

    {"label": "positive|neutral|negative", "score": probability of that label,
     "compound": positive minus negative probability (-1 to +1),
     "probs": {"positive": .., "neutral": .., "negative": ..}}
    """
    if not texts:
        return []
    classifier = load_model(model_name)
    with _model_lock:  # one inference at a time
        raw_results = classifier(texts, batch_size=BATCH_SIZE)
    scored = []
    for per_label in raw_results:
        probabilities = {item["label"].lower(): float(item["score"]) for item in per_label}
        for label in SENTIMENT_LABELS:
            probabilities.setdefault(label, 0.0)
        best_label = max(SENTIMENT_LABELS, key=lambda name: probabilities[name])
        scored.append(
            {
                "label": best_label,
                "score": round(probabilities[best_label], 4),
                "compound": round(probabilities["positive"] - probabilities["negative"], 4),
                "probs": {name: round(probabilities[name], 4) for name in SENTIMENT_LABELS},
            }
        )
    return scored
