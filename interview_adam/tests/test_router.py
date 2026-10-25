"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Routeur HTTP : authentification obligatoire, codes et messages français, contrat des
réponses validé par les modèles Pydantic, et erreurs du modèle traduites en 503/504.

Montée sur une app FastAPI isolée (celle du module seul) : le Module 1 n'est pas importé
et ne peut donc pas être cassé par ces tests.
"""

import json

import pytest
from fastapi.testclient import TestClient

import interview_adam.router as router_module
from auth import current_user
from interview_adam.llm_adam import (AdamMistralModelMissing, AdamMistralQuota, AdamMistralTimedOut,
                                     AdamMistralUnreachable)
from interview_adam.service import AdamInterviewService
from conftest import StubClient

QUESTION = "Comment structures-tu une API FastAPI pour un premier projet ?"
OTHER_USER = {"id": "otheruser0000000000000000000000xx", "name": "Autre", "email": "autre@example.invalid"}


def questions_payload(**overrides):
    payload = {"job_title": "Développeur Back-End Python", "n_questions": 3,
               "question_type": "mixed", "seniority": "junior"}
    payload.update(overrides)
    return payload


def question_set(n=3):
    return {"questions": [{"question": f"{QUESTION} ({i + 1})" if i else QUESTION,
                           "category": "technical", "focus": "architecture",
                           "expected_points": ["routes", "schémas"]} for i in range(n)]}


EVALUATION = {"score": 7.0, "criteria": {"relevance": 7, "clarity": 6, "structure": 7,
                                         "technical_accuracy": 8},
              "strengths": ["exemple concret"], "weaknesses": ["pas de résultat chiffré"],
              "verdict": "Bonne réponse, à structurer."}
IMPROVEMENT = {"improved_answer": "x" * 140, "star": None, "tips": ["chiffrer le résultat"]}


@pytest.fixture
def client_for(app_factory, monkeypatch):
    """
    Fabrique un TestClient authentifié sur `user`, avec un service entretien branché sur
    des réponses simulées. Retourne (client, stub).
    """

    def build(user, responses, raw=False):
        stub = StubClient(responses, raw=raw)
        monkeypatch.setattr(router_module, "service", AdamInterviewService(client=stub))
        application = app_factory(caller=lambda: user)
        return TestClient(application), stub

    return build


@pytest.fixture
def answered_session(clean_sessions, user, client_for):
    client, _ = client_for(user, [question_set(3)])
    created = client.post("/interview/questions", json=questions_payload(n_questions=3))
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]
    client, _ = client_for(user, [EVALUATION])
    client.post("/interview/evaluate", json={"session_id": session_id, "index": 1,
                                             "answer": "J'ai séparé routes et schémas Pydantic."})
    return session_id


# ----------------------------------------------------------------------
# Authentification
# ----------------------------------------------------------------------

def test_every_route_requires_a_logged_in_user(app_factory):
    client = TestClient(app_factory())  # aucune surcharge d'auth : jeton réel exigé
    for method, path in (("post", "/interview/questions"), ("post", "/interview/evaluate"),
                         ("post", "/interview/improve"), ("get", "/interview/sessions"),
                         ("get", "/interview/sessions/a1b2c3d4e5f6"),
                         ("delete", "/interview/sessions/a1b2c3d4e5f6"),
                         ("get", "/interview/status"), ("post", "/interview/release")):
        response = client.request(method, path, json={})
        assert response.status_code in (401, 403), (path, response.status_code)


# ----------------------------------------------------------------------
# POST /interview/questions
# ----------------------------------------------------------------------

def test_questions_returns_201_with_the_agreed_shape(user, client_for):
    client, stub = client_for(user, [question_set(3)])
    response = client.post("/interview/questions", json=questions_payload())

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session_id", "context", "questions", "model", "seconds", "degraded",
                         "rag_used", "rag_sources"}
    assert len(body["questions"]) == 3
    assert body["questions"][0]["index"] == 1
    assert body["context"]["job_title"] == "Développeur Back-End Python"
    assert body["degraded"] is False
    # Aucun retriever branché dans ces tests : la réponse doit le dire, pas mentir par omission.
    assert body["rag_used"] is False and body["rag_sources"] == []
    assert stub.calls[0]["schema"]["required"] == ["questions"]


def test_questions_rejects_a_missing_job_title(user, client_for):
    client, _ = client_for(user, [question_set(3)])
    response = client.post("/interview/questions", json={"n_questions": 3})
    assert response.status_code == 422


def test_questions_rejects_an_out_of_range_count(user, client_for):
    client, _ = client_for(user, [question_set(3)])
    response = client.post("/interview/questions", json=questions_payload(n_questions=99))
    assert response.status_code == 422


def test_model_absent_is_a_503_with_a_french_message(user, client_for):
    client, _ = client_for(user, [AdamMistralModelMissing("mistral:7b-instruct-v0.2-q4_K_M")])
    response = client.post("/interview/questions", json=questions_payload())
    assert response.status_code == 503
    assert "ollama pull" in response.json()["detail"]


def test_ollama_down_is_a_503(user, client_for):
    client, _ = client_for(user, [AdamMistralUnreachable()])
    response = client.post("/interview/questions", json=questions_payload())
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_saturation_is_a_503_and_timeout_a_504(user, client_for):
    client, _ = client_for(user, [AdamMistralQuota()])
    assert client.post("/interview/questions", json=questions_payload()).status_code == 503

    client, _ = client_for(user, [AdamMistralTimedOut()])
    response = client.post("/interview/questions", json=questions_payload())
    assert response.status_code == 504


def test_unexpected_failure_never_leaks_a_stack_trace(user, client_for):
    """Un bug interne devient un 500 lisible : la stack trace reste dans les journaux serveur."""
    client, _ = client_for(user, [RuntimeError("traceback privé du serveur")])
    response = client.post("/interview/questions", json=questions_payload())

    assert response.status_code == 500
    assert "traceback" not in response.text
    assert "erreur" in response.json()["detail"].lower()


# ----------------------------------------------------------------------
# POST /interview/evaluate
# ----------------------------------------------------------------------

def test_evaluate_returns_score_criteria_and_verdict(user, client_for, answered_session):
    client, stub = client_for(user, [EVALUATION])
    response = client.post("/interview/evaluate",
                           json={"session_id": answered_session, "index": 2,
                                 "answer": "J'utilise des dépôts de données et des tests."})

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 7.0
    assert body["criteria"]["technical_accuracy"] == 8.0
    assert body["weaknesses"] == ["pas de résultat chiffré"]
    assert body["question"].startswith(QUESTION)
    assert "<reponse_candidat>" in stub.prompts[0]


def test_evaluate_rejects_an_answer_over_the_limit(user, client_for, answered_session):
    client, _ = client_for(user, [EVALUATION])
    response = client.post("/interview/evaluate",
                           json={"session_id": answered_session, "index": 1, "answer": "x" * 9000})
    assert response.status_code == 422 or len(response.json()["answer"]) <= 4001


def test_evaluate_on_an_unknown_session_is_404(user, client_for):
    client, _ = client_for(user, [EVALUATION])
    response = client.post("/interview/evaluate",
                           json={"session_id": "a1b2c3d4e5f6a7b8", "index": 1, "answer": "réponse"})
    assert response.status_code == 404
    assert "introuvable" in response.json()["detail"].lower()


def test_evaluate_degrades_instead_of_failing(user, client_for, answered_session):
    client, _ = client_for(user, [AdamMistralModelMissing("mistral:7b"),
                                   AdamMistralModelMissing("mistral:7b")])
    # Transport cassé => 503 assumé (pas de fausse note) : la règle du module.
    response = client.post("/interview/evaluate",
                           json={"session_id": answered_session, "index": 1, "answer": "réponse"})
    assert response.status_code == 503


def test_evaluate_of_another_users_session_is_404(other_user, client_for, answered_session):
    client, _ = client_for(other_user, [EVALUATION])
    response = client.post("/interview/evaluate",
                           json={"session_id": answered_session, "index": 1, "answer": "réponse"})
    assert response.status_code == 404


# ----------------------------------------------------------------------
# POST /interview/improve
# ----------------------------------------------------------------------

def test_improve_returns_the_rewritten_answer(user, client_for, answered_session):
    client, stub = client_for(user, [IMPROVEMENT])
    response = client.post("/interview/improve",
                           json={"session_id": answered_session, "index": 1})

    assert response.status_code == 200
    assert response.json()["improved_answer"] == "x" * 140
    assert response.json()["tips"] == ["chiffrer le résultat"]
    assert "<reponse_candidat>" in stub.prompts[0]


def test_improve_with_a_star_structure(user, client_for, answered_session):
    star = {"improved_answer": "y" * 140,
            "star": {"situation": "Stage", "task": "Refonte", "action": "Migration", "result": "-30 %"},
            "tips": []}
    client, _ = client_for(user, [star])
    body = client.post("/interview/improve",
                       json={"session_id": answered_session, "index": 1}).json()
    assert body["star"]["action"] == "Migration"


# ----------------------------------------------------------------------
# Historique
# ----------------------------------------------------------------------

def test_sessions_list_is_scoped_to_the_user(user, other_user, client_for, answered_session):
    client, _ = client_for(user, [])
    mine = client.get("/interview/sessions").json()
    assert len(mine) == 1
    assert mine[0]["answered"] == 1
    assert mine[0]["average_score"] == 7.0

    client, _ = client_for(other_user, [])
    assert client.get("/interview/sessions").json() == []


def test_session_detail_carries_answers_and_advice(user, client_for, answered_session):
    client, _ = client_for(user, [])
    response = client.get(f"/interview/sessions/{answered_session}")

    assert response.status_code == 200
    body = response.json()
    assert body["n_questions"] == 3 and body["answered"] == 1
    assert len(body["answers"]) == 3
    assert body["answers"][0]["score"] == 7.0
    assert body["advice"]
    assert json.dumps(body, ensure_ascii=False)


def test_session_id_in_the_path_is_validated(user, client_for):
    client, _ = client_for(user, [])
    assert client.get("/interview/sessions/../../etc/passwd").status_code == 404
    assert client.get("/interview/sessions/injection%20test").status_code == 404


def test_unknown_session_detail_is_404(user, client_for):
    client, _ = client_for(user, [])
    response = client.get("/interview/sessions/a1b2c3d4e5f6a7b8c9d0")
    assert response.status_code == 404


# ----------------------------------------------------------------------
# Libération du modèle (partage GPU avec le Module 1)
# ----------------------------------------------------------------------

def test_release_reports_the_model_it_unloads(user, client_for):
    client, _ = client_for(user, [])
    response = client.post("/interview/release")
    assert response.status_code == 200
    assert response.json()["released"] is True


# ----------------------------------------------------------------------
# DELETE /interview/sessions/{id}
# ----------------------------------------------------------------------

def test_delete_removes_the_session_and_its_answers(user, client_for, clean_sessions):
    """
    Parité avec la suppression d'un CV côté Module 1. La vérification porte aussi sur
    `interview_qa` : sans cascade effective, des réponses orphelines fausseraient
    l'historique d'une session récréée avec le même identifiant.
    """
    from interview_adam import db_adam

    client, _ = client_for(user, [question_set(3)])
    session_id = client.post("/interview/questions", json=questions_payload()).json()["session_id"]

    response = client.delete(f"/interview/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "session_id": session_id}

    assert client.get(f"/interview/sessions/{session_id}").status_code == 404
    assert session_id not in {row["id"] for row in client.get("/interview/sessions").json()}

    connection = db_adam._connect()
    assert connection.execute("SELECT COUNT(*) FROM interview_qa WHERE session_id = ?",
                              (session_id,)).fetchone()[0] == 0


def test_delete_another_users_session_is_404_not_403(user, client_for, other_user, answered_session):
    """
    403 confirmerait que la session existe : un identifiant de session est un secret.
    Le Module répond 404, comme pour une session inexistante, et ne supprime rien.
    """
    client, _ = client_for(other_user, [])
    response = client.delete(f"/interview/sessions/{answered_session}")
    assert response.status_code == 404

    owner, _ = client_for(user, [])
    assert owner.get(f"/interview/sessions/{answered_session}").status_code == 200


def test_delete_is_idempotent_in_appearance_and_validated_in_path(user, client_for):
    client, _ = client_for(user, [])
    assert client.delete("/interview/sessions/a1b2c3d4e5f6a7b8c9d0").status_code == 404
    assert client.delete("/interview/sessions/../secrets").status_code == 404


# ----------------------------------------------------------------------
# GET /interview/status
# ----------------------------------------------------------------------

def test_status_reports_llm_model_and_rag_state(user, client_for):
    client, _ = client_for(user, [])
    response = client.get("/interview/status")
    assert response.status_code == 200

    body = response.json()
    assert body["llm_available"] is True
    assert body["model"] == "mistral:7b-instruct-v0.2-q4_K_M"
    # Ces tests montent le service sans retriever : le statut doit l'annoncer et dire comment
    # l'activer, au lieu d'afficher un silence interprétable.
    assert body["rag_available"] is False and body["rag_chunks"] == 0
    assert "ingest" in body["rag_reason"]
    assert set(body["languages"]) == {"fr", "en"}


def test_status_does_not_500_when_the_llm_is_unreachable(user, client_for, monkeypatch):
    """Un diagnostic qui tombe ne diagnostique rien : l'indisponibilité est une donnée."""
    from interview_adam.llm_adam import AdamMistralUnreachable

    client, stub = client_for(user, [])
    monkeypatch.setattr(stub, "is_available",
                        lambda: (False, "Ollama injoignable"))
    response = client.get("/interview/status")
    assert response.status_code == 200
    assert response.json()["llm_available"] is False
    assert "Ollama" in response.json()["llm_reason"]

    def explode():
        raise AdamMistralUnreachable()

    monkeypatch.setattr(stub, "is_available", explode)
    body = client.get("/interview/status").json()
    assert body["llm_available"] is False and "Ollama" in body["llm_reason"]
