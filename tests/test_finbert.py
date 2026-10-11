from app.integrations import finbert


def test_score_texts_normalizes_the_model_output(monkeypatch):
    class FakeClassifier:
        def __call__(self, texts, batch_size):
            return [[{"label": "Positive", "score": 0.7}, {"label": "Negative", "score": 0.2}, {"label": "Neutral", "score": 0.1}] for _ in texts]

    monkeypatch.setattr(finbert, "load_model", lambda model_name: FakeClassifier())
    scored = finbert.score_texts(["x"], "any-model")
    assert scored[0]["label"] == "positive" and scored[0]["compound"] == 0.5
    assert scored[0]["probs"] == {"positive": 0.7, "neutral": 0.1, "negative": 0.2}


def test_score_texts_with_no_texts_does_not_load_the_model(monkeypatch):
    monkeypatch.setattr(finbert, "load_model", lambda model_name: (_ for _ in ()).throw(AssertionError("model loaded")))
    assert finbert.score_texts([], "any-model") == []
