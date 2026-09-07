"""Tests for PLUTO's local intelligence layer (Phase 1).

Covers the whole pipeline: classifier training + prediction + confidence,
entity extraction, persistent SQLite memory, and the brain's multi-step
planning. Everything is local - no external AI/API.
"""
from __future__ import annotations

import os

import pytest

from app.intelligence.classifier import LocalIntentClassifier
from app.intelligence.dataset import build_dataset
from app.intelligence.entities import extract_entities, summarize_entities
from app.intelligence.memory import PlutoMemory
from app.intelligence.brain import PlutoBrain
from app.agent.nlu import NLUStep


# ---------------------------------------------------------------------------
# Fixtures: isolated model + db (never touch ~/.pluto defaults)
# ---------------------------------------------------------------------------
@pytest.fixture()
def tmp_model(tmp_path):
    return str(tmp_path / "intent.joblib")


@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "pluto.db")


def _trained_classifier(model_path: str) -> LocalIntentClassifier:
    clf = LocalIntentClassifier(model_path=model_path)
    clf.fit(build_dataset())
    return clf


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
class TestClassifier:
    def test_trains_and_predicts_representative_commands(self, tmp_model):
        clf = _trained_classifier(tmp_model)
        cases = {
            "take a screenshot": "take_screenshot",
            "set volume to 40": "set_volume",
            "create a file called notes.txt": "create_file",
            "what apps are running": "list_apps",
            "search for iron man on youtube": "browser_search",
            "delete the file old-report.txt": "delete_file",
            "send a whatsapp message to mom saying hi": "send_message",
            "run ls -la": "run_command",
            "who are you": "identity",
            "what can you do": "help",
        }
        for command, expected in cases.items():
            label, conf = clf.predict(command)
            assert label == expected, f"{command!r} -> {label!r} (expected {expected!r})"
            assert 0.0 <= conf <= 1.0

    def test_predict_topk_and_distribution(self, tmp_model):
        clf = _trained_classifier(tmp_model)
        top = clf.predict_topk("take a screenshot", k=3)
        assert len(top) == 3
        assert top[0][0] == "take_screenshot"
        dist = clf.distribution("take a screenshot")
        assert "take_screenshot" in dist
        # probabilities sum to ~1.
        assert abs(sum(dist.values()) - 1.0) < 0.05

    def test_is_trained_and_save_load_roundtrip(self, tmp_model):
        clf = _trained_classifier(tmp_model)
        assert clf.is_trained()
        path = clf.save()
        assert os.path.isfile(path)

        clf2 = LocalIntentClassifier(model_path=tmp_model)
        assert clf2.load() is True
        label, _ = clf2.predict("take a screenshot")
        assert label == "take_screenshot"

    def test_evaluate_shape(self, tmp_model):
        clf = LocalIntentClassifier(model_path=tmp_model)
        texts = [t for t, _ in build_dataset()]
        labels = [l for _, l in build_dataset()]
        metrics = clf.evaluate(texts, labels)
        assert {"accuracy", "f1_macro", "report", "test_samples"} <= set(metrics)
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert metrics["test_samples"] > 0

    def test_untrained_predict_is_empty(self, tmp_model):
        clf = LocalIntentClassifier(model_path=tmp_model)
        label, conf = clf.predict("hello")
        assert label == "" and conf == 0.0


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
class TestEntities:
    def test_extract_app_and_site(self):
        assert extract_entities("open firefox")["app"] == "firefox"
        assert extract_entities("go to youtube")["site"] == "youtube"

    def test_extract_path_and_file(self):
        ents = extract_entities("create a file called notes.txt in my Documents folder")
        assert ents.get("file") == "notes.txt"
        assert ents.get("directory") == "~/Documents"

    def test_extract_volume_number(self):
        assert extract_entities("set volume to 55")["volume"] == 55

    def test_extract_ordinal(self):
        assert extract_entities("play the second video")["ordinal"] == 1

    def test_extract_query(self):
        ents = extract_entities("search for iron man on youtube")
        assert "iron man" in (ents.get("query") or "")

    def test_extract_clipboard_and_recipient(self):
        assert extract_entities("copy hello to the clipboard")["clipboard_text"] == "hello"
        ents = extract_entities("send a whatsapp message to mom saying hi")
        assert "mom" in (ents.get("recipient") or "")

    def test_summarize_empty(self):
        assert summarize_entities({}) == ""


# ---------------------------------------------------------------------------
# Memory (SQLite persistence)
# ---------------------------------------------------------------------------
class TestMemory:
    def test_records_actions_and_outcomes(self, tmp_db):
        mem = PlutoMemory(db_path=tmp_db)
        mem.record_action("s1", "open_url", command="open youtube",
                          intent="open_website", parameters={"url": "youtube"},
                          result="Loaded", success=True)
        mem.record_action("s1", "delete_file", command="delete x",
                          intent="delete_file", success=False,
                          error="denied")
        actions = mem.recent_actions()
        assert len(actions) == 2
        stats = mem.outcome_stats()
        assert stats["success"] == 1
        assert stats["failure"] == 1
        mem.close()

    def test_corrections_feed_learning(self, tmp_db):
        mem = PlutoMemory(db_path=tmp_db)
        mem.record_correction("open firefox", "open_application",
                              predicted_intent="open_website")
        pairs = mem.correction_pairs()
        assert pairs == [("open firefox", "open_application")]
        mem.close()

    def test_metadata_roundtrip(self, tmp_db):
        mem = PlutoMemory(db_path=tmp_db)
        mem.set_model_meta("accuracy", {"acc": 0.8})
        meta = mem.get_model_meta("accuracy")
        assert meta == {"acc": 0.8}
        mem.close()

    def test_context_snapshot_roundtrip(self, tmp_db):
        mem = PlutoMemory(db_path=tmp_db)
        mem.save_context("s1", {"current_url": "https://youtube.com",
                                "last_search_query": "iron man",
                                "recent_files": ["/home/u/x.txt"]})
        assert mem.load_context("s1")["current_url"] == "https://youtube.com"
        assert mem.context_sessions() == ["s1"]
        mem.delete_context("s1")
        assert mem.load_context("s1") is None
        mem.close()

    def test_correction_pairs_feed_trainer(self, tmp_db):
        mem = PlutoMemory(db_path=tmp_db)
        mem.record_correction("open firefox", "open_application", predicted_intent="open_website")
        mem.record_correction("close the browser", "browser_control")
        pairs = mem.correction_pairs()
        assert len(pairs) == 2
        assert ("open firefox", "open_application") in pairs
        mem.close()


# ---------------------------------------------------------------------------
# Brain (pipeline: understand + plan)
# ---------------------------------------------------------------------------
class TestBrain:
    def _brain(self, tmp_model, tmp_db):
        return PlutoBrain(
            classifier=LocalIntentClassifier(model_path=tmp_model),
            memory=PlutoMemory(db_path=tmp_db),
        )

    def test_understand_reports_intent_confidence_entities(self, tmp_model, tmp_db):
        brain = self._brain(tmp_model, tmp_db)
        brain.classifier.fit(build_dataset())
        brain._model_ready = True
        u = brain.understand("set volume to 40")
        assert u.intent == "set_volume"
        assert 0.0 <= u.confidence <= 1.0
        assert u.entities.get("volume") == 40
        assert u.top_intents and u.top_intents[0][0] == "set_volume"

    def test_plan_is_multi_step_and_only_uses_real_tools(self, tmp_model, tmp_db):
        brain = self._brain(tmp_model, tmp_db)
        brain.classifier.fit(build_dataset())
        brain._model_ready = True
        result = brain.plan("open YouTube and search for Iron Man")
        names = [s.name for s in result.steps if isinstance(s, NLUStep)]
        assert names == ["open_url", "browser_search"]
        # The dominant intent of a composite request may be either "open a
        # website" or "search" - both are true; the plan is authoritative.
        assert result.intent in ("open_website", "browser_search")
        assert "open_url" in result.recommended_tools
        assert "browser_search" in result.recommended_tools

    def test_plan_handles_confirmation_tool(self, tmp_model, tmp_db):
        brain = self._brain(tmp_model, tmp_db)
        brain.classifier.fit(build_dataset())
        brain._model_ready = True
        result = brain.plan("delete the file old-report.txt")
        names = [s.name for s in result.steps if isinstance(s, NLUStep)]
        assert names == ["delete_file"]

    def test_record_action_and_stats(self, tmp_model, tmp_db):
        brain = self._brain(tmp_model, tmp_db)
        brain.classifier.fit(build_dataset())
        brain._model_ready = True
        brain.record_action("s1", "open_url", command="open yt",
                            intent="open_website", success=True, confidence=0.6)
        assert brain.outcome_stats()["success"] == 1


# ---------------------------------------------------------------------------
# Feedback learning / correction endpoint
# ---------------------------------------------------------------------------
class TestCorrectionEndpoint:
    def test_correct_intent_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.intelligence.dataset import INTENT_LABELS

        assert "open_application" in INTENT_LABELS
        with TestClient(app) as client:
            r = client.post(
                "/api/chat/correct",
                json={"input": "open firefox to the docs",
                      "correct_intent": "open_application",
                      "predicted_intent": "open_website"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["success"] is True
            assert body["correct_intent"] == "open_application"

    def test_correct_intent_rejects_bad_payload(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post("/api/chat/correct", json={"input": "", "correct_intent": ""})
            assert r.status_code == 200
            assert r.json()["success"] is False

    def test_intelligence_status_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get("/api/tools/intelligence/status")
            assert r.status_code == 200
            body = r.json()
            assert body["engine"].startswith("local")
            assert "outcomes" in body
