"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Schémas du simulateur d'entretien.

Deux familles, volontairement séparées :
- les modèles Pydantic (`*In`, `*Out`) : contrat de l'API et validation de la sortie du LLM ;
- les schémas JSON (`*_JSON_SCHEMA`) : envoyés à Ollama dans `format` et rappelés en texte
  dans le prompt. Ils sont écrits à la main, aplatis (pas de `$ref`/`$defs`), sans `enum` ni
  `minimum`/`maximum` : la grammaire de sortie d'Ollama ne les garantit pas, et Mistral
  n'est pas listé dans les modèles à sortie structurée. Les bornes 0-10 sont donc
  re-calées côté Python par les validateurs Pydantic.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from interview_adam import config_adam as cfg
from interview_adam.security import defuse

Language = Literal["fr", "en"]
QuestionType = Literal["technical", "hr", "mixed"]
Seniority = Literal["junior", "inter", "senior", "lead"]


def _clean_str(value, limit):
    if value is None:
        return ""
    return defuse(value)[:limit].strip()


def _coerce_score(value):
    """Renvoie un float entre 0 et 10, ou None si la valeur est irrécupérable."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.search(r"-?\d+(?:[.,]\d+)?", str(value).replace("\u00a0", " "))
        if not match:
            return None
        number = float(match.group(0).replace(",", "."))
    if number < 0:
        return 0.0
    if number > 10:
        return 10.0
    return round(number, 1)


# ----------------------------------------------------------------------
# Entrées API
# ----------------------------------------------------------------------

class QuestionsIn(BaseModel):
    """Contexte de l'entretien. `job_description` est saisie à la main : le dépôt ne stocke
    aucune offre (voir interview_adam.cv_bridge.get_job_offer_context)."""

    job_title: str = Field(..., description="Intitulé du poste visé")
    job_description: Optional[str] = Field(None, description="Description de l'offre, facultative")
    company: Optional[str] = Field(None, description="Nom de l'entreprise, facultatif")
    seniority: Seniority = Field("junior", description="Niveau visé")
    question_type: QuestionType = Field("mixed", description="Type de questions")
    n_questions: int = Field(6, ge=cfg.MIN_QUESTIONS, le=cfg.MAX_QUESTIONS)
    language: Language = Field(cfg.DEFAULT_LANGUAGE, description="Langue des questions et réponses")
    use_cv: bool = Field(False, description="Compléter le contexte avec un CV déjà généré")
    cv_generation_id: Optional[str] = Field(None, description="Identifiant du CV dans l'historique Module 1")

    @field_validator("job_title", "job_description", "company", mode="before")
    @classmethod
    def _sanitize_text_fields(cls, value, info):
        limits = {"job_title": cfg.MAX_JOB_TITLE_CHARS,
                  "job_description": cfg.MAX_JOB_DESCRIPTION_CHARS,
                  "company": cfg.MAX_COMPANY_CHARS}
        return _clean_str(value, limits.get(info.field_name, cfg.MAX_JOB_TITLE_CHARS))

    @field_validator("job_title")
    @classmethod
    def _title_required(cls, value):
        if len(value) < 2:
            raise ValueError("Intitulé de poste requis (2 caractères minimum).")
        return value


class EvaluateIn(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    index: int = Field(..., ge=1, le=cfg.MAX_QUESTIONS, description="Numéro de la question (1-based)")
    answer: str = Field(..., description="Réponse rédigée par le candidat")

    @field_validator("answer", mode="before")
    @classmethod
    def _sanitize_answer(cls, value):
        return _clean_str(value, cfg.MAX_ANSWER_CHARS)

    @field_validator("session_id", mode="before")
    @classmethod
    def _sanitize_session(cls, value):
        # Identifiant technique : aucun caractère hors hexadécimal ne doit passer.
        cleaned = defuse(str(value or ""))
        if not cleaned.isalnum():
            raise ValueError("Identifiant de session invalide.")
        return cleaned


class ImproveIn(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    index: int = Field(..., ge=1, le=cfg.MAX_QUESTIONS)

    @field_validator("session_id", mode="before")
    @classmethod
    def _sanitize_session(cls, value):
        cleaned = defuse(str(value or ""))
        if not cleaned.isalnum():
            raise ValueError("Identifiant de session invalide.")
        return cleaned


# ----------------------------------------------------------------------
# Sorties attendues du LLM (Pydantic) + leurs schémas JSON pour Ollama
# ----------------------------------------------------------------------

class AdamQuestion(BaseModel):
    question: str
    category: str = "technical"
    focus: str = ""
    expected_points: list[str] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def _question_not_empty(cls, value):
        cleaned = defuse(value)[: cfg.MAX_QUESTION_CHARS].strip()
        if len(cleaned) < 8:
            raise ValueError("Question trop courte ou vide.")
        return cleaned

    @field_validator("category", "focus", mode="before")
    @classmethod
    def _soft_text(cls, value):
        return defuse(str(value or "")).strip()

    @field_validator("expected_points", mode="before")
    @classmethod
    def _string_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return [defuse(str(v)).strip() for v in list(value)[:8] if str(v).strip()]


class AdamQuestionSet(BaseModel):
    questions: list[AdamQuestion]

    @field_validator("questions")
    @classmethod
    def _not_empty(cls, value):
        if not value:
            raise ValueError("Aucune question produite.")
        return value


QUESTION_SET_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "category": {"type": "string"},
                    "focus": {"type": "string"},
                    "expected_points": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["question", "category"],
            },
        }
    },
    "required": ["questions"],
}


class AdamCriteria(BaseModel):
    relevance: Optional[float] = None
    clarity: Optional[float] = None
    structure: Optional[float] = None
    technical_accuracy: Optional[float] = None

    @field_validator("*", mode="before")
    @classmethod
    def _clamp(cls, value):
        return _coerce_score(value)


class AdamEvaluation(BaseModel):
    """La note globale est obligatoire : sans elle l'évaluation n'a pas de sens pour le candidat."""

    score: float
    criteria: AdamCriteria = Field(default_factory=AdamCriteria)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    verdict: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, value):
        coerced = _coerce_score(value)
        if coerced is None:
            raise ValueError("Note absente ou illisible.")
        return coerced

    @field_validator("verdict", mode="before")
    @classmethod
    def _soft_text(cls, value):
        return defuse(str(value or "")).strip()

    @field_validator("strengths", "weaknesses", mode="before")
    @classmethod
    def _string_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return [defuse(str(v)).strip() for v in list(value)[:8] if str(v).strip()]


EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "criteria": {
            "type": "object",
            "properties": {
                "relevance": {"type": "number"},
                "clarity": {"type": "number"},
                "structure": {"type": "number"},
                "technical_accuracy": {"type": "number"},
            },
            "required": ["relevance", "clarity", "structure", "technical_accuracy"],
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string"},
    },
    "required": ["score", "criteria", "strengths", "weaknesses", "verdict"],
}


class AdamStar(BaseModel):
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _soft_text(cls, value):
        return defuse(str(value or "")).strip()


class AdamImprovement(BaseModel):
    improved_answer: str = ""
    star: Optional[AdamStar] = None
    tips: list[str] = Field(default_factory=list)

    @field_validator("improved_answer", mode="before")
    @classmethod
    def _clamp_answer(cls, value):
        cleaned = defuse(str(value or "")).strip()
        if len(cleaned) < 20:
            raise ValueError("Réponse améliorée vide ou trop courte.")
        return cleaned[: 2 * cfg.MAX_ANSWER_CHARS]

    @field_validator("tips", mode="before")
    @classmethod
    def _string_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return [defuse(str(v)).strip() for v in list(value)[:8] if str(v).strip()]


IMPROVEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "improved_answer": {"type": "string"},
        "star": {
            "type": "object",
            "properties": {
                "situation": {"type": "string"},
                "task": {"type": "string"},
                "action": {"type": "string"},
                "result": {"type": "string"},
            },
            "required": ["situation", "task", "action", "result"],
        },
        "tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["improved_answer"],
}


# ----------------------------------------------------------------------
# Sorties API
# ----------------------------------------------------------------------

class AdamRagSource(BaseModel):
    """
    Fragment de la base de connaissances effectivement injecté dans le prompt.
    `score` est la similarité cosinus brute (vecteur de la requête contre le fragment) :
    c'est une mesure, pas une confiance recalculée, donc l'interface peut l'afficher telle
    quelle. `id` renvoie au fragment de `interview_adam/knowledge/`, vérifiable en CLI.
    """

    id: str
    domain: str
    title: str
    type: str = "guideline"
    difficulty: str = "intermediate"
    score: float


class QuestionOut(BaseModel):
    index: int
    question: str
    category: str
    focus: str = ""
    expected_points: list[str] = Field(default_factory=list)


class InterviewContextOut(BaseModel):
    job_title: str
    company: Optional[str] = None
    seniority: str
    question_type: str
    language: str
    cv_used: bool = False


class QuestionsOut(BaseModel):
    session_id: str
    context: InterviewContextOut
    questions: list[QuestionOut]
    model: Optional[str] = None
    seconds: Optional[float] = None
    degraded: bool = Field(False, description="Vraies si un repli sans IA a été utilisé")
    rag_used: bool = Field(False, description="Vrai si des fragments RAG ont été injectés")
    rag_sources: list[AdamRagSource] = Field(default_factory=list)


class EvaluationOut(BaseModel):
    session_id: str
    index: int
    question: str
    answer: str
    score: Optional[float]
    criteria: AdamCriteria
    strengths: list[str]
    weaknesses: list[str]
    verdict: str
    model: Optional[str] = None
    seconds: Optional[float] = None
    degraded: bool = False
    rag_used: bool = False
    rag_sources: list[AdamRagSource] = Field(default_factory=list)


class ImprovementOut(BaseModel):
    session_id: str
    index: int
    improved_answer: str
    star: Optional[AdamStar] = None
    tips: list[str] = Field(default_factory=list)
    model: Optional[str] = None
    seconds: Optional[float] = None
    degraded: bool = False
    rag_used: bool = False
    rag_sources: list[AdamRagSource] = Field(default_factory=list)


class InterviewStatusOut(BaseModel):
    """
    Diagnostic pour l'interface : bandeau « le modèle est indisponible » avant de lancer
    un entretien, et preuve à l'écran que le RAG est bien branché sur l'index ingéré.
    """

    llm_available: bool
    llm_reason: str = ""
    model: str
    rag_available: bool = False
    rag_reason: str = ""
    rag_chunks: int = 0
    rag_model: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    question_types: list[str] = Field(default_factory=list)


class SessionSummaryOut(BaseModel):
    id: str
    job_title: str
    company: Optional[str] = None
    seniority: str
    question_type: str
    language: str
    status: str
    n_questions: int
    answered: int
    average_score: Optional[float] = None
    best_index: Optional[int] = None
    weakest_index: Optional[int] = None
    created_at: str
    finished_at: Optional[str] = None
    saved_summary: Optional[dict] = Field(
        None, description="Synthèse figée à la clôture, conservée telle quelle en base")


class SessionDetailOut(SessionSummaryOut):
    cv_used: bool = False
    model: Optional[str] = None
    answers: list[dict] = Field(default_factory=list)
    advice: list[str] = Field(default_factory=list)
