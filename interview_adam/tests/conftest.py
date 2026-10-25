"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Préparation de l'environnement de test : base SQLite jetable, aucune écriture dans `data/`,
aucun appel réseau (le client Ollama est remplacé partout).

`ADAM_DB_PATH` doit être posé AVANT l'import de `interview_adam.config_adam` : c'est à
l'import que le chemin de base est lu.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_TEST_DB = Path(tempfile.mkdtemp(prefix="smartcareer_test_")) / "interview_test.db"
os.environ["ADAM_DB_PATH"] = str(_TEST_DB)

# Import volontairement placé APRÈS la variable d'environnement : config_adam fige
# le chemin de base à l'import. Tout import antérieur écrirait dans la vraie base.
from interview_adam.llm_adam import AdamMistralBadJson  # noqa: E402

# Table `users` reprise de db.py (Module 1) : la clé étrangère
# interview_sessions.user_id doit pouvoir être vérifiée dans la base jetable.
USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""

USER_ID = "testuser0000000000000000000000adam"
OTHER_USER_ID = "otheruser000000000000000000000xx"


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    from interview_adam import db_adam

    conn = sqlite3.connect(_TEST_DB)
    conn.execute(USERS_TABLE)
    for user_id, name in ((USER_ID, "Adam Test"), (OTHER_USER_ID, "Autre Candidat")):
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, f"{name.lower().replace(' ', '.')}@example.invalid", "x",
             "2026-01-01T00:00:00+00:00"))
    conn.commit()
    conn.close()
    yield
    # Windows refuse de supprimer un fichier SQLite encore ouvert : on ferme d'abord.
    db_adam.reset_connection()
    _TEST_DB.unlink(missing_ok=True)
    try:
        _TEST_DB.parent.rmdir()
    except OSError:
        pass


@pytest.fixture
def user():
    return {"id": USER_ID, "name": "Adam Test", "email": "adam.test@example.invalid",
            "created_at": "2026-01-01T00:00:00+00:00"}


@pytest.fixture
def other_user():
    """Second compte : sert à vérifier qu'une session n'est jamais visible par un autre utilisateur."""
    return {"id": OTHER_USER_ID, "name": "Autre Candidat", "email": "autre@example.invalid",
            "created_at": "2026-01-01T00:00:00+00:00"}


@pytest.fixture
def db_conn():
    from interview_adam import db_adam

    return db_adam._connect()


@pytest.fixture
def clean_sessions(db_conn):
    """Chaque test repart sans session d'entretien (les lignes de test ne se gênent pas)."""
    with db_conn:
        db_conn.execute("DELETE FROM interview_qa")
        db_conn.execute("DELETE FROM interview_sessions")
    yield


class StubClient:
    """
    Client Mistral simulé : renvoie une file de réponses, compte les appels, capte les prompts.

    `raw=True` reproduit le comportement du vrai client quand Ollama renvoie du non-JSON :
    le service doit alors passer par le prompt de réparation, puis par le repli.
    """

    def __init__(self, responses, raw=False):
        self.responses = list(responses)
        self.calls = []
        self.raw = raw

    @property
    def prompts(self):
        return [call["prompt"] for call in self.calls]

    def generate_json(self, prompt, schema, temperature=0.4, max_tokens=None):
        self.calls.append({"prompt": prompt, "schema": schema, "temperature": temperature,
                           "max_tokens": max_tokens})
        if not self.responses:
            raise AssertionError("le test n'a pas prévu assez de réponses simulées")
        outcome = self.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if self.raw:
            raise AdamMistralBadJson("(sortie du modèle non JSON)")
        data = dict(outcome)
        data.setdefault("_model", "mistral:test")
        return data

    def release(self):
        return True

    def is_available(self):
        return True, "ok"


@pytest.fixture
def clean_cv(monkeypatch):
    """
    CV du Module 1 tel qu'il sort de `db.get_generation`, identité complète comprise :
    les tests vérifient que rien de personnel ne ressort du module.
    """
    import db  # module de premier niveau du dépôt (Module 1), comme dans cv_bridge

    cv = {
        "personal_info": {
            "first_name": "Nadia", "last_name": "Ben Ali", "title": "Développeuse Back-End",
            "email": "nadia.benali@example.fr", "phone": "+33 6 12 34 56 78",
            "location": "6 rue des Lilas, 75011 Paris",
            "linkedin": "https://www.linkedin.com/in/nadia-benali", "github": "",
        },
        "profile": "Développeuse back-end, contact nadia.benali@example.fr.",
        "education": [{"degree": "Master", "field": "Informatique", "institution": "ESPRIT",
                       "location": "Tunis", "start": "2022", "end": "2026"}],
        "experiences": [{"role": "Stagiaire", "company": "TechCorp", "location": "Paris",
                         "start": "2025", "end": "2025",
                         "description": "API FastAPI, voir https://techcorp.example/post"}],
        "projects": [{"name": "Pipeline", "technologies": ["Python", "PostgreSQL"],
                      "description": "ETL quotidien"}],
        "skills": [{"category": "Langages", "items": ["Python", "SQL"]}],
        "languages": [{"name": "Français", "level": "courant"}],
        "certifications": [], "interests": ["échecs"],
    }

    def fake_get_generation(generation_id, user_id):
        if generation_id == "absent":
            return None
        # Le Module 1 titre souvent le CV avec le nom du candidat : le titre est donc
        # piégé volontairement, pour vérifier qu'il ne sort jamais de la passerelle.
        return {"id": generation_id, "title": "CV Nadia Ben Ali — Développeuse Back-End", "cv": cv}

    monkeypatch.setattr(db, "get_generation", fake_get_generation)
    return cv


@pytest.fixture
def app_factory():
    """Construit une app FastAPI avec le routeur entretien, avec ou sans surcharge d'auth."""
    from fastapi import FastAPI

    from auth import current_user
    from interview_adam.router import router

    def build(caller=None):
        application = FastAPI()
        application.include_router(router)
        if caller is not None:
            application.dependency_overrides[current_user] = caller
        return application

    return build
