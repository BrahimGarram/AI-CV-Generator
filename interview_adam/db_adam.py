"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Persistance du simulateur : tables `interview_sessions` et `interview_qa`.

Même fichier SQLite que la plateforme (`data/cv_platform.db`) mais connexion et verrou
propres : `db.py` (Module 1) n'est ni importé ni modifié. `timeout=30` évite les erreurs
« database is locked » si les deux modules écrivent en même jour, les écritures restent
courtes, et le mode WAL n'est pas activé (cela changerait le fichier partagé avec le Module 1).

Schéma idempotent (`CREATE TABLE IF NOT EXISTS`), créé à la première utilisation :
pas de migration externe, cohérent avec l'approche de `db.py`.
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from interview_adam import config_adam as cfg

_LOCK = threading.Lock()
_INIT_LOCK = threading.Lock()
_CONN = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS interview_sessions (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_title        TEXT NOT NULL,
    company          TEXT,
    job_description  TEXT,
    seniority        TEXT NOT NULL,
    question_type    TEXT NOT NULL,
    language         TEXT NOT NULL,
    n_questions      INTEGER NOT NULL,
    model            TEXT,
    status           TEXT NOT NULL,
    cv_generation_id TEXT,
    summary_json     TEXT,
    created_at       TEXT NOT NULL,
    finished_at      TEXT
);

CREATE TABLE IF NOT EXISTS interview_qa (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    idx             INTEGER NOT NULL,
    question        TEXT NOT NULL,
    category        TEXT NOT NULL,
    focus           TEXT,
    expected_json   TEXT,
    answer          TEXT,
    score           REAL,
    criteria_json   TEXT,
    strengths_json  TEXT,
    weaknesses_json TEXT,
    verdict         TEXT,
    improved_json   TEXT,
    created_at      TEXT NOT NULL,
    answered_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_interview_sessions_user
    ON interview_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interview_qa_session
    ON interview_qa(session_id, idx);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id():
    return uuid.uuid4().hex


def _connect():
    global _CONN
    with _INIT_LOCK:
        if _CONN is None:
            cfg.DB_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CONN = sqlite3.connect(str(cfg.DB_FILE), check_same_thread=False, timeout=30)
            _CONN.row_factory = sqlite3.Row
            _CONN.execute("PRAGMA foreign_keys = ON")
            _CONN.executescript(SCHEMA)
    return _CONN


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _loads(value, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except ValueError:
        return default


def _row(row):
    return dict(row) if row is not None else None


def _rows(cursor):
    return [dict(r) for r in cursor.fetchall()]


def reset_connection():
    """Ferme la connexion (tests avec fichier jetable, rechargement à chaud)."""
    global _CONN
    with _INIT_LOCK:
        if _CONN is not None:
            _CONN.close()
            _CONN = None


# ----------------------------------------------------------------------
# Sessions
# ----------------------------------------------------------------------

def create_session(user_id, job_title, company, job_description, seniority, question_type,
                   language, n_questions, model=None, cv_generation_id=None):
    session_id = _new_id()
    conn = _connect()
    with _LOCK, conn:
        conn.execute(
            "INSERT INTO interview_sessions (id, user_id, job_title, company, job_description, "
            "seniority, question_type, language, n_questions, model, status, cv_generation_id, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?)",
            (session_id, user_id, job_title, company, job_description, seniority, question_type,
             language, n_questions, model, cv_generation_id, _now()),
        )
    return session_id


def get_session(session_id, user_id):
    """Session + questions-réponses, uniquement si elle appartient à `user_id`."""
    conn = _connect()
    with _LOCK:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id)).fetchone()
        if row is None:
            return None
        qa = _rows(conn.execute(
            "SELECT * FROM interview_qa WHERE session_id = ? ORDER BY idx", (session_id,)))
    session = _row(row)
    session["answers"] = [_expand_qa(item) for item in qa]
    return session


def list_sessions(user_id, limit=50):
    """
    Historique : une ligne par session avec le comptage et la moyenne déjà calculés en SQL.
    La liste n'a pas besoin des questions : l'écran de synthèse les relit séparément.
    """
    conn = _connect()
    with _LOCK:
        rows = _rows(conn.execute(
            "SELECT id, job_title, company, seniority, question_type, language, status, "
            "n_questions, summary_json, created_at, finished_at, "
            "(SELECT COUNT(*) FROM interview_qa q WHERE q.session_id = s.id "
            " AND q.answer IS NOT NULL) AS answered, "
            "(SELECT ROUND(AVG(q.score), 1) FROM interview_qa q WHERE q.session_id = s.id "
            " AND q.answer IS NOT NULL AND q.score IS NOT NULL) AS average_score "
            "FROM interview_sessions s WHERE s.user_id = ? "
            "ORDER BY s.created_at DESC LIMIT ?",
            (user_id, limit)))
    for item in rows:
        item["summary"] = _loads(item.pop("summary_json"), None)
    return rows


def attach_questions(session_id, questions):
    """Enregistre les questions générées (une ligne par question, réponse vide)."""
    conn = _connect()
    now = _now()
    with _LOCK, conn:
        conn.executemany(
            "INSERT INTO interview_qa (id, session_id, idx, question, category, focus, "
            "expected_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(_new_id(), session_id, item["index"], item["question"], item.get("category") or "technical",
              item.get("focus"), _dumps(item.get("expected_points") or []), now)
             for item in questions],
        )


def save_evaluation(session_id, index, answer, evaluation):
    conn = _connect()
    with _LOCK, conn:
        conn.execute(
            "UPDATE interview_qa SET answer = ?, score = ?, criteria_json = ?, strengths_json = ?, "
            "weaknesses_json = ?, verdict = ?, answered_at = ? WHERE session_id = ? AND idx = ?",
            (answer, evaluation.get("score"), _dumps(evaluation.get("criteria")),
             _dumps(evaluation.get("strengths") or []), _dumps(evaluation.get("weaknesses") or []),
             evaluation.get("verdict"), _now(), session_id, index),
        )


def save_improvement(session_id, index, improvement):
    conn = _connect()
    with _LOCK, conn:
        conn.execute("UPDATE interview_qa SET improved_json = ? WHERE session_id = ? AND idx = ?",
                     (_dumps(improvement), session_id, index))


def finish_session(session_id, user_id, summary):
    conn = _connect()
    with _LOCK, conn:
        cursor = conn.execute(
            "UPDATE interview_sessions SET status = 'finished', summary_json = ?, finished_at = ? "
            "WHERE id = ? AND user_id = ?",
            (_dumps(summary), _now(), session_id, user_id))
    return cursor.rowcount > 0


def delete_session(session_id, user_id):
    """
    Suppression d'une session, bornée à son propriétaire dans le WHERE : sans cette
    condition, un identifiant deviné effacerait la session d'un autre compte.
    Les réponses attachées partent avec elle (`interview_qa ... ON DELETE CASCADE`),
    il n'y a donc pas de second DELETE à écrire — ni de ligne orpheline possible.
    """
    conn = _connect()
    with _LOCK, conn:
        cursor = conn.execute("DELETE FROM interview_sessions WHERE id = ? AND user_id = ?",
                              (session_id, user_id))
    return cursor.rowcount > 0


def _expand_qa(row):
    row["expected_points"] = _loads(row.pop("expected_json"), [])
    row["criteria"] = _loads(row.pop("criteria_json"), {})
    row["strengths"] = _loads(row.pop("strengths_json"), [])
    row["weaknesses"] = _loads(row.pop("weaknesses_json"), [])
    row["improvement"] = _loads(row.pop("improved_json"), None)
    return row
