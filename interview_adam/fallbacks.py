"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Replis déterministes utilisés quand le modèle ne produit pas de sortie exploitable.

Règle du module : une erreur du LLM ne doit jamais faire tomber l'application. Après une
tentative de réparation du JSON, on renvoie un contenu utile marqué `degraded: true` pour
que l'interface précise clairement qu'il ne vient pas de l'IA.

Les questions de repli sont volontairement génériques (elles n'ont pas été adaptées au poste) ;
les analyses de repli sont heuristiques (longueur, structure, indices concrets) et jamais
présentées comme une note de recruteur.
"""

from interview_adam.security import defuse

TECHNICAL = {
    "fr": [
        "Qu'est-ce qui, dans ce poste, te donne envie de candidater ?",
        "Quelle est la tâche technique dont tu es le plus fier, et pourquoi ?",
        "Comment décrirais-tu ton processus pour débugger un problème compliqué ?",
        "Comment décides-tu entre deux technologies pour un même besoin ?",
        "Qu'est-ce que tu ne sais pas faire aujourd'hui et que tu veux apprendre sur ce poste ?",
        "Comment travailles-tu la qualité de ton code (tests, revues, documentation) ?",
    ],
    "en": [
        "What about this role makes you want to apply?",
        "Which technical task are you most proud of, and why?",
        "Walk me through how you debug a tricky problem.",
        "How do you choose between two technologies for the same need?",
        "What can't you do yet that you want to learn in this role?",
        "How do you keep your code quality up (tests, reviews, docs)?",
    ],
}

PROJECT = {
    "fr": [
        "Choisis un projet dans ton parcours : quel était le problème de départ ?",
        "Quelle partie de ce projet t'a demandé le plus de temps, et qu'as-tu dû sacrifier ?",
        "Qu'y aurais-tu fait différemment aujourd'hui ?",
        "Comment as-tu travaillé avec les autres sur ce projet ?",
    ],
    "en": [
        "Pick one project from your background: what problem were you solving?",
        "Which part of that project took the longest, and what did you have to cut?",
        "What would you do differently today?",
        "How did you work with the rest of the team on it?",
    ],
}

HR = {
    "fr": [
        "Raconte-moi une fois où tu as dû expliquer une décision technique à un non-technicien.",
        "Raconte-moi un désaccord dans une équipe ou un projet, et comment il s'est réglé.",
        "Comment réagis-tu quand tu réalises en pleine tâche que tu ne sais pas faire ?",
        "Quelle critique reçue sur ton travail t'a le plus fait progresser ?",
        "Comment organises-tu ton travail quand plusieurs échéances se chevauchent ?",
    ],
    "en": [
        "Tell me about a time you explained a technical decision to a non-technical person.",
        "Tell me about a disagreement in a team and how it was resolved.",
        "What do you do when you realise mid-task that you don't know how to proceed?",
        "Which piece of feedback on your work helped you improve the most?",
        "How do you organise your work when several deadlines overlap?",
    ],
}

_CATEGORY_POOLS = {"technical": TECHNICAL, "project": PROJECT, "hr": HR}


def generic_questions(question_type, n_questions, language):
    """Banque de questions génériques, mélangées par catégorie selon le type demandé."""
    language = language if language in ("fr", "en") else "fr"
    if question_type == "technical":
        plan = ["technical"] * n_questions
    elif question_type == "hr":
        plan = ["hr"] * n_questions
    else:  # mixed
        order = ["technical", "project", "hr"]
        plan = [order[i % 3] for i in range(n_questions)]

    questions = []
    cursors = {category: 0 for category in _CATEGORY_POOLS}
    for category in plan:
        pool = _CATEGORY_POOLS[category][language]
        index = cursors[category]
        text = pool[index % len(pool)]
        if index >= len(pool):  # on manque de place : on numérote pour éviter les doublons visibles
            text = f"{text} (variante {index // len(pool) + 1})"
        cursors[category] = index + 1
        questions.append({
            "question": text,
            "category": category,
            "focus": "",
            "expected_points": [],
            "degraded": True,
        })
    return questions


def evaluate_heuristic(answer, language):
    """
    Retour d'expérience immédiat sans IA : repère les signaux faibles objectives
    (longueur, première personne, connecteurs, absence d'exemple chiffré).
    score = None : aucune note n'est inventée.
    """
    language = language if language in ("fr", "en") else "fr"
    text = defuse(answer or "")
    words = len(text.split())
    lower = text.lower()

    fr_markers = ("parce que", "ensuite", "résultat", "chiffr", "%", "j'ai", "nous avons", "contexte")
    en_markers = ("because", "then", "result", "percent", "%", "i ", "we ", "context", "impact")
    markers = fr_markers if language == "fr" else en_markers
    hits = sum(1 for marker in markers if marker in lower)

    strengths, weaknesses = [], []
    if language == "fr":
        if words >= 60:
            strengths.append(f"Réponse développée ({words} mots) : le recruteur a de la matière.")
        else:
            weaknesses.append(f"Réponse trop courte ({words} mots) : insuffisante pour juger une compétence.")
        if hits >= 3:
            strengths.append("Structure en chaîne causal/action/résultat : c'est ce qu'on attend à l'oral.")
        else:
            weaknesses.append("Enchaînement situation → action → résultat absents ; ajoute le contexte et la conséquence.")
        if any(marker in lower for marker in ("%", "chiffr")) or any(c.isdigit() for c in text):
            strengths.append("Des repères concrets apparaissent, ça rend la réponse vérifiable.")
        else:
            weaknesses.append("Aucun repère chiffré ni exemple daté : difficile à croire pour un recruteur.")
        verdict = ("Analyse heuristique : le simulateur n'a pas pu solliciter le modèle pour cette réponse. "
                   "Réessaie dans un instant pour une notation complète (score sur 10 et critères).")
    else:
        if words >= 60:
            strengths.append(f"Answer is developed ({words} words): the recruiter has material to judge.")
        else:
            weaknesses.append(f"Answer is too short ({words} words): not enough to assess the skill.")
        if hits >= 3:
            strengths.append("You chain cause / action / result, which is what interviewers listen for.")
        else:
            weaknesses.append("Situation → action → result structure is missing; add context and outcome.")
        if any(marker in lower for marker in ("%", "percent")) or any(c.isdigit() for c in text):
            strengths.append("Concrete reference points appear, which makes the answer verifiable.")
        else:
            weaknesses.append("No figures or dated example: hard for a recruiter to believe.")
        verdict = ("Heuristic feedback: the simulator could not reach the model for this answer. "
                   "Try again shortly for a full score out of 10 with per-criterion ratings.")

    return {
        "score": None,
        "criteria": {"relevance": None, "clarity": None, "structure": None, "technical_accuracy": None},
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:4],
        "verdict": verdict,
        "degraded": True,
    }


def improve_fallback(question, answer, language):
    """Repli de réécriture : consigne STAR sans IA, sans faux contenu."""
    language = language if language in ("fr", "en") else "fr"
    question_clean = defuse(question or "")
    if language == "fr":
        text = (
            "Le modèle n'a pas pu rédiger de version améliorée. Pour reconstruire ta réponse, "
            f"prends « {question_clean} » et écris-la en quatre temps : (1) Situation — le contexte, "
            "à quelle époque, dans quel cadre ; (2) Tâche — ce qui attendait de toi précisément ; "
            "(3) Action — ce que TU as fait, en verbes d'action et en arbitrages ; (4) Résultat — la "
            "conséquence observable, chiffrée si possible, plus ce que tu en as tiré. "
            "Garde 90 à 180 mots et ne cite que des faits qui sont les tiens."
        )
        tips = ["Rédige d'abord la partie Action : c'est là que le recruteur te juge",
                "Termine par une conséquence mesurable",
                "Une seule idée par phrase"]
    else:
        text = (
            "The model could not produce an improved version. Rebuild your answer around "
            f"“{question_clean}” in four moves: (1) Situation — the context and when it happened; "
            "(2) Task — what exactly was expected of you; (3) Action — what YOU did, as verbs and "
            "trade-offs; (4) Result — the observable outcome, quantified if possible, plus what you "
            "learned. Keep it 90 to 180 words and only use facts that are yours."
        )
        tips = ["Write the Action part first: that is what the interviewer judges",
                "Close on a measurable consequence",
                "One idea per sentence"]
    return {
        "improved_answer": text,
        "star": None,
        "tips": tips,
        "degraded": True,
    }
