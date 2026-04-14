#!/usr/bin/env python3
"""
Chronos Temporal Database

Persists the prediction → intervention → outcome feedback loop.
Uses SQLite (WAL mode) to track:
  - predictions: goal + simulated interventions with confidence scores
  - outcomes: what actually happened after an intervention was applied
  - leverage_history: which intervention types have historically worked

Schema is append-only so the feedback loop never loses data.
"""

import json
import logging
import random
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chronos_predictions (
    id          TEXT PRIMARY KEY,
    goal        TEXT NOT NULL,
    horizon_days INTEGER NOT NULL DEFAULT 30,
    context     TEXT,
    n_simulations INTEGER NOT NULL DEFAULT 50,
    interventions TEXT NOT NULL,   -- JSON array of Intervention dicts
    summary     TEXT,
    confidence  REAL,
    created_at  REAL NOT NULL,
    domain      TEXT
);

CREATE TABLE IF NOT EXISTS chronos_outcomes (
    id              TEXT PRIMARY KEY,
    prediction_id   TEXT NOT NULL REFERENCES chronos_predictions(id),
    intervention_id TEXT NOT NULL,
    applied_at      REAL NOT NULL,
    outcome_text    TEXT NOT NULL,
    success         INTEGER,       -- 1 = success, 0 = failure, NULL = unknown
    delta_score     REAL,          -- outcome quality vs predicted (−1.0 to +1.0)
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS chronos_leverage_history (
    id              TEXT PRIMARY KEY,
    intervention_type TEXT NOT NULL,
    domain          TEXT,
    success_count   INTEGER NOT NULL DEFAULT 0,
    failure_count   INTEGER NOT NULL DEFAULT 0,
    avg_delta_score REAL,
    last_updated    REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_predictions_created ON chronos_predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outcomes_prediction ON chronos_outcomes(prediction_id);
CREATE INDEX IF NOT EXISTS idx_leverage_type ON chronos_leverage_history(intervention_type);
"""


def _default_db_path() -> Path:
    return get_hermes_home() / "chronos.db"


class TemporalDB:
    """Thread-safe SQLite store for Chronos prediction/outcome data."""

    def __init__(self, db_path: Optional[Path] = None):
        self._path = Path(db_path or _default_db_path())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self._path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _execute(self, sql: str, params=(), *, retries: int = 5) -> sqlite3.Cursor:
        for attempt in range(retries):
            try:
                return self._conn().execute(sql, params)
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < retries - 1:
                    time.sleep(0.05 * (2 ** attempt) + random.uniform(0, 0.02))
                    continue
                raise

    def _executemany(self, sql: str, params_list) -> None:
        for attempt in range(5):
            try:
                self._conn().executemany(sql, params_list)
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < 4:
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                raise

    def _init_schema(self):
        with self._write_lock:
            conn = self._conn()
            conn.executescript(SCHEMA_SQL)
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def store_prediction(
        self,
        prediction_id: str,
        goal: str,
        interventions: List[Dict[str, Any]],
        horizon_days: int = 30,
        context: str = "",
        n_simulations: int = 50,
        summary: str = "",
        confidence: float = 0.0,
        domain: str = "",
    ) -> str:
        with self._write_lock:
            self._execute(
                """INSERT INTO chronos_predictions
                   (id, goal, horizon_days, context, n_simulations,
                    interventions, summary, confidence, created_at, domain)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction_id,
                    goal,
                    horizon_days,
                    context,
                    n_simulations,
                    json.dumps(interventions, ensure_ascii=False),
                    summary,
                    confidence,
                    time.time(),
                    domain,
                ),
            )
            self._conn().commit()
        return prediction_id

    def get_prediction(self, prediction_id: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM chronos_predictions WHERE id = ?", (prediction_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["interventions"] = json.loads(d["interventions"])
        return d

    def list_predictions(self, limit: int = 20) -> List[Dict]:
        rows = self._execute(
            "SELECT * FROM chronos_predictions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["interventions"] = json.loads(d["interventions"])
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Outcomes
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        outcome_id: str,
        prediction_id: str,
        intervention_id: str,
        outcome_text: str,
        success: Optional[bool] = None,
        delta_score: Optional[float] = None,
        notes: str = "",
    ) -> str:
        with self._write_lock:
            self._execute(
                """INSERT INTO chronos_outcomes
                   (id, prediction_id, intervention_id, applied_at,
                    outcome_text, success, delta_score, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    outcome_id,
                    prediction_id,
                    intervention_id,
                    time.time(),
                    outcome_text,
                    (1 if success else 0) if success is not None else None,
                    delta_score,
                    notes,
                ),
            )
            # Update leverage history
            pred = self.get_prediction(prediction_id)
            if pred:
                for iv in pred["interventions"]:
                    if iv.get("id") == intervention_id:
                        self._update_leverage_history(
                            iv.get("action_type", "unknown"),
                            pred.get("domain", ""),
                            success,
                            delta_score,
                        )
            self._conn().commit()
        return outcome_id

    def _update_leverage_history(
        self,
        intervention_type: str,
        domain: str,
        success: Optional[bool],
        delta_score: Optional[float],
    ):
        row = self._execute(
            "SELECT * FROM chronos_leverage_history WHERE intervention_type = ? AND domain = ?",
            (intervention_type, domain),
        ).fetchone()
        now = time.time()
        if row is None:
            import uuid
            self._execute(
                """INSERT INTO chronos_leverage_history
                   (id, intervention_type, domain, success_count, failure_count,
                    avg_delta_score, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    intervention_type,
                    domain,
                    1 if success else 0,
                    0 if success else 1,
                    delta_score or 0.0,
                    now,
                ),
            )
        else:
            sc = row["success_count"] + (1 if success else 0)
            fc = row["failure_count"] + (0 if success else 1)
            total = sc + fc
            old_avg = row["avg_delta_score"] or 0.0
            new_avg = (old_avg * (total - 1) + (delta_score or 0.0)) / total if total > 0 else 0.0
            self._execute(
                """UPDATE chronos_leverage_history
                   SET success_count = ?, failure_count = ?,
                       avg_delta_score = ?, last_updated = ?
                   WHERE intervention_type = ? AND domain = ?""",
                (sc, fc, new_avg, now, intervention_type, domain),
            )

    # ------------------------------------------------------------------
    # Leverage history (for scoring boost)
    # ------------------------------------------------------------------

    def get_leverage_stats(self, intervention_type: str, domain: str = "") -> Dict:
        row = self._execute(
            "SELECT * FROM chronos_leverage_history WHERE intervention_type = ? AND domain = ?",
            (intervention_type, domain),
        ).fetchone()
        if row:
            return dict(row)
        # Try domain-agnostic
        row = self._execute(
            "SELECT * FROM chronos_leverage_history WHERE intervention_type = ?",
            (intervention_type,),
        ).fetchone()
        return dict(row) if row else {}

    def get_training_data(self) -> List[Dict]:
        """Return all prediction+outcome pairs for model improvement."""
        rows = self._execute(
            """SELECT p.goal, p.domain, p.interventions, p.confidence,
                      o.intervention_id, o.success, o.delta_score
               FROM chronos_predictions p
               JOIN chronos_outcomes o ON o.prediction_id = p.id
               ORDER BY o.applied_at DESC
               LIMIT 500"""
        ).fetchall()
        return [dict(r) for r in rows]
