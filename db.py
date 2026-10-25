"""
Base de données SQLite de la plateforme (un simple fichier : data/cv_platform.db).

Tables :
- users        : comptes (mot de passe haché, jamais stocké en clair) ;
- generations  : historique des CV générés par chaque utilisateur.
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generations (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    tex_path    TEXT NOT NULL,
    pdf_path    TEXT,
    source      TEXT,
    cv_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generations_user ON generations(user_id, created_at DESC);
"""


def _connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_CONN = _connect()
_CONN.executescript(SCHEMA)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(row):
    return dict(row) if row else None


# ----------------------------------------------------------------------
# Utilisateurs
# ----------------------------------------------------------------------

def create_user(name, email, password_hash):
    user = {"id": uuid.uuid4().hex, "name": name, "email": email.lower(), "created_at": _now()}
    with _LOCK, _CONN:
        _CONN.execute(
            "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], name, user["email"], password_hash, user["created_at"]),
        )
    return user


def get_user_by_email(email):
    with _LOCK:
        return _row(_CONN.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone())


def get_user(user_id):
    with _LOCK:
        return _row(_CONN.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone())


# ----------------------------------------------------------------------
# Historique des CV
# ----------------------------------------------------------------------

def add_generation(generation_id, user_id, title, tex_path, pdf_path, source, cv_data):
    with _LOCK, _CONN:
        _CONN.execute(
            "INSERT INTO generations (id, user_id, title, created_at, tex_path, pdf_path, source, cv_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (generation_id, user_id, title, _now(), str(tex_path), str(pdf_path) if pdf_path else None,
             source, json.dumps(cv_data, ensure_ascii=False)),
        )


def list_generations(user_id):
    with _LOCK:
        rows = _CONN.execute(
            "SELECT id, title, created_at, pdf_path IS NOT NULL AS has_pdf, source "
            "FROM generations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) | {"has_pdf": bool(r["has_pdf"])} for r in rows]


def get_generation(generation_id, user_id):
    with _LOCK:
        row = _CONN.execute(
            "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["cv"] = json.loads(data.pop("cv_json"))
    return data


def delete_generation(generation_id, user_id):
    with _LOCK, _CONN:
        cursor = _CONN.execute("DELETE FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id))
    return cursor.rowcount > 0


def count_generations(user_id):
    with _LOCK:
        return _CONN.execute("SELECT COUNT(*) FROM generations WHERE user_id = ?", (user_id,)).fetchone()[0]
