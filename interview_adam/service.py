"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Orchestration du simulateur : contexte, prompts, appel Mistral, validation Pydantic,
réparation en une tentative, repli convivial, persistance SQLite.

Règle d'erreur : les pannes de transport (Ollama injoignable, modèle absent, timeout, quota)
traversent le service et deviennent des 503/504 dans le routeur. Seules les sorties
inexploitables (JSON non conforme) déclenchent réparation puis repli `degraded=True`.
"""

import json
import logging
import time
from datetime import datetime, timezone

from pydantic import ValidationError

from interview_adam import cv_bridge, db_adam, fallbacks
from interview_adam import config_adam as cfg
from interview_adam.llm_adam import AdamMistralBadJson, AdamMistralError, client as default_client
from interview_adam.privacy import scrub_text
from interview_adam.prompts import adam_evaluate, adam_improve, adam_questions, repair
from interview_adam.schemas_adam import (EVALUATION_SCHEMA, IMPROVEMENT_SCHEMA, QUESTION_SET_SCHEMA,
                                         AdamEvaluation, AdamImprovement, AdamQuestionSet)

logger = logging.getLogger("smartcareer.interview")


class InterviewError(RuntimeError):
    """Erreur affichable : `http_status` est le code à renvoyer à l'interface."""

    def __init__(self, message, http_status=503):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


class InterviewNotFound(InterviewError):
    def __init__(self, message="Session d'entretien introuvable. Lance une nouvelle session."):
        super().__init__(message, http_status=404)


class InterviewInputError(InterviewError):
    def __init__(self, message):
        super().__init__(message, http_status=422)


class AdamInterviewService:
    """
    `client` : injectable, pour les tests sans réseau.
    `retriever` : objet portant `retrieve(kind, query, limit) -> (contexte, sources)`,
    fourni par `interview_adam.rag.AdamRetriever` (phase 2b). Absent, les prompts tournent
    sans documentation de référence : le module reste fonctionnel, `rag_used` vaut false.
    """

    def __init__(self, client=None, retriever=None):
        self.client = client or default_client
        self.retriever = retriever

    # ------------------------------------------------------------------
    # Appel modèle -> validation -> réparation -> repli
    # ------------------------------------------------------------------

    def _run(self, prompt, schema, model_cls, temperature, fallback_factory, max_tokens=None):
        """
        Retourne `(données, meta)` : `données` = dict validé ou repli,
        `meta` = {"model", "seconds", "degraded", "reason"}.
        `max_tokens` : budget num_predict de l'étape (voir les caps par étape dans config_adam).
        """
        start = time.time()
        attempt = self._first_attempt(prompt, schema, model_cls, temperature, max_tokens)

        if isinstance(attempt, _TransportFailure):
            raise attempt.error

        if isinstance(attempt, _InvalidOutput):
            repaired = self._repair_attempt(prompt, schema, model_cls, attempt, max_tokens)
            if isinstance(repaired, _ValidOutput):
                attempt = repaired
            elif isinstance(repaired, _TransportFailure):
                raise repaired.error
            else:
                data = fallback_factory()
                data["_meta"] = {"model": None, "seconds": round(time.time() - start, 1),
                                 "degraded": True,
                                 "reason": f"{repaired.reason} | {attempt.reason}"[:200]}
                return data

        data = dict(attempt.data)
        data["_meta"] = {"model": attempt.model or cfg.MISTRAL_MODEL,
                         "seconds": round(time.time() - start, 1),
                         "degraded": False, "reason": ""}
        return data

    def _first_attempt(self, prompt, schema, model_cls, temperature, max_tokens=None):
        try:
            raw = self.client.generate_json(prompt, schema, temperature=temperature,
                                            max_tokens=max_tokens)
        except AdamMistralBadJson as invalid:
            return _InvalidOutput(reason=str(invalid), raw_text="")
        except AdamMistralError as error:
            return _TransportFailure(error)
        return self._validate(raw, model_cls)

    def _repair_attempt(self, original_prompt, schema, model_cls, failure, max_tokens=None):
        """Seconde chance : on montre au modèle ce qu'il a produit et le motif de rejet."""
        repair_prompt = repair.build(original_prompt, failure.raw_text, failure.reason, schema)
        try:
            raw = self.client.generate_json(repair_prompt, schema, temperature=0.1,
                                            max_tokens=max_tokens)
        except AdamMistralBadJson as invalid:
            return _InvalidOutput(reason=str(invalid), raw_text="")
        except AdamMistralError as error:
            return _TransportFailure(error)
        result = self._validate(raw, model_cls)
        if isinstance(result, _InvalidOutput):
            # La réparation a produit du JSON mais toujours hors contrat : on garde la sortie
            # la plus récente comme référence pour le message de repli.
            result.raw_text = raw and json.dumps(raw, ensure_ascii=False)[:1600] or ""
        return result

    @staticmethod
    def _validate(raw, model_cls):
        model = raw.get("_model") if isinstance(raw, dict) else None
        try:
            return _ValidOutput(data=model_cls.model_validate(raw).model_dump(), model=model)
        except ValidationError as invalid:
            return _InvalidOutput(reason=_reason(invalid),
                                  raw_text=json.dumps(raw, ensure_ascii=False, default=str)[:1600])

    # ------------------------------------------------------------------
    # Fonctionnalité 1 — questions adaptées au poste
    # ------------------------------------------------------------------

    def generate_questions(self, user, body):
        user_id = user["id"]
        job_description = scrub_text(body.job_description or "")
        company = scrub_text(body.company or "")
        cv_digest_text = None
        cv_generation_id = None
        gaps = {}

        if body.use_cv:
            if not body.cv_generation_id:
                raise InterviewInputError("Choisis d'abord le CV à utiliser pour personnaliser l'entretien.")
            bundle = cv_bridge.get_cv_bundle(user_id, body.cv_generation_id)
            if bundle is None:
                raise InterviewNotFound("Ce CV est introuvable dans ton espace. Choisis-en un autre.")
            cv_digest_text = bundle["digest"]
            cv_generation_id = bundle["generation_id"]
            # Le titre du CV n'est PAS l'employeur : c'est un nom de document que l'utilisateur
            # peut avoir intitulé avec son propre nom. Ne jamais le faire passer dans `company`,
            # il atterrirait dans le prompt et dans l'interface. L'entreprise vient de l'offre.

        # Point de branchement Module 1 : aucune offre stockée aujourd'hui -> saisie manuelle.
        if not job_description:
            offer = cv_bridge.get_job_offer_context(user_id, cv_generation_id)
            if offer:
                job_description = scrub_text(offer.get("description") or "")
                company = company or scrub_text(offer.get("company") or "")

        if cv_generation_id:
            gaps = cv_bridge.skill_gaps(job_description, cv_digest_text or "")

        query = " ".join(x for x in (body.job_title, job_description[:600],
                                     ", ".join(gaps.get("covered") or [])) if x)
        rag_context, rag_sources = self._retrieve("questions", query)
        prompt = adam_questions.build(
            job_title=body.job_title, seniority=body.seniority, question_type=body.question_type,
            n_questions=body.n_questions, language=body.language, company=company or None,
            job_description=job_description or None, cv_digest_text=cv_digest_text,
            gaps=gaps, rag_context=rag_context)

        result = self._run(prompt, QUESTION_SET_SCHEMA, AdamQuestionSet, 0.6,
                           lambda: {"questions": fallbacks.generic_questions(
                               body.question_type, body.n_questions, body.language)},
                           max_tokens=min(cfg.MAX_NEW_TOKENS,
                                          cfg.QUESTIONS_BASE_TOKENS
                                          + cfg.QUESTIONS_TOKENS_PER_QUESTION * body.n_questions))
        meta = result.pop("_meta")
        questions = _normalize_questions(result.get("questions") or [], body.n_questions, body.language)

        session_id = db_adam.create_session(
            user_id=user_id, job_title=body.job_title, company=company or None,
            job_description=job_description or None, seniority=body.seniority,
            question_type=body.question_type, language=body.language, n_questions=len(questions),
            model=meta["model"] if not meta["degraded"] else None, cv_generation_id=cv_generation_id)
        db_adam.attach_questions(session_id, questions)

        return {
            "session_id": session_id,
            "context": {"job_title": body.job_title, "company": company or None,
                        "seniority": body.seniority, "question_type": body.question_type,
                        "language": body.language, "cv_used": bool(cv_generation_id)},
            "questions": questions,
            "model": meta["model"],
            "seconds": meta["seconds"],
            "degraded": meta["degraded"] or any(q["degraded"] for q in questions),
            "rag_used": bool(rag_sources),
            "rag_sources": rag_sources,
        }

    # ------------------------------------------------------------------
    # Fonctionnalité 2 — analyse d'une réponse
    # ------------------------------------------------------------------

    def evaluate_answer(self, user, body):
        session = self._owned_session(body.session_id, user["id"])
        qa = _find_qa(session, body.index)
        answer = scrub_text(body.answer)

        query = " ".join(x for x in (session["job_title"], qa["question"], qa["category"]) if x)
        rag_context, rag_sources = self._retrieve("evaluate", query)
        prompt = adam_evaluate.build(
            question=qa["question"], category=qa["category"],
            expected_points=qa.get("expected_points") or [], answer=answer,
            language=session["language"], job_title=session["job_title"],
            seniority=session["seniority"], rubric_context=rag_context)

        result = self._run(prompt, EVALUATION_SCHEMA, AdamEvaluation, 0.2,
                           lambda: fallbacks.evaluate_heuristic(answer, session["language"]),
                           max_tokens=cfg.EVALUATE_MAX_TOKENS)
        meta = result.pop("_meta")
        evaluation = {"score": result.get("score"), "criteria": result.get("criteria") or {},
                      "strengths": result.get("strengths") or [],
                      "weaknesses": result.get("weaknesses") or [],
                      "verdict": result.get("verdict") or ""}
        db_adam.save_evaluation(session["id"], body.index, answer, evaluation)

        # La session se clôture seule quand toutes les questions ont une réponse : la synthèse
        # est alors figée en base et l'historique affiche un entretien terminé.
        updated = db_adam.get_session(session["id"], user["id"])
        if updated and updated["n_questions"] and \
                sum(1 for item in updated["answers"] if item.get("answer")) >= updated["n_questions"]:
            db_adam.finish_session(session["id"], user["id"], summarize(updated))
            session = updated

        return {"session_id": session["id"], "index": body.index, "question": qa["question"],
                "answer": answer, "model": meta["model"], "seconds": meta["seconds"],
                "degraded": meta["degraded"], "rag_used": bool(rag_sources),
                "rag_sources": rag_sources, **evaluation}

    # ------------------------------------------------------------------
    # Fonctionnalité 3 — réponse améliorée (STAR)
    # ------------------------------------------------------------------

    def improve_answer(self, user, body):
        session = self._owned_session(body.session_id, user["id"])
        qa = _find_qa(session, body.index)
        answer = qa.get("answer") or ""

        cv_digest_text = None
        if session.get("cv_generation_id"):
            bundle = cv_bridge.get_cv_bundle(user["id"], session["cv_generation_id"])
            cv_digest_text = bundle["digest"] if bundle else None

        rag_context, rag_sources = self._retrieve(
            "improve", " ".join(x for x in (session["job_title"], qa["question"], qa["category"]) if x))
        prompt = adam_improve.build(
            question=qa["question"], category=qa["category"], answer=answer,
            language=session["language"],
            evaluation={"score": qa.get("score"), "criteria": qa.get("criteria") or {},
                        "weaknesses": qa.get("weaknesses") or []},
            cv_digest_text=cv_digest_text, job_title=session["job_title"],
            seniority=session["seniority"],
            technique_notes=rag_context)

        result = self._run(prompt, IMPROVEMENT_SCHEMA, AdamImprovement, 0.4,
                           lambda: fallbacks.improve_fallback(qa["question"], answer, session["language"]),
                           max_tokens=cfg.IMPROVE_MAX_TOKENS)
        meta = result.pop("_meta")
        improvement = {"improved_answer": result.get("improved_answer") or "",
                       "star": result.get("star"), "tips": result.get("tips") or []}
        db_adam.save_improvement(session["id"], body.index, improvement)

        return {"session_id": session["id"], "index": body.index, "model": meta["model"],
                "seconds": meta["seconds"], "degraded": meta["degraded"],
                "rag_used": bool(rag_sources), "rag_sources": rag_sources, **improvement}

    # ------------------------------------------------------------------
    # Fonctionnalité 4 — historique et synthèse
    # ------------------------------------------------------------------

    def list_sessions(self, user):
        return [summarize(row) for row in db_adam.list_sessions(user["id"])]

    def session_detail(self, user, session_id):
        session = self._owned_session(session_id, user["id"])
        detail = summarize(session)
        detail.update({"cv_used": bool(session.get("cv_generation_id")),
                       "model": session.get("model"),
                       "answers": session.get("answers") or [],
                       "advice": build_advice(session.get("answers") or [], session["language"])})
        return detail

    def delete_session(self, user, session_id):
        """
        Suppression bornée à l'utilisateur. `interview_qa` suit par ON DELETE CASCADE :
        il n'y a pas de second DELETE à faire. On vérifie la propriété avant d'écrire,
        pour qu'un faux identifiant ne supprime jamais la session d'un autre utilisateur.
        """
        self._owned_session(session_id, user["id"])
        return db_adam.delete_session(session_id, user["id"])

    # ------------------------------------------------------------------
    # Diagnostic
    # ------------------------------------------------------------------

    def status(self):
        """
        État des trois dépendances du module, pour l'interface (bandeau « modèle indisponible »)
        et pour la démonstration : Mistral joignable, nom du modèle, index RAG chargé ou non.
        Aucun appel ne lève ici : un status qui échoue n'aide personne.
        """
        try:
            llm_available, llm_reason = self.client.is_available()
        except Exception as error:  # noqa: BLE001 - le client lui-même ne doit pas casser la route
            llm_available, llm_reason = False, f"client Mistral : {error}"

        if self.retriever is None:
            rag_available, rag_reason = False, ("index RAG absent : lance "
                                                "python -m interview_adam.rag.ingest")
            rag_chunks, rag_model = 0, None
        else:
            rag_available, rag_reason = self.retriever.available()
            store = self.retriever.store
            rag_chunks = store.size if store is not None else 0
            rag_model = self.retriever.model_name

        return {
            "llm_available": bool(llm_available),
            "llm_reason": str(llm_reason),
            "model": cfg.MISTRAL_MODEL,
            "rag_available": bool(rag_available),
            "rag_reason": str(rag_reason),
            "rag_chunks": rag_chunks,
            "rag_model": rag_model,
            "languages": list(cfg.LANGUAGES),
            "question_types": list(cfg.QUESTION_TYPES),
        }

    def release_model(self):
        """Libère la VRAM occupée par Mistral (voir la note GPU dans llm_adam.py)."""
        return self.client.release()

    def _owned_session(self, session_id, user_id):
        session = db_adam.get_session(session_id, user_id)
        if session is None:
            raise InterviewNotFound()
        return session

    def _retrieve(self, kind, query):
        """
        Documents de référence pour le prompt, en `(contexte, sources)`.

        Le retriever est facultatif et peut être défaillant (index non ingéré, modèle
        d'embeddings absent, faiss manquant) : dans tous les cas on rend un contexte vide
        et l'entretien a lieu, exactement comme en 2a. Les sources rendues accompagnent la
        réponse HTTP pour que l'interface affiche « sur quels documents j'ai été noté ».
        """
        if self.retriever is None:
            return "", []
        try:
            context, sources = self.retriever.retrieve(kind, query, limit=cfg.MAX_RAG_CONTEXT_CHARS)
        except Exception as error:  # noqa: BLE001 - la base documentaire ne doit jamais casser une session
            logger.warning("RAG indisponible pour %s : %s", kind, error)
            return "", []
        return (context or "")[:cfg.MAX_RAG_CONTEXT_CHARS], list(sources or [])


# ----------------------------------------------------------------------
# Résultat d'une tentative d'appel au modèle
# ----------------------------------------------------------------------

class _ValidOutput:
    def __init__(self, data, model):
        self.data = data
        self.model = model


class _InvalidOutput:
    def __init__(self, reason, raw_text=""):
        self.reason = reason
        self.raw_text = raw_text


class _TransportFailure:
    def __init__(self, error):
        self.error = error


# ----------------------------------------------------------------------
# Aides
# ----------------------------------------------------------------------

def _reason(validation_error):
    errors = validation_error.errors()
    return "; ".join(f"{e.get('loc', ['?'])[0]}: {e.get('msg')}" for e in errors[:6]) or "sortie non conforme"


def _find_qa(session, index):
    for item in session.get("answers") or []:
        if item.get("idx") == index:
            return item
    raise InterviewNotFound("Cette question n'existe pas dans cette session.")


def _normalize_questions(raw, expected, language):
    """Indexe, nettoie et complète à défaut le nombre de questions demandé (jamais plus)."""
    cleaned = []
    for item in raw:
        if isinstance(item, dict) and item.get("question"):
            cleaned.append({
                "index": len(cleaned) + 1,
                "question": scrub_text(item["question"])[:cfg.MAX_QUESTION_CHARS],
                "category": item.get("category") or "technical",
                "focus": scrub_text(item.get("focus") or ""),
                "expected_points": [scrub_text(p) for p in (item.get("expected_points") or [])[:6]],
                "degraded": bool(item.get("degraded")),
            })

    if len(cleaned) < expected:
        for item in fallbacks.generic_questions("mixed", expected - len(cleaned), language):
            cleaned.append({"index": len(cleaned) + 1, "question": item["question"],
                            "category": item["category"], "focus": "",
                            "expected_points": [], "degraded": True})

    return cleaned[:expected]


def summarize(session_row):
    """
    Moyenne, meilleure et moins bonne réponse.
    Deux formes d'entrée : la ligne d'historique (moyenne déjà calculée en SQL, sans les
    questions) et le détail de session (moyenne recalculée à partir des réponses).
    """
    answers = session_row.get("answers")
    if answers is None:
        answered = session_row.get("answered", 0)
        average = session_row.get("average_score")
        best = session_row.get("best_index")
        weakest = session_row.get("weakest_index")
    else:
        answered = sum(1 for item in answers if item.get("answer"))
        scored = [(item["idx"], item["score"]) for item in answers
                  if item.get("answer") and item.get("score") is not None]
        average = round(sum(score for _, score in scored) / len(scored), 1) if scored else None
        best = max(scored, key=lambda item: item[1])[0] if scored else None
        weakest = min(scored, key=lambda item: item[1])[0] if scored else None

    summary = session_row.get("summary")
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except ValueError:
            summary = None

    return {"id": session_row["id"], "job_title": session_row["job_title"],
            "company": session_row.get("company"), "seniority": session_row.get("seniority"),
            "question_type": session_row.get("question_type"), "language": session_row.get("language"),
            "status": session_row.get("status", "in_progress"),
            "n_questions": session_row.get("n_questions", len(answers or [])),
            "answered": answered, "average_score": average, "best_index": best,
            "weakest_index": weakest, "created_at": session_row.get("created_at")
            or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "finished_at": session_row.get("finished_at"), "saved_summary": summary}


def build_advice(answers, language):
    """
    Conseils de clôture déterministes, déduits des faiblesses déjà remontées par le modèle.
    Aucun nouveau contenu généré : la synthèse finale reste explicable.
    """
    answered = [item for item in answers if item.get("answer")]
    if not answered:
        return (["Aucune réponse enregistrée : lance une session pour obtenir un compte rendu."]
                if language != "en" else ["No answer recorded: run a session to get a report."])

    categories = {}
    for item in answered:
        if item.get("weaknesses"):
            categories.setdefault(item.get("category") or "hr", []).extend(item["weaknesses"])

    low = [item["idx"] for item in answered if (item.get("score") or 0) < 6]
    has_improvement = any(item.get("improvement") for item in answered)

    if language == "en":
        advice = []
        if "technical" in categories:
            advice.append("Technical answers: justify each choice (why this technology, not another).")
        if "hr" in categories or "project" in categories:
            advice.append("Behavioural answers: always run situation -> action -> quantified result.")
        if low:
            advice.append("Review questions " + ", ".join(str(i) for i in low) + " before the real interview.")
        advice.append("Read the improved answers out loud: 90 to 180 words is about 90 seconds of speech."
                      if has_improvement else
                      "Ask for an improved answer on your weakest questions.")
        return advice[:4]

    advice = []
    if "technical" in categories:
        advice.append("Côté technique : motive chacun de tes choix (pourquoi cette technologie plutôt qu'une autre).")
    if "hr" in categories or "project" in categories:
        advice.append("Côté comportemental : systématise situation → action → résultat chiffré.")
    if low:
        advice.append("Revois d'abord les questions " + ", ".join(str(i) for i in low) + ".")
    advice.append("Relis les réponses améliorées à voix haute avant l'entretien : 90 à 180 mots "
                  "tiennent en une minute trente." if has_improvement else
                  "Demande une réponse améliorée pour tes questions les plus faibles.")
    return advice[:4]
