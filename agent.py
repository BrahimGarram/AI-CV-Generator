"""
Agent conversationnel de création de CV.

C'est le LLM (Gemini) qui mène la conversation : il comprend, répond aux questions,
propose des idées, rédige les reformulations, met à jour le CV et décide quand générer.
Python ne fait que :
- garder l'historique et le CV ;
- appliquer des garde-fous (guards.py) qui retirent ce que l'utilisateur n'a jamais dit ;
- journaliser la session.
"""

import json
import re

from config import OUTPUT_DIR
from cv_schema import empty_cv, is_filled
from guards import sanitize
from llm import chat_json

LOG_FILE = OUTPUT_DIR / "session_log.jsonl"
MAX_HISTORY = 30  # messages envoyés au LLM

WELCOME = (
    "Bonjour ! Je suis ton assistant pour créer un CV professionnel. "
    "Parle-moi de toi comme tu veux : ton nom, ta formation, tes stages, tes projets, tes compétences... "
    "Je te poserai des questions si besoin et je t'aiderai à tout formuler de façon professionnelle."
)

SYSTEM_PROMPT = """Tu es un conseiller carrière expert et chaleureux qui aide l'utilisateur à créer son CV.
Tu mènes la conversation comme un vrai humain : naturel, bienveillant, efficace. Tu tutoies, en français
(ou dans la langue de l'utilisateur).

À CHAQUE MESSAGE, tu renvoies un JSON avec :
- "reply"  : ta réponse à l'utilisateur ;
- "action" : "continue", "generate" ou "cancel" ;
- "cv"     : le CV COMPLET et à jour (tout le CV précédent + les changements de ce message).

TA FAÇON DE DISCUTER
- Réponds toujours d'abord à ce que l'utilisateur dit ou demande. S'il pose une question, réponds-y vraiment
  (conseils de CV, pourquoi une info est utile, etc.).
- Pose une ou deux questions à la fois, pas un interrogatoire. Ne répète jamais une question à laquelle il a
  déjà répondu ou qu'il a refusée.
- Aide-le à enrichir son CV : demande ce qui rendrait le CV plus fort (formation, compétences, stages et
  expériences avec leurs missions, projets, langues, coordonnées, poste visé, certifications, centres
  d'intérêt, résumé professionnel) et donne des idées ou des exemples concrets adaptés à son profil.
- S'il refuse une information ou dit qu'elle n'est pas nécessaire, respecte son choix et passe à autre chose.
- C'est LUI qui décide quand générer le CV.

REFORMULATIONS ET ENRICHISSEMENT
- Tu peux proposer des descriptions professionnelles (missions en phrases nominales : « Conception de... »,
  « Développement de... ») et un résumé professionnel, en partant de ce qu'il a dit.
- Montre la proposition dans "reply" et demande s'il la valide. Ne l'écris dans "cv" qu'après son accord
  (ou s'il t'a demandé explicitement de reformuler et d'ajouter directement).
- Tant qu'il n'a pas validé, garde dans "cv" sa version fidèle.

RÈGLES POUR LE CV (très important)
- N'invente JAMAIS de faits : ni entreprise, ni date, ni chiffre, ni technologie, ni diplôme, ni langue.
  Tout ce qui est dans "cv" doit venir de l'utilisateur ou d'une proposition qu'il a acceptée.
- Recopie à l'identique e-mail, téléphone et liens. Corrige seulement les majuscules et fautes évidentes
  (java -> Java, springboot -> Spring Boot, esprit -> ESPRIT, "out 2025" -> "Août 2025").
- Nom complet : first_name = prénom(s), last_name = nom de famille (souvent le dernier mot).
- Dates au format "Mois AAAA" ou "AAAA". Si une durée est donnée ("août 2025, 2 mois"), calcule la fin
  ("Septembre 2025").
- education : degree = type de diplôme (Licence, Master, Cycle ingénieur, BTS, Baccalauréat...), field =
  spécialité, institution = établissement. Un étudiant ingénieur pas encore diplômé = "Cycle ingénieur".
- experiences : un élément par stage / emploi, chacun avec SA propre entreprise, ses dates et ses missions.
  role = intitulé du poste (stage -> "Stagiaire en ..."), pas le sujet. Un même stage écrit de deux façons
  ("ETAP" et "d'étap") = un seul élément. Un stage n'est jamais un projet.
- projects : projets académiques ou personnels uniquement.
- skills : regroupées par catégorie (Langages, Frameworks, Bases de données, Outils, DevOps, Cloud,
  Data & IA, Soft skills). Pas de certification ni de diplôme dans les compétences.
- languages : avec le niveau s'il est donné (Langue maternelle, Courant, B2...).
- title = poste visé, seulement s'il le dit. profile = résumé validé par lui.

QUAND METTRE action = "generate"
- Quand il demande de générer / finaliser le CV, ou accepte ta proposition de le générer.
- Même s'il manque des informations : tu peux le signaler brièvement, mais s'il veut générer, tu génères.
- S'il demande si tu PEUX générer avec peu d'informations : réponds honnêtement que oui, c'est possible,
  explique en une phrase ce qui rendrait le CV plus fort, et laisse-le choisir (générer maintenant ou compléter).
  Ne dis jamais que c'est impossible.
- Seule exception : sans aucun nom, demande-lui son nom avant (action = "continue").
- Quand action = "generate", "reply" est une courte phrase du type « Parfait, je génère ton CV... ».
- action = "cancel" seulement s'il veut arrêter complètement la conversation."""


def _nullable():
    return {"type": ["string", "null"]}


def _object(fields, lists=()):
    return {
        "type": "object",
        "properties": {f: ({"type": "array", "items": {"type": "string"}} if f in lists else _nullable())
                       for f in fields},
    }


CV_SCHEMA = {
    "type": "object",
    "properties": {
        "personal_info": _object(["first_name", "last_name", "title", "email", "phone",
                                  "location", "linkedin", "github"]),
        "profile": _nullable(),
        "education": {"type": "array", "items": _object(
            ["degree", "field", "institution", "location", "start", "end"])},
        "experiences": {"type": "array", "items": _object(
            ["role", "company", "location", "start", "end", "description"])},
        "projects": {"type": "array", "items": _object(
            ["name", "description", "technologies"], lists=["technologies"])},
        "skills": {"type": "array", "items": _object(["category", "items"], lists=["items"])},
        "languages": {"type": "array", "items": _object(["name", "level"])},
        "certifications": {"type": "array", "items": _object(["name", "issuer", "year"])},
        "interests": {"type": "array", "items": {"type": "string"}},
    },
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "action": {"type": "string", "enum": ["continue", "generate", "cancel"]},
        "cv": CV_SCHEMA,
    },
    "required": ["reply", "action", "cv"],
}


def _compact(data):
    if isinstance(data, dict):
        return {k: _compact(v) for k, v in data.items() if is_filled(v)}
    if isinstance(data, list):
        return [_compact(v) for v in data if is_filled(v)]
    return data


class CVAgent:

    def __init__(self):
        self.data = empty_cv()
        self.history = [{"role": "assistant", "content": WELCOME}]

    @property
    def user_text(self):
        return "\n".join(m["content"] for m in self.history if m["role"] == "user")

    @property
    def conversation_text(self):
        return "\n".join(m["content"] for m in self.history)

    def handle(self, message):
        """Traite un message. Retourne {"action": "continue"|"generate"|"cancel", "reply": str}."""
        self.history.append({"role": "user", "content": message})

        # Le CV actuel est donné au LLM avec le dernier message pour qu'il le mette à jour.
        messages = self.history[-MAX_HISTORY:-1] + [{
            "role": "user",
            "content": (
                f"{message}\n\n"
                f"[CV ACTUEL — à mettre à jour et renvoyer en entier dans \"cv\"]\n"
                f"{json.dumps(_compact(self.data), ensure_ascii=False)}"
            ),
        }]
        result = chat_json(SYSTEM_PROMPT, messages, RESPONSE_SCHEMA)

        reply = (result.get("reply") or "").strip() or "D'accord. Tu veux ajouter autre chose ?"
        reply = re.sub(r"([.!?])(?=[A-ZÀ-Ý])", r"\1 ", reply)  # "début !Pour" -> "début ! Pour"
        action = result.get("action") if result.get("action") in ("continue", "generate", "cancel") else "continue"

        if isinstance(result.get("cv"), dict):
            # La réponse actuelle n'est pas incluse : une suggestion doit avoir été vue
            # par l'utilisateur avant d'entrer dans le CV.
            self.data, removed = sanitize(result["cv"], self.data, self.user_text, self.conversation_text)
        else:
            removed = ["cv manquant dans la réponse"]

        self.history.append({"role": "assistant", "content": reply})
        model = result.get("_model")
        self._log(message, action, reply, removed, model)
        return {"action": action, "reply": reply, "removed": removed,
                "model": model, "seconds": result.get("_seconds")}

    def _log(self, message, action, reply, removed, model=None):
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "message": message, "model": model, "action": action, "reply": reply,
                    "removed_by_guards": removed, "cv": _compact(self.data),
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass
