"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Prompt n°1 — génération des questions d'entretien adaptées au poste.

Trois leviers : rôle d'expert recrutement, exemples few-shot (français, décision de
conception : la consigne de langue fait traduire la sortie si l'utilisateur choisit l'anglais),
contrat JSON strict. Le contexte RAG (barème et questions de référence du domaine) est injecté
comme simple référence, jamais comme consigne.
"""

from interview_adam import config_adam as cfg
from interview_adam.prompts import base_adam as base
from interview_adam.schemas_adam import QUESTION_SET_SCHEMA

SYSTEM = f"""{base.SYSTEM_HEADER}

MISSION : produire les questions d'un entretien pour le poste décrit, au nombre exact demandé,
chacune pertinente pour CE poste (pas une question générique).

RÈGLES DE SÉLECTION
- La répartition demandée dans la TÂCHE est prioritaire : si un type domine ("technical" ou "hr"),
  au moins DEUX questions sur trois sont de ce type. L'équilibre ne vaut que pour un "mixed".
- "technical" : une question par compétence clé de l'offre, adaptée au niveau.
- "project" : ancrée sur une expérience/projet réellement présent dans le CV fourni ; sans CV,
  demande une réalisation dont le candidat pourrait parler.
- "hr" : comportemental, format situation concrète (« Raconte-moi une fois où… »), jamais théorique.
- Si des manques offre/profil sont signalés, consacre-leur au moins une question (comment compenser),
  sans jamais juger ni humilier.
- Une question = une seule chose à répondre, 40 mots max, à la 2e personne.
- "expected_points" : 2 à 4 éléments de réponse attendus (serviront à évaluer), concrets et vérifiables.

FORMAT : renvoie exactement {{"questions": [...]}} avec n objets, sans texte autour."""


EXAMPLE = """EXEMPLE (extrait)
Contexte : poste "Développeur Back-End Python (junior)", offre mentionnant FastAPI et PostgreSQL,
CV du candidat mentionnant Django et MySQL, manque signalé : fastapi.

Sortie attendue :
{"questions":[
 {"question":"Qu'est-ce qui te semble différent entre une vue Django synchrone et une route FastAPI asynchrone ?","category":"technical","focus":"FastAPI, asynchrone","expected_points":["différence thread/process vs event loop","connaissance de asyncio","cas d'usage I/O"]},
 {"question":"Dans ton projet Django, comment as-tu structuré tes modèles et géré les migrations ?","category":"project","focus":"modélisation, migrations","expected_points":["explique un choix de schéma","cite une migration précise","évoque un problème rencontré et sa résolution"]}
]}"""


def build(job_title, seniority, question_type, n_questions, language,
          company=None, job_description=None, cv_digest_text=None, gaps=None, rag_context=""):
    """Construit le prompt de génération de questions."""
    gaps = gaps or {}
    sections = []

    min_majority = (2 * n_questions + 2) // 3  # ceil(2n/3)
    if question_type == "technical":
        split = (f"{min_majority} questions au minimum sur {n_questions} en catégorie "
                 f"\"technical\" (compétences du poste), le reste en \"project\"/\"hr\".")
    elif question_type == "hr":
        split = (f"{min_majority} questions au minimum sur {n_questions} en catégorie "
                 f"\"hr\" (comportemental/motivation), le reste en \"project\"/\"technical\".")
    else:
        split = "équilibre technique / projet / comportemental."
    request = (
        f"TÂCHE : génère exactement {n_questions} questions d'entretien pour ce poste, "
        f"type de questions demandé : {question_type}, niveau : {base.seniority_label(seniority)}.\n"
        f"Répartis les catégories ainsi : {split}"
    )
    sections.append((100, request))
    sections.append((80, base.job_block(job_title, company, seniority, job_description)))

    if cv_digest_text:
        sections.append((30, "PROFIL DU CANDIDAT (anonymisé, à utiliser pour ancrer les questions)\n"
                             + base.block("candidat", cv_digest_text)))
    else:
        sections.append((30, "Aucun CV n'est fourni : les questions restent générales pour le poste, "
                             "sans supposer d'expérience particulière au candidat."))

    missing = gaps.get("missing") or []
    if missing:
        sections.append((20, "MANQUES ENTRE L'OFFRE ET LE PROFIL (compétences attendues non visibles "
                             "dans le profil) : " + ", ".join(missing[:12])))
    covered = gaps.get("covered") or []
    if covered:
        sections.append((10, "COMPÉTENCES DÉJA VISIBLES DANS LE PROFIL : " + ", ".join(covered[:12])))

    if rag_context:
        sections.append((15, "Références de barème et questions types du domaine (documentation interne, "
                             "à adapter, pas à recopier) :\n"
                             + base.block("references", rag_context)))

    sections.append((90, base.language_instruction(language)))
    sections.append((60, EXAMPLE))

    budget = cfg.MAX_CV_DIGEST_CHARS + cfg.MAX_JOB_DESCRIPTION_CHARS + cfg.MAX_RAG_CONTEXT_CHARS + 4000
    user = "\n\n".join(base.fit(sections, budget))
    return base.compose(SYSTEM, user, QUESTION_SET_SCHEMA)
