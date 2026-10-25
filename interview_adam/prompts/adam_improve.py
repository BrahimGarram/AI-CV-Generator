"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Prompt n°3 — proposition d'une réponse améliorée.

Règle héritée de la philosophie du projet (Module 1) : ne jamais inventer de fait sur le
candidat. Une amélioration qui manque d'information laisse un marqueur `[à compléter : …]`
plutôt qu'un faux chiffre ou une fausse entreprise.

Pour une question comportementale, la réponse est reconstruite en STAR (Situation, Tâche,
Action, Résultat) ; pour une question technique, en démonstration de raisonnement.
"""

from interview_adam import config_adam as cfg
from interview_adam.prompts import base_adam as base
from interview_adam.schemas_adam import IMPROVEMENT_SCHEMA

SYSTEM = f"""{base.SYSTEM_HEADER}

MISSION : proposer un MODÈLE de réponse que le candidat adaptera avec ses vrais faits pour
convaincre le recruteur du poste. Ce n'est pas sa réponse définitive : une trame bien structurée,
avec UNIQUEMENT ses informations à lui.

RÈGLES ABSOLUES
- Reste sur le SUJET et la MÊME situation que le candidat : une question sur la conteneurisation
  ne devient pas une anecdote de débogage ; un conflit ne devient pas une histoire de logs.
- N'ajoute AUCUN fait (entreprise, technologie, chiffre, durée, résultat) absent de sa réponse ou
  de son profil.
- Ne conclus JAMAIS sur un résultat inventé (un pourcentage, une économie, une date non donnés).
- Réponse courte ou creuse du candidat → RACOURCIS et signale l'absence au lieu de la combler :
  chaque fait manquant devient `[à compléter : …]`. Une réponse améliorée de 30 mots entièrement
  balisés est correcte ; une histoire inventée de 120 mots est une faute.
- INTERDIT de recopier l'EXEMPLE. N'utilise PAS les mots « inscriptions », « pool de connexions »,
  « logs », « taux d'échec », « serveur », « Django », « PostgreSQL » sauf s'ils figurent dans LA
  réponse ou le profil du candidat. L'exemple ne fournit que la FORME et l'usage des [à compléter].
- Réutilise SES mots ; corrige style, précision technique et ordre des idées.
- Longueur : 80 à 120 mots seulement si le candidat a fourni cette matière, sinon plus court avec
  des [à compléter]. Deux ou trois paragraphes, sans puces dans "improved_answer".

STRUCTURE
- Comportemental/projet (hr/project) : STAR explicite — situation (contexte court et daté),
  task (ce qui était attendu), action (ce qu'IL a fait : verbes, décisions, arbitrages),
  result (conséquence observable + ce qu'il en tire).
- Technique (technical) : démonstration de raisonnement — principe → démarche concrète → cas réel
  du candidat → limites/alternatives. Renseigne "star" avec les équivalents.
- "tips" : 2-3 chaînes courtes et actionnables pour l'oral, au « tu », sans numéro ni structure
  interne (pas de généralité du type « sois confiant », pas un tableau à l'intérieur d'une chaîne).

FORMAT : renvoie exactement {{"improved_answer":"...","star":{{"situation":"...","task":"...","action":"...",
"result":"..."}},"tips":["..."]}}."""


EXAMPLE = """EXEMPLE DE FORMAT UNIQUEMENT — squelette, aucun contenu réel à recopier.
Question technique : « Comment rends-tu ton application exécutable sur n'importe quelle machine ? »
Réponse du candidat (courte et pauvre) : « Je l'embarque dans un conteneur. »
Sortie attendue : le candidat n'a donné presque aucune matière, donc CHAQUE fait absent devient
un marqueur [à compléter : …] — on n'invente pas une histoire à sa place.
{"improved_answer":"Pour rendre mon application portable, j'ai [à compléter : quel outil d'image ?] afin de [à compléter : quel bénéfice concret pour l'équipe ?]. Concrètement j'ai [à compléter : le fichier ou la commande utilisé], ce qui a donné [à compléter : résultat observable]. La limite que j'identifie : [à compléter : un compromis ou une contrainte].",
 "star":{"situation":"[à compléter : le problème]","task":"[à compléter : l'objectif]","action":"[à compléter : ce que TU as fait]","result":"[à compléter : la conséquence]"},
 "tips":["Remplace chaque [à compléter] par un fait réel de TON projet","Garde la réponse courte et honnête plutôt que de broder"]}"""


def build(question, category, answer, language, evaluation=None, cv_digest_text=None,
          job_title=None, seniority=None, technique_notes=""):
    """Construit le prompt de réécriture améliorée."""
    header = (f"Question posée (catégorie={category}"
              f"{', poste=' + job_title if job_title else ''}"
              f"{', niveau=' + base.seniority_label(seniority) if seniority else ''}) :\n"
              + base.block("question", question, cfg.MAX_QUESTION_CHARS))

    parts = [(100, f"TÂCHE : réécris la réponse du candidat pour le recruteur de ce poste.\n\n{header}"),
             (70, "Réponse actuelle du candidat :\n"
                  + base.block("reponse_candidat", answer or "(vide)", cfg.MAX_ANSWER_CHARS))]

    if evaluation:
        weaknesses = [w for w in (evaluation.get("weaknesses") or [])[:4] if w]
        criteria = {key: value for key, value in (evaluation.get("criteria") or {}).items()
                    if isinstance(value, (int, float))}
        note = f"Évaluation précédente : {evaluation.get('score')}/10."
        if weaknesses:
            note += "\nPoints à corriger en priorité :\n" + "\n".join(f"- {w}" for w in weaknesses)
        if criteria:
            note += "\nCritères les plus faibles : " + ", ".join(f"{k}={v}" for k, v in criteria.items())
        parts.append((50, note))

    if cv_digest_text:
        parts.append((25, "Profil du candidat (anonymisé) — unique source de faits autorisés :\n"
                          + base.block("candidat", cv_digest_text)))

    if technique_notes:
        parts.append((15, "Fiches de méthode (documentation interne) :\n"
                          + base.block("references", technique_notes)))

    parts.append((40, base.language_instruction(language)))
    parts.append((60, EXAMPLE))

    budget = 2 * cfg.MAX_ANSWER_CHARS + cfg.MAX_CV_DIGEST_CHARS + cfg.MAX_RAG_CONTEXT_CHARS + 4000
    user = "\n\n".join(base.fit(parts, budget))
    return base.compose(SYSTEM, user, IMPROVEMENT_SCHEMA)
