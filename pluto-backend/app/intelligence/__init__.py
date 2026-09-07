"""PLUTO's own local intelligence layer (NO external AI/API).

This package builds PLUTO's brain using only Python + lightweight local models:

- classifier     TF-IDF + linear classifier (scikit-learn) for intent detection
- entities       rule/dictionary/regex extraction of entities (apps, sites, paths...)
- similarity     TF-IDF cosine semantic similarity + fuzzy fallback
- memory         SQLite persistent memory (actions, corrections, outcomes)
- brain          the full intelligence pipeline: input -> intent -> entities ->
                 context -> confidence -> plan -> tool selection -> observation
                 -> verification -> recovery -> result
- trainer        train / evaluate / persist the local model

There is deliberately NO OpenAI, GPT, Gemini, Claude, Ollama, LM Studio,
OpenRouter or Groq dependency here. Everything runs offline and locally.
"""

from .brain import PlutoBrain, Understanding, PlanResult, pluto_brain

__all__ = [
    "PlutoBrain",
    "Understanding",
    "PlanResult",
    "pluto_brain",
]
