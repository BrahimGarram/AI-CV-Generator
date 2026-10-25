"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Prompt n°2 — évaluation d'une réponse du candidat.

Barème explicite avec ancres de score (un 7 B sans ancres donne du 7-8 à tout), critères
séparés (pertinence, clarté, structure, exactitude technique), et interdiction d'inventer
une compétence que le candidat n'a pas mentionnée. Le barème du domaine (RAG) est fourni
en référence.
"""

from interview_adam import config_adam as cfg
from interview_adam.prompts import base_adam as base
from interview_adam.schemas_adam import EVALUATION_SCHEMA

SYSTEM = f"""{base.SYSTEM_HEADER}

MISSION : évaluer la réponse d'un candidat à UNE question, comme le recruteur du poste.
Exigeant mais formatif : le candidat doit progresser.

BARÈME (0-10, décimal)
- 0-3 : faux, ou trop vague pour être vérifiable (« je suis rigoureux »).
- 4-5 : éléments justes mais incomplets, sans exemple concret ni résultat mesurable.
- 6-7 : correct et illustré, mais structure floue ou peu de profondeur technique.
- 8-9 : précis, structuré (contexte → action → résultat), exemple concret véridique.
- 10 : excellent et mesuré : faits chiffrés, choix justifiés, conscience des limites.

CRITÈRES (chacun 0-10, indépendants de la note globale)
- relevance : traite la question posée (pas une réponse préparée à côté).
- clarity : vocabulaire précis, pas de jargon de remplissage.
- structure : enchaînement logique, exemple situé dans le temps.
- technical_accuracy : justesse réelle ; si comportemental, justesse du raisonnement et
  cohérence des faits racontés.

RÈGLES
- Juge uniquement ce qui est écrit ; n'invente aucune compétence ni expérience non citée.
- Distingue DEUX échecs et nomme lequel dans "verdict" :
  * HORS SUJET : la réponse ne traite pas la question → "relevance" basse (le reste peut être
    juste) ; le candidat doit apprendre à écouter la question, pas réviser un cours.
  * MANQUE DE CONNAISSANCES : bon sujet mais faux ou superficiel → "relevance" correcte mais
    "technical_accuracy" basse ; le candidat doit réviser le sujet.
    Ne confonds jamais : juste-mais-à-côté ≠ lacune technique ; sur-sujet-mais-faux ≠ hors-sujet.
- "strengths"/"weaknesses" : 1 à 4 éléments concrets citant un passage, rédigés dans la langue
  demandée (ne recopie aucun document de référence).
- "verdict" : 2-3 phrases, pro et encourageant, résumant le niveau et disant si le problème est
  l'écoute (hors sujet) ou la maîtrise (lacune).
- Réponse vide : score proche de 0 avec une faiblesse explicite.

FORMAT : renvoie exactement {{"score":...,"criteria":{{"relevance":...,"clarity":...,"structure":...,
"technical_accuracy":...}},"strengths":[...],"weaknesses":[...],"verdict":"..."}}."""


EXAMPLE = """EXEMPLE
Question (technical, poste "Développeur Back-End Python junior") :
"Comment optimises-tu une requête SQL lente ?"
Réponse du candidat : "Je mets des index et j'utilise JOIN au lieu de plusieurs requêtes."

Sortie attendue :
{"score":4.5,
 "criteria":{"relevance":7,"clarity":6,"structure":3,"technical_accuracy":4},
 "strengths":["Deux pistes correctes et applicables (index, réduction des allers-retours)"],
 "weaknesses":["Aucun diagnostic : la lenteur n'est jamais mesurée (EXPLAIN ANALYZE, plan d'exécution)","Pas d'exemple concret ni de structure problème → action → résultat"],
 "verdict":"Réponse sur le sujet mais lacune de méthode : c'est un manque de connaissances, pas du hors-sujet. Un recruteur attend la démarche — mesurer avant d'optimiser, puis justifier — et un cas chiffré."}"""


def build(question, category, expected_points, answer, language,
          job_title=None, seniority=None, rubric_context=""):
    """Construit le prompt d'évaluation d'une réponse."""
    header = (f"Question posée (catégorie={category}"
              f"{', poste=' + job_title if job_title else ''}"
              f"{', niveau=' + base.seniority_label(seniority) if seniority else ''}) :\n"
              + base.block("question", question, cfg.MAX_QUESTION_CHARS))

    task = f"TÂCHE : évalue la réponse ci-dessous sur 10 avec ses quatre critères.\n\n{header}"
    if expected_points:
        anchors = "\n".join(f"- {point}" for point in list(expected_points)[:6])
        task += f"\n\nÉléments de réponse attendus (barème du recruteur pour cette question) :\n{anchors}"
    task += "\n\n" + "Réponse rédigée par le candidat :\n" + base.block(
        "reponse_candidat", answer or "(vide)", cfg.MAX_ANSWER_CHARS)

    sections = [
        (100, task),
        (40, base.language_instruction(language)),
    ]
    if rubric_context:
        sections.append((15, "Barème du domaine (documentation interne, à adapter à la question) :\n"
                             + base.block("references", rubric_context)))
    sections.append((60, EXAMPLE))

    budget = cfg.MAX_ANSWER_CHARS + cfg.MAX_RAG_CONTEXT_CHARS + 4000
    user = "\n\n".join(base.fit(sections, budget))
    return base.compose(SYSTEM, user, EVALUATION_SCHEMA)
