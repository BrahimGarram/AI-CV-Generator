"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Passerelle vers le Module 1 (CV) : lecture seule stricte.

Le module ne ajoute ni n'enlève rien aux CV : il passe par `db.list_generations` et
`db.get_generation`, puis anonymise immédiatement (`interview_adam.privacy`) avant toute
utilisation. Les données d'identité ne ressortent jamais de ce fichier.

Le dépôt du Module 1 ne stocke aucune offre d'emploi (aucune table, aucune colonne) :
`get_job_offer_context` est donc un point de branchement documenté qui renvoie None,
prêt à être complété le jour où l'adaptation à une offre arrive.

Le sélecteur « Utiliser mon CV » de l'interface passe par le endpoint déjà existant
`GET /history` (Module 1) : ce fichier ne fait que lire un CV sélectionné.
"""

import re
import unicodedata

import db  # Module 1 : import en lecture seule (aucune écriture, aucune modification)

from interview_adam.privacy import anonymize_cv, cv_digest, target_title_of

# Vocabulaire de compétences utilisé pour l'analyse d'écart CV / offre (déterministe, sans LLM).
SKILL_VOCAB = [
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "go", "rust", "kotlin", "swift", "sql", "r",
    "angular", "react", "vue", "next.js", "nuxt", "svelte", "django", "flask", "fastapi", "laravel", "symfony",
    "spring", "spring boot", "node.js", "express", "nestjs", ".net", "flutter", "react native", "html", "css",
    "sass", "tailwind", "bootstrap",
    "mysql", "postgresql", "mongodb", "redis", "oracle", "sqlite", "elasticsearch", "cassandra",
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "gitlab ci", "github actions", "ci/cd", "linux",
    "bash", "nginx", "grafana", "prometheus",
    "aws", "azure", "gcp", "cloud", "serverless", "kafka", "rabbitmq", "spark", "hadoop", "airflow", "dbt",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "langchain", "llm", "nlp", "opencv",
    "machine learning", "deep learning", "data analysis", "data visualization", "power bi", "tableau", "mlops",
    "git", "jira", "scrum", "agile", "tests unitaires", "pytest", "jest", "cypress", "selenium",
    "rest", "api", "graphql", "microservices", "uml", "merise", "design pattern",
]

_VOCAB_MATCHES = {term: re.compile(rf"(?<![a-z0-9+#.]){re.escape(term)}(?![a-z0-9+#])") for term in SKILL_VOCAB}


def _ascii_lower(text):
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()


def get_cv_bundle(user_id, generation_id):
    """
    CV anonymisé prêt pour un prompt.
    Retourne None si le CV n'existe pas ou n'appartient pas à l'utilisateur.
    """
    generation = db.get_generation(generation_id, user_id)
    if generation is None:
        return None
    cv = generation.get("cv") or {}
    return {
        "generation_id": generation["id"],
        # Le titre de la génération est un nom de fichier choisi par l'utilisateur : il peut
        # contenir son propre nom. Il n'est donc jamais exposé au module (ni prompt, ni UI).
        "target_title": target_title_of(cv),
        "digest": cv_digest(cv),
        "anonymized": anonymize_cv(cv),
    }


def get_job_offer_context(user_id, generation_id):
    """
    Point de branchement pour le Module 1 : adaptation du CV à une offre d'emploi.

    Le dépôt actuel ne stocke aucune offre (ni table, ni colonne, ni endpoint) : le
    simulateur demande donc la description de l'offre dans son propre formulaire.
    Quand le Module 1 exposera les offres, renvoyer ici un dictionnaire :
        {"title": str, "description": str, "company": str, "source": "module1"}
    `interview_adam.service.generate_questions` l'utilise sans autre changement
    (la saisie manuelle restant le repli).
    """
    return None


def skill_gaps(job_description, profile_digest):
    """
    Écart déterministe entre l'offre et le profil (texte déjà anonymisé du CV) :
    ce que le candidat a, ce que l'offre demande et qu'il n'a pas, et ce qu'il a en plus.
    Les manques orientent les questions : c'est une source classique de question d'entretien.
    """
    offer_text = _ascii_lower(job_description or "")
    profile_text = _ascii_lower(profile_digest or "")

    required = {term for term, pattern in _VOCAB_MATCHES.items() if pattern.search(offer_text)}
    if not required:
        return {"missing": [], "covered": [], "extra": []}
    held = {term for term, pattern in _VOCAB_MATCHES.items() if pattern.search(profile_text)}

    return {
        "missing": sorted(required - held),
        "covered": sorted(required & held),
        "extra": sorted(held - required),
    }
