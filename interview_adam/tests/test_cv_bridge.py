"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Passerelle Module 1 : lecture seule stricte et anonymisation immédiate du CV, plus l'écart
déterministe offre / profil qui oriente les questions.
"""

import pytest

import db  # Module 1
from interview_adam import cv_bridge
from interview_adam.privacy import find_pii


def test_bundle_is_anonymised_but_keeps_useful_facts(clean_cv, user):
    bundle = cv_bridge.get_cv_bundle(user["id"], "gen1")

    assert bundle["generation_id"] == "gen1"
    assert bundle["target_title"] == "Développeuse Back-End"
    assert find_pii(bundle["digest"]) == []
    assert "ESPRIT" in bundle["digest"] and "TechCorp" in bundle["digest"]
    assert "nadia" not in bundle["digest"].lower()
    assert "example.fr" not in bundle["digest"]
    assert bundle["anonymized"]["target_title"] == "Développeuse Back-End"
    assert "personal_info" not in bundle["anonymized"]


def test_bundle_never_exposes_the_generation_title(clean_cv, user, monkeypatch):
    """
    Le titre d'une génération est un nom de fichier libre : l'utilisateur peut y mettre
    son propre nom. Il ne doit jamais sortir de la passerelle, sinon il se retrouve dans
    `company`, donc dans le prompt et dans l'interface.
    """
    monkeypatch.setattr(db, "get_generation",
                        lambda gid, uid: {"id": gid, "title": "CV Nadia Benali — 06 12 34 56 78",
                                          "cv": clean_cv})
    bundle = cv_bridge.get_cv_bundle(user["id"], "gen1")
    assert "cv_title" not in bundle
    assert "Benali" not in str(bundle)


def test_bundle_is_none_for_an_unknown_generation(user):
    assert cv_bridge.get_cv_bundle(user["id"], "absent") is None


def test_bridge_is_read_only_on_the_module1_database(clean_cv, user, monkeypatch):
    """Aucune écriture dans les tables du Module 1 : les fonctions de modification sont interdites."""
    for name in ("save_generation", "delete_generation", "update_generation"):
        if hasattr(db, name):
            monkeypatch.setattr(db, name, _forbidden)

    monkeypatch.setattr(db, "list_generations", _forbidden)
    cv_bridge.get_cv_bundle(user["id"], "gen1")


def _forbidden(*args, **kwargs):
    raise AssertionError("la passerelle ne doit jamais écrire dans le Module 1")


def test_job_offer_context_is_an_empty_seam(user):
    """
    Le dépôt ne stocke aucune offre : la fonction renvoie None et le simulateur demande
    la description à la main. Test de verrouillage du contrat, pas du contenu.
    """
    assert cv_bridge.get_job_offer_context(user["id"], "gen1") is None


# ----------------------------------------------------------------------
# Écart offre / profil
# ----------------------------------------------------------------------

def test_skill_gaps_splits_required_skills_into_missing_and_covered():
    offer = "Nous cherchons FastAPI, PostgreSQL et Docker pour notre équipe data."
    profile = "Expérience : Python, FastAPI, pandas, Git."

    gaps = cv_bridge.skill_gaps(offer, profile)
    assert "fastapi" in gaps["covered"]
    assert set(gaps["missing"]) >= {"postgresql", "docker"}
    assert "git" in gaps["extra"]


def test_no_required_skill_detected_means_no_invented_gap():
    gaps = cv_bridge.skill_gaps("Rejoignez une équipe dynamique et bienveillante.", "Python, Docker")
    assert gaps == {"missing": [], "covered": [], "extra": []}


def test_accents_and_casing_do_not_hide_a_skill():
    gaps = cv_bridge.skill_gaps("Maîtrise de Kubernetes et de la CI/CD exigée.", "kubernetes, Jenkins")
    assert "kubernetes" in gaps["covered"]
    assert "ci/cd" in gaps["missing"]


def test_word_boundaries_avoid_partial_matches():
    """« graph » ne doit pas être lu comme « graphql », ni « goroutine » comme « go »."""
    gaps = cv_bridge.skill_gaps("Besoin deographe et de rédaction.", "")
    assert "go" not in gaps["missing"] and "graphql" not in gaps["missing"]


def test_gaps_on_an_anonymised_digest_stay_useful(clean_cv, user):
    """
    Le digest expurgé conserve les compétences : « PostgreSQL » apparaît dans les
    technologies du projet, donc seul « React » ressort comme manque réel.
    """
    bundle = cv_bridge.get_cv_bundle(user["id"], "gen1")
    gaps = cv_bridge.skill_gaps("Poste : Python, PostgreSQL, React.", bundle["digest"])
    assert {"python", "postgresql"} <= set(gaps["covered"])
    assert gaps["missing"] == ["react"]
