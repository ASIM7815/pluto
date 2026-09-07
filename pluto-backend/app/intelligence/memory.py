"""PLUTO's persistent memory (SQLite).

Replaces the ephemeral in-memory view with a durable store that survives
restarts. This is what lets PLUTO *remember* and *learn*:

- ``actions``        every tool action + its outcome (success/failure/confidence)
                     -> used for feedback learning and honest reporting.
- ``corrections``    user corrections of an intent (input, predicted intent,
                     correct intent) -> the trainer folds these into the model.
- ``model_meta``     key/value metadata (model version, last accuracy, etc).

Uses SQLite from the standard library (no server, no external DB). The store is
file-backed under ``~/.pluto`` by default so it is local and offline.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = "~/.pluto/pluto.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    session_id TEXT,
    command TEXT,
    intent TEXT,
    tool TEXT,
    parameters TEXT,
    result TEXT,
    success INTEGER,
    error TEXT,
    confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions(ts DESC);
CREATE INDEX IF NOT EXISTS idx_actions_session ON actions(session_id);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    session_id TEXT,
    input TEXT NOT NULL,
    predicted_intent TEXT,
    correct_intent TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corrections_input ON corrections(input);

CREATE TABLE IF NOT EXISTS model_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS contexts (
    session_id TEXT PRIMARY KEY,
    data TEXT,
    updated_ts TEXT
);
"""


class PlutoMemory:
    """Thread-safe SQLite-backed persistent memory for PLUTO."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = os.path.expanduser(db_path or DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        logger.info("memory_initialized", path=self.db_path)

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # actions
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
        params = json.dumps(parameters or {}, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO actions (ts, session_id, command, intent, tool, "
                "parameters, result, success, error, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (self._now(), session_id, command, intent, tool, params,
                 result, int(bool(success)), error, confidence),
            )
            self._conn.commit()

    def recent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM actions ORDER BY ts DESC LIMIT ?", (int(limit),)
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def outcome_stats(self) -> Dict[str, int]:
        """Counts of successes/failures (the signal the trainer learns from)."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT success, COUNT(*) AS c FROM actions GROUP BY success"
            )
            rows = {int(r["success"]): int(r["c"]) for r in cur.fetchall()}
            return {"success": rows.get(1, 0), "failure": rows.get(0, 0)}

    # ------------------------------------------------------------------
    # corrections -> feedback learning
    # ------------------------------------------------------------------
    def record_correction(
        self,
        input_text: str,
        correct_intent: str,
        session_id: Optional[str] = None,
        predicted_intent: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO corrections (ts, session_id, input, predicted_intent, correct_intent) "
                "VALUES (?, ?, ?, ?, ?)",
                (self._now(), session_id, input_text, predicted_intent, correct_intent),
            )
            self._conn.commit()
        logger.info("correction_recorded", input=input_text, correct=correct_intent)

    def corrections(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM corrections ORDER BY ts DESC"
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def correction_pairs(self) -> List[tuple]:
        """Return ``[(input, correct_intent), ...]`` for the trainer to fold in."""
        with self._lock:
            cur = self._conn.execute("SELECT input, correct_intent FROM corrections")
            return [(r["input"], r["correct_intent"]) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # model metadata
    # ------------------------------------------------------------------
    def set_model_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO model_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
            self._conn.commit()

    def get_model_meta(self, key: str) -> Any:
        with self._lock:
            cur = self._conn.execute(
                "SELECT value FROM model_meta WHERE key=?", (key,)
            )
        row = cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["value"])
        except Exception:  # noqa: BLE001
            return row["value"]

    def all_model_meta(self) -> Dict[str, Any]:
        with self._lock:
            cur = self._conn.execute("SELECT key, value FROM model_meta")
            return {r["key"]: r["value"] for r in cur.fetchall()}

    def clear_actions(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM actions")
            self._conn.commit()

    # ------------------------------------------------------------------
    # context snapshots (durable session context)
    # ------------------------------------------------------------------
    def save_context(self, session_id: str, data: Dict[str, Any]) -> None:
        """Persist a serialisable context snapshot for a session."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO contexts (session_id, data, updated_ts) VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET data=excluded.data, "
                "updated_ts=excluded.updated_ts",
                (session_id, json.dumps(data or {}, ensure_ascii=False), self._now()),
            )
            self._conn.commit()

    def load_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a persisted context snapshot, or None when absent."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT data FROM contexts WHERE session_id=?", (session_id,)
            )
        row = cur.fetchone()
        if row is None or not row["data"]:
            return None
        try:
            return json.loads(row["data"])
        except Exception:  # noqa: BLE001
            logger.warning("context_deserialize_error", session=session_id)
            return None

    def delete_context(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM contexts WHERE session_id=?", (session_id,)
            )
            self._conn.commit()

    def context_sessions(self) -> List[str]:
        with self._lock:
            cur = self._conn.execute("SELECT session_id FROM contexts")
            return [r["session_id"] for r in cur.fetchall()]

    def clear_contexts(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM contexts")
            self._conn.commit()

    def clear_corrections(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM corrections")
            self._conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {k: row[k] for k in row.keys()}


# Canonical singleton used across the app.
#
# Important: we do NOT open the SQLite file at import time (that would create
# ~/.pluto/pluto.db as an import side-effect and make tests/imports heavier).
# Instead a lazy proxy initialises the real store on first attribute access.
class _LazyMemory:
    """Proxy that builds the real ``PlutoMemory`` only on first use."""

    def __init__(self) -> None:
        self._real: Optional[PlutoMemory] = None

    def _ensure(self) -> PlutoMemory:
        if self._real is None:
            self._real = PlutoMemory()
        return self._real

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure(), name)


pluto_memory = _LazyMemory()


def get_memory(db_path: Optional[str] = None) -> PlutoMemory:
    """Return the canonical full ``PlutoMemory`` singleton.

    ``db_path`` is only honoured the first time (the singleton owns one store);
    passing it is useful for fresh test instances instead.
    """
    global _pluto_memory
    if _pluto_memory is None:
        _pluto_memory = PlutoMemory(db_path)
    return _pluto_memory


_pluto_memory: Optional[PlutoMemory] = None
