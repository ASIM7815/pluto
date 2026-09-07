# PLUTO Local Intelligence (`app/intelligence/`)

PLUTO's brain is **fully local**. It does not call OpenAI, GPT, Gemini, Claude,
Ollama, LM Studio, OpenRouter, Groq or any other external model/API. Everything
runs on this machine using Python + lightweight local libraries.

## Pipeline

```
input → natural-language understanding → intent detection → entity extraction
     → context → confidence → task planning → tool selection → execution
     → observation → verification → recovery → result
```

This is implemented by `PlutoBrain` (`brain.py`), used by the active
orchestrator (`app/agent/pattern_orchestrator.py`).

## Modules

| Module | Responsibility |
|--------|----------------|
| `dataset.py` | PLUTO's own command→intent corpus (33 intents, ~400 examples). |
| `classifier.py` | TF-IDF + word/char n-grams + calibrated LinearSVC. `train`, `predict`, `predict_topk`, `evaluate`, `save`, `load`. Confidence via `predict_proba`. |
| `entities.py` | Rule/dictionary/regex extraction: apps, sites, paths, files, numbers, ordinals, volumes, recipients, queries, screenshot area, processes. |
| `similarity.py` | TF-IDF cosine semantic similarity + difflib fuzzy fallback. |
| `memory.py` | SQLite store: `actions`, `corrections`, `model_meta`. Persistent memory + feedback-learning source. |
| `brain.py` | `PlutoBrain` — understand + plan + record. Wraps the classifier, entity extractor, and the deterministic multi-step planner (`app/agent/nlu.py`). |
| `trainer.py` | `python -m app.intelligence.trainer` — train, evaluate, save, smoke-test. |

## Train / evaluate

```bash
cd pluto-backend
python -m app.intelligence.trainer
```

- Loads the seed corpus **plus** any user corrections stored in SQLite.
- Reports held-out accuracy + macro F1 + per-class metrics.
- Saves the model to `~/.pluto/models/intent_classifier.joblib`.
- Writes the metric into `model_meta` so the settings UI can show it.

## How confidence is used

- `PlutoBrain.understand` returns `(intent, confidence, entities, top_intents)`.
- The planner is authoritative for *what to do*; confidence is an honest signal
  about *how sure PLUTO is of the intent*. Low-confidence requests are flagged
  `ambiguous` and PLUTO asks for clarification rather than guessing.
- Confirmation-gated destructive tools still require user approval regardless
  of confidence (safety is independent of ML confidence).

## Persistence / learning

Every executed action is written to SQLite (`actions`) with its outcome. User
corrections are written to `corrections`. Retraining folds corrections back in,
so PLUTO improves from real feedback. Context (current app/browser/file/search)
is still in-memory per session (Phase 3 will persist it to SQLite too).
