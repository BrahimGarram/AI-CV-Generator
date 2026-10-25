"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Routeur FastAPI du simulateur d'entretien.

Convention du dépôt reprise : pas de préfixe `/api` (le Module 1 expose /auth, /sessions,
/history directement). Sous-préfixe `/interview`, aucun conflit avec les routes existantes.

Montage dans `app/api.py` (deux lignes, rien d'autre) :
    from interview_adam.router import router as interview_router
    app.include_router(interview_router)

Toutes les routes exigent la dépendance d'authentification existante (`auth.current_user`).
Chaque erreur est convertie en `HTTPException` avec un message français dans `detail`,
comme le fait déjà le Module 1 (503 quand le LLM est indisponible).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from auth import current_user

from interview_adam import config_adam as cfg
from interview_adam.llm_adam import AdamMistralError
from interview_adam.privacy import PrivacyError
from interview_adam.rag.retriever import AdamRetriever
from interview_adam.schemas_adam import (EvaluateIn, EvaluationOut, ImproveIn, ImprovementOut,
                                        InterviewStatusOut, QuestionsIn, QuestionsOut,
                                        SessionDetailOut, SessionSummaryOut)
from interview_adam.service import AdamInterviewService, InterviewError

logger = logging.getLogger("smartcareer.interview")

router = APIRouter(prefix="/interview", tags=["entretien"])


def _retriever_or_none():
    """
    Charge l'index vectoriel s'il a été ingéré, sinon rend None : le service tourne alors
    exactement comme avant le RAG. Import et construction sont légers — ni torch ni faiss
    ne sont importés ici, seulement au premier `embed()`.
    """
    try:
        return AdamRetriever.build()
    except Exception as error:  # noqa: BLE001 - un RAG cassé ne doit pas empêcher l'API de démarrer
        logger.warning("RAG désactivé au démarrage : %s", error)
        return None


# Service partagé : le routeur n'apporte aucun état par utilisateur, les sessions sont en base.
service = AdamInterviewService(retriever=_retriever_or_none())


def _fail(error):
    """Traduit une erreur interne en réponse HTTP lisible ; ne laisse jamais tomber un 500 nu."""
    if isinstance(error, InterviewError):
        raise HTTPException(error.http_status, error.message) from error
    if isinstance(error, AdamMistralError):
        logger.warning("Mistral indisponible : %s", error)
        raise HTTPException(error.http_status, error.message) from error
    if isinstance(error, PrivacyError):
        # Un contenu personnel a survécu au nettoyage : bug du module, on n'envoie rien.
        logger.error("Contrôle de confidentialité déclenché : %s", error)
        raise HTTPException(503, "Le simulateur refuse d'envoyer certaines informations au modèle. "
                                 "Réessaie en simplifiant le texte saisi.") from error
    logger.exception("Erreur inattendue dans le module entretien", exc_info=error)
    raise HTTPException(500, "Une erreur est survenue pendant l'entretien. Réessaie dans un instant.") from error


@router.post("/questions", response_model=QuestionsOut, status_code=201,
             summary="Génère les questions adaptées au poste")
def questions(body: QuestionsIn, user=Depends(current_user)):
    try:
        return service.generate_questions(user, body)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 - une route doit toujours répondre en HTTP
        _fail(error)


@router.post("/evaluate", response_model=EvaluationOut,
             summary="Note une réponse (0-10) avec forces, faiblesses et critères")
def evaluate(body: EvaluateIn, user=Depends(current_user)):
    try:
        return service.evaluate_answer(user, body)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        _fail(error)


@router.post("/improve", response_model=ImprovementOut,
             summary="Propose une réponse améliorée (STAR si comportemental)")
def improve(body: ImproveIn, user=Depends(current_user)):
    try:
        return service.improve_answer(user, body)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        _fail(error)


@router.get("/sessions", response_model=list[SessionSummaryOut],
            summary="Historique des sessions de l'utilisateur")
def sessions(user=Depends(current_user)):
    return service.list_sessions(user)


def _known_id(session_id):
    """
    Un identifiant de session est un hexadécimal de 32 caractères. On rejette d'abord tout
    ce qui ne ressemble pas à un identifiant : `../../etc/passwd` ou une chaîne de 5000
    caractères doivent faire un 404 propre, pas une requête SQL ni un 500.
    """
    if not session_id.isalnum() or len(session_id) > 64:
        raise HTTPException(404, "Session d'entretien introuvable.")


@router.get("/sessions/{session_id}", response_model=SessionDetailOut,
            summary="Détail et synthèse d'une session")
def session_detail(session_id: str, user=Depends(current_user)):
    _known_id(session_id)
    try:
        return service.session_detail(user, session_id)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        _fail(error)


@router.delete("/sessions/{session_id}", summary="Supprime une session et ses réponses")
def delete_session(session_id: str, user=Depends(current_user)):
    """
    Parité avec la suppression d'un CV côté Module 1. Suppression bornée à l'utilisateur :
    un identifiant appartenant à un autre compte répond 404, jamais 200 ni 403 qui
    confirmerait qu'une session existe.
    """
    _known_id(session_id)
    try:
        deleted = service.delete_session(user, session_id)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        _fail(error)
        return {"deleted": False, "session_id": session_id}
    if not deleted:
        raise HTTPException(404, "Session d'entretien introuvable.")
    return {"deleted": True, "session_id": session_id}


@router.get("/status", response_model=InterviewStatusOut,
            summary="État du modèle et de l'index RAG (bandeau d'interface)")
def status(user=Depends(current_user)):
    """
    Avant de lancer un entretien, l'interface demande si Mistral répond et si la base
    documentaire est chargée. Le module fonctionne dans les quatre combinaisons possibles :
    cette route n'est pas un prérequis, c'est un indicateur.
    """
    return service.status()


@router.post("/release", summary="Libère la VRAM occupée par Mistral (fin de page)")
def release(user=Depends(current_user)):
    """
    Le Module 1 décharge son propre modèle Ollama avant de générer un CV, mais pas le nôtre :
    cet appel permet à l'interface de rendre la carte graphique immédiatement en partant sur
    l'éditeur de CV. Échec toléré : keep_alive finit de toute façon par décharger le modèle.

    La route exige `current_user` : sans jeton Bearer valide elle répond 401 et n'atteint
    jamais Ollama. La trace ci-dessous prouve côté serveur qu'une libération authentifiée est
    bien arrivée (id utilisateur + résultat), utile pour la démo et le rapport.
    """
    released = service.release_model()
    logger.info("VRAM Mistral libérée pour user=%s (released=%s, model=%s)", user["id"], released, cfg.MISTRAL_MODEL)
    return {"released": released, "model": cfg.MISTRAL_MODEL}
