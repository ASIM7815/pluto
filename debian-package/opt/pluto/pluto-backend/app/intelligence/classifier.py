"""PLUTO's local intent classifier (scikit-learn, fully offline).

Design goals:
- No external model/API. Uses TF-IDF + a linear classifier that PLUTO trains
  itself on its own dataset.
- Confidence via probability outputs so the orchestrator can gate actions
  that fall below a confidence threshold.
- Save / load the model to disk (joblib) so PLUTO keeps its learned intent
  model between runs and can improve it from user corrections.
- Fast and light: no GPU, no PyTorch needed. scikit-learn is sufficient and
  appropriate for sentence-level intent classification of short commands.

The pipeline is:  raw text -> TfidfVectorizer -> SGDClassifier(modified_huber).
``SGDClassifier(loss='modified_huber')`` provides calibrated-ish probabilities
(``predict_proba``) at linear cost, which is exactly what we need for short
NLU commands.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple, Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default model location (kept under PLUTO's home so it survives restarts).
DEFAULT_MODEL_PATH = "~/.pluto/models/intent_classifier.joblib"

# Decision threshold: below this, the brain treats the input as ambiguous and
# asks for clarification rather than guessing.
DEFAULT_CONFIDENCE_THRESHOLD = 0.42

_LABEL_KEY = "intent_labels"
_MODEL_KEY = "model"


class LocalIntentClassifier:
    """A small, trainable, saveable local intent classifier."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.model_path = os.path.expanduser(model_path or DEFAULT_MODEL_PATH)
        self.confidence_threshold = confidence_threshold
        self.labels: List[str] = []
        self._pipeline: Any = None

    # ------------------------------------------------------------------
    # training
    # ------------------------------------------------------------------
    def train(
        self,
        texts: Sequence[str],
        labels: Sequence[str],
        extra_texts: Optional[Sequence[str]] = None,
        extra_labels: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Fit the classifier on (text, label) pairs.

        ``extra_texts``/``extra_labels`` let the trainer add user corrections on
        top of the seed dataset without mutating the seed corpus.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.pipeline import make_pipeline, FeatureUnion

        all_texts = list(texts)
        all_labels = list(labels)
        if extra_texts and extra_labels:
            all_texts.extend(list(extra_texts))
            all_labels.extend(list(extra_labels))

        if not all_texts:
            raise ValueError("Cannot train an empty dataset.")

        unique_labels = sorted(set(all_labels))
        # Combined word + character n-grams: char features tolerate the
        # paraphrase/morphology variation common in short commands.
        features = FeatureUnion([
            ("word", TfidfVectorizer(
                lowercase=True, sublinear_tf=True, strip_accents="unicode",
                analyzer="word", ngram_range=(1, 2), min_df=1, max_df=0.98,
                max_features=30000,
            )),
            ("char", TfidfVectorizer(
                lowercase=True, sublinear_tf=True, strip_accents="unicode",
                analyzer="char_wb", ngram_range=(2, 5), min_df=1, max_df=0.98,
                max_features=30000,
            )),
        ])
        # Calibrated LinearSVC gives strong performance on short text AND
        # calibrated probabilities for the confidence score.
        base = LinearSVC(random_state=42, max_iter=6000, class_weight="balanced")
        clf = CalibratedClassifierCV(base, cv=3)
        pipeline = make_pipeline(features, clf)
        pipeline.fit(all_texts, all_labels)

        self._pipeline = pipeline
        self.labels = unique_labels
        logger.info(
            "intent_model_trained",
            samples=len(all_texts),
            classes=len(unique_labels),
            model_path=self.model_path,
        )

        # Quick in-sample accuracy for logging only.
        try:
            acc = float(pipeline.score(all_texts, all_labels))
        except Exception:  # noqa: BLE001
            acc = 0.0
        return {
            "samples": len(all_texts),
            "classes": len(unique_labels),
            "in_sample_accuracy": round(acc, 4),
        }

    def fit(self, samples: Sequence[Tuple[str, str]],
            extra: Optional[Sequence[Tuple[str, str]]] = None) -> Dict[str, Any]:
        """Convenience fit from ``[(text, label), ...]`` tuples."""
        texts = [s[0] for s in samples]
        labels = [s[1] for s in samples]
        extra_texts = [s[0] for s in extra] if extra else None
        extra_labels = [s[1] for s in extra] if extra else None
        return self.train(texts, labels, extra_texts, extra_labels)

    # ------------------------------------------------------------------
    # prediction
    # ------------------------------------------------------------------
    def is_trained(self) -> bool:
        return self._pipeline is not None

    def predict(self, text: str) -> Tuple[str, float]:
        """Return ``(intent_label, confidence)`` for a single utterance."""
        if not self.is_trained():
            return "", 0.0
        try:
            probs = self._pipeline.predict_proba([text])[0]
        except ValueError:
            return "", 0.0
        idx = int(probs.argmax())
        label = self._pipeline.classes_[idx]
        return str(label), round(float(probs[idx]), 4)

    def predict_topk(self, text: str, k: int = 3) -> List[Tuple[str, float]]:
        """Return the top-k ``(label, confidence)`` pairs, best first."""
        if not self.is_trained():
            return []
        try:
            probs = self._pipeline.predict_proba([text])[0]
        except ValueError:
            return []
        order = probs.argsort()[::-1][:k]
        return [(str(self._pipeline.classes_[i]), round(float(probs[i]), 4)) for i in order]

    def distribution(self, text: str) -> Dict[str, float]:
        """Full label->confidence distribution (for introspection)."""
        if not self.is_trained():
            return {}
        try:
            probs = self._pipeline.predict_proba([text])[0]
        except ValueError:
            return {}
        return {
            str(label): round(float(prob), 4)
            for label, prob in zip(self._pipeline.classes_, probs)
        }

    def is_confident(self, label: str, confidence: float) -> bool:
        """Whether a prediction clears the ambiguity threshold."""
        return bool(confidence >= self.confidence_threshold)

    # ------------------------------------------------------------------
    # evaluation
    # ------------------------------------------------------------------
    def evaluate(
        self,
        texts: Sequence[str],
        labels: Sequence[str],
        test_size: float = 0.25,
    ) -> Dict[str, Any]:
        """Stratified train/test evaluation + per-class report.

        Returns accuracy, a macro-averaged F1, per-class metrics and the test
        size used. Used by the trainer to report PLUTO's real skill.
        """
        from sklearn.metrics import accuracy_score, f1_score, classification_report
        from sklearn.model_selection import train_test_split

        if len(texts) < 4:
            return {
                "accuracy": 0.0, "f1_macro": 0.0, "report": {},
                "test_samples": 0, "note": "Not enough samples for a split.",
            }
        x_train, x_test, y_train, y_test = train_test_split(
            list(texts), list(labels),
            test_size=test_size, random_state=42, stratify=labels,
        )
        self.train(x_train, y_train)
        preds = self._pipeline.predict(x_test)
        report = classification_report(
            y_test, preds, output_dict=True, zero_division=0
        )
        return {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "f1_macro": round(float(f1_score(y_test, preds, average="macro", zero_division=0)), 4),
            "report": report,
            "test_samples": len(x_test),
            "train_samples": len(x_train),
        }

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def save(self, path: Optional[str] = None) -> str:
        """Persist the model to disk (joblib). Returns the path written."""
        if not self.is_trained():
            raise RuntimeError("Cannot save an untrained model.")
        import joblib

        target = os.path.expanduser(path or self.model_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        joblib.dump(
            {"model": self._pipeline, _LABEL_KEY: self.labels},
            target,
        )
        logger.info("intent_model_saved", path=target)
        return target

    def load(self, path: Optional[str] = None) -> bool:
        """Load a previously trained model. Returns True on success."""
        target = os.path.expanduser(path or self.model_path)
        if not os.path.isfile(target):
            return False
        try:
            import joblib

            data = joblib.load(target)
            self._pipeline = data[_MODEL_KEY]
            self.labels = data.get(_LABEL_KEY, [])
            logger.info("intent_model_loaded", path=target, classes=len(self.labels))
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("intent_model_load_error", path=target, error=str(e))
            return False

    def load_or_train(self, samples: Sequence[Tuple[str, str]]) -> bool:
        """Load the model if present; otherwise train it on ``samples``."""
        if self.load():
            return True
        self.fit(samples)
        try:
            self.save()
        except Exception as e:  # noqa: BLE001
            logger.warning("intent_model_save_skipped", error=str(e))
        return True
