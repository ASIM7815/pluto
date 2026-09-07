"""PLUTO's intelligence pipeline: the local brain.

Implements the flow the task demands, fully offline:

    input -> NLU (intent + entities) -> context -> confidence -> task planning
    -> tool selection -> execution -> observation -> verification -> recovery
    -> result

This module (Phase 1) provides the *understanding + planning + memory* core.
Execution/recovery is wired into the orchestrator (Phase 2) using the exact
``steps`` produced here; the tool layer already verifies each action.

Two sources of intelligence, both local:
1. ``LocalIntentClassifier`` (TF-IDF + linear) -> which intent + confidence.
2. ``app.agent.nlu.intent_planner`` -> the ordered, entity-aware multi-step plan
   (this is the already-tested deterministic planner that turns a request into
   concrete tool calls). The brain enriches it with ML intent + confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.intelligence.classifier import LocalIntentClassifier
from app.intelligence.entities import extract_entities, summarize_entities
from app.intelligence.dataset import build_dataset
from app.intelligence.memory import PlutoMemory, get_memory

logger = get_logger(__name__)


@dataclass
class Understanding:
    """The result of NLU understanding for one utterance."""

    intent: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    top_intents: List[Tuple[str, float]] = field(default_factory=list)
    ambiguous: bool = False


@dataclass
class PlanResult:
    """The full plan: what the user wants + the ordered steps to do it."""

    intent: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    steps: List[Any] = field(default_factory=list)
    recommended_tools: List[str] = field(default_factory=list)

    @property
    def has_action(self) -> bool:
        return any(hasattr(s, "name") for s in self.steps)


# Map a planned tool name -> the high-level intent label (fallback when the
# classifier is not yet trained / returns no confident label).
_TOOL_TO_INTENT: Dict[str, str] = {
    "open_application": "open_application",
    "close_application": "close_application",
    "switch_to_application": "switch_application",
    "list_running_applications": "list_apps",
    "open_url": "open_website",
    "browser_search": "browser_search",
    "browser_click": "browser_click",
    "browser_snapshot": "browser_snapshot",
    "close_browser": "browser_control",
    "browser_key": "browser_control",
    "browser_type": "browser_control",
    "browser_fullscreen": "browser_control",
    "take_screenshot": "take_screenshot",
    "set_volume": "set_volume",
    "get_volume": "get_volume",
    "copy_to_clipboard": "copy_to_clipboard",
    "get_clipboard": "get_clipboard",
    "list_directory": "list_files",
    "find_files": "find_files",
    "create_folder": "create_folder",
    "create_file": "create_file",
    "read_file": "read_file",
    "open_file": "open_file",
    "open_folder": "open_folder",
    "delete_file": "delete_file",
    "move_file": "move_file",
    "copy_file": "copy_file",
    "get_processes": "get_processes",
    "kill_process": "kill_process",
    "send_message": "send_message",
    "open_chat_app": "open_chat",
    "execute_command": "run_command",
}


class PlutoBrain:
    """The local intelligence pipeline for PLUTO."""

    def __init__(
        self,
        classifier: Optional[LocalIntentClassifier] = None,
        memory: Optional[PlutoMemory] = None,
    ) -> None:
        self.classifier = classifier or LocalIntentClassifier()
        self.memory = memory or get_memory()
        self._model_ready = False

    # ------------------------------------------------------------------
    # model bootstrapping
    # ------------------------------------------------------------------
    def ensure_model(self) -> None:
        """Load the persisted model, else train it once on the seed dataset."""
        if self._model_ready:
            return
        # Already trained in-memory? No need to reload/retrain.
        if self.classifier.is_trained():
            self._model_ready = True
            return
        try:
            self.classifier.load_or_train(build_dataset())
            self._model_ready = True
            # Persist some human-visible metadata for the settings page.
            self.memory.set_model_meta("intent_model_loaded_at", self._now())
        except Exception as e:  # noqa: BLE001
            logger.error("intent_model_bootstrap_error", error=str(e))
            # Never raise: the planner still works deterministically.
            self._model_ready = True

    # ------------------------------------------------------------------
    # understanding
    # ------------------------------------------------------------------
    def understand(self, text: str, context: Optional[Dict[str, Any]] = None) -> Understanding:
        """Classify intent, extract entities, score confidence."""
        self.ensure_model()
        if not text or not str(text).strip():
            return Understanding(intent="", confidence=0.0, entities={}, top_intents=[])

        entity_map = extract_entities(text)
        if self.classifier.is_trained():
            intent, confidence = self.classifier.predict(text)
            top = self.classifier.predict_topk(text, k=4)
            ambiguous = not self.classifier.is_confident(intent, confidence)
            if not intent:
                intent, confidence, top = self._fallback_intent(text, context)
        else:
            intent, confidence, top = self._fallback_intent(text, context)
            ambiguous = False

        logger.debug(
            "brain_understand", input=text[:80], intent=intent,
            confidence=confidence, entities=summarize_entities(entity_map),
        )
        return Understanding(
            intent=intent,
            confidence=round(float(confidence), 4),
            entities=entity_map,
            top_intents=top,
            ambiguous=bool(ambiguous),
        )

    # ------------------------------------------------------------------
    # planning
    # ------------------------------------------------------------------
    def plan(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PlanResult:
        """Produce the ordered multi-step plan for a command."""
        self.ensure_model()
        understanding = self.understand(text, context)

        # Use the already-tested deterministic planner for the concrete steps.
        from app.agent.nlu import intent_planner, NLUStep

        steps: List[Any] = []
        try:
            steps = intent_planner.plan(text, context or {})
        except Exception as e:  # noqa: BLE001
            logger.error("brain_plan_error", input=text[:80], error=str(e))
            steps = []

        recommended: List[str] = []
        for step in steps:
            if isinstance(step, NLUStep) and step.name not in recommended:
                recommended.append(step.name)

        return PlanResult(
            intent=understanding.intent,
            confidence=understanding.confidence,
            entities=understanding.entities,
            steps=steps,
            recommended_tools=recommended,
        )

    # ------------------------------------------------------------------
    # fallback intent (when the model isn't trained/confident)
    # ------------------------------------------------------------------
    def _fallback_intent(self, text: str, context: Optional[Dict[str, Any]]) -> Tuple[str, float, List]:
        from app.agent.nlu import intent_planner, NLUStep

        try:
            plan = intent_planner.plan(text, context or {})
        except Exception:  # noqa: BLE001
            plan = []
        tool = next((s.name for s in plan if isinstance(s, NLUStep)), "")
        intent = _TOOL_TO_INTENT.get(tool, "")
        if not intent:
            # Greeting / social detection.
            lowered = (text or "").lower().strip()
            if any(k in lowered for k in ("hello", "hi ", "hey", "howdy", "good morning")):
                intent = "greeting"
            elif any(k in lowered for k in ("thank", "thanks", "well done", "good job")):
                intent = "thanks"
            elif any(k in lowered for k in ("what can you do", "help", "capabilities", "list your skills")):
                intent = "help"
            elif any(k in lowered for k in ("who are you", "what are you", "your name", "introduce yourself")):
                intent = "identity"
        confidence = 0.55 if intent else 0.0
        return intent, confidence, ([(intent, confidence)] if intent else [])

    # ------------------------------------------------------------------
    # memory delegations (used by the orchestrator)
    # ------------------------------------------------------------------
    def record_action(
        self,
        session_id: Optional[str],
        tool: str,
        command: Optional[str] = None,
        intent: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> None:
        try:
            self.memory.record_action(
                session_id=session_id, tool=tool, command=command, intent=intent,
                parameters=parameters, result=result, success=success,
                error=error, confidence=confidence,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("brain_record_action_error", error=str(e))

    def record_correction(
        self,
        input_text: str,
        correct_intent: str,
        session_id: Optional[str] = None,
        predicted_intent: Optional[str] = None,
    ) -> None:
        try:
            self.memory.record_correction(
                input_text, correct_intent, session_id, predicted_intent
            )
        except Exception as e:  # noqa: BLE001
            logger.error("brain_correction_error", error=str(e))

    def outcome_stats(self) -> Dict[str, int]:
        try:
            return self.memory.outcome_stats()
        except Exception:  # noqa: BLE001
            return {"success": 0, "failure": 0}

    def recent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            return self.memory.recent_actions(limit)
        except Exception:  # noqa: BLE001
            return []

    # ------------------------------------------------------------------
    # training
    # ------------------------------------------------------------------
    def train_and_evaluate(self) -> Dict[str, Any]:
        """Train on the seed dataset + any stored corrections, return metrics.

        Evaluation is reported against a held-out stratified split; the
        *persisted* model is then re-trained on the FULL dataset (so it uses
        every example for real use). This folder of outcomes into model meta so
        PLUTO's settings page can show how good its local model is.
        """
        dataset = build_dataset()
        corrections = self.memory.correction_pairs()
        results = self.classifier.evaluate(
            [d[0] for d in dataset], [d[1] for d in dataset]
        )
        # Re-fit on the full corpus so the on-disk model uses all data.
        self.classifier.fit(dataset, extra=corrections)
        self.classifier.save()
        self.memory.set_model_meta(
            "intent_model_accuracy",
            {"accuracy": results.get("accuracy"), "f1_macro": results.get("f1_macro"),
             "train_samples": results.get("train_samples"),
             "test_samples": results.get("test_samples")},
        )
        self._model_ready = True
        logger.info("brain_train_and_evaluate", accuracy=results.get("accuracy"))
        return results

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


# Lazy singleton so importing this package never trains/connects prematurely.
_pluto_brain: Optional[PlutoBrain] = None


def get_brain() -> PlutoBrain:
    global _pluto_brain
    if _pluto_brain is None:
        _pluto_brain = PlutoBrain()
    return _pluto_brain


pluto_brain = get_brain()
