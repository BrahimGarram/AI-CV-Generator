"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Tests de l'anonymisation : la règle du module est qu'aucune donnée personnelle brute
n'atteint le modèle, y compris quand elle provient d'un CV du Module 1.
"""

import pytest

from interview_adam import config_adam as cfg
from interview_adam.privacy import (anonymize_cv, assert_anonymized, cv_digest, find_pii, scrub_text,
                                    target_title_of)
from interview_adam.prompts import adam_evaluate, adam_improve, adam_questions

CV = {
    "personal_info": {
        "first_name": "Camille", "last_name": "Martin",
        "title": "Développeur Full-Stack Angular / FastAPI",
        "email": "camille.martin@example.fr", "phone": "+216 22 345 678",
        "location": "Tunis, La Marsa, rue 8245",
        "linkedin": "https://www.linkedin.com/in/camille-martin",
        "github": "www.github.com/camille-martin",
    },
    "profile": "Étudiant ingénieur, contacter camille.martin@example.fr ou au 022 345 678.",
    "education": [{"degree": "Cycle ingénieur", "field": "Génie logiciel", "institution": "ESPRIT",
                   "location": "Tunis", "start": "2022", "end": "2027"}],
    "experiences": [{"role": "Développeur stagiaire", "company": "TechCorp", "location": "Tunis",
                     "start": "2025", "end": "2025",
                     "description": "Refonte de l'API (voir https://blog.example.org/post)."}],
    "projects": [{"name": "SmartCareer", "description": "API FastAPI + Angular, dépôt sur "
                  "github.com/camille-martin/smartcareer", "technologies": ["FastAPI", "Angular", "PostgreSQL"]}],
    "skills": [{"category": "Langages", "items": ["Python", "TypeScript"]}],
    "languages": [{"name": "Arabe", "level": "maternelle"}],
    "certifications": [],
    "interests": ["échecs"],
}


def test_personal_info_is_dropped_entirely():
    anonymized = anonymize_cv(CV)
    assert "personal_info" not in anonymized
    for value in ("Camille", "Martin", "camille.martin@example.fr", "+216 22 345 678"):
        assert value not in str(anonymized)


def test_target_title_survives_and_is_returned_separately():
    assert target_title_of(CV) == "Développeur Full-Stack Angular / FastAPI"
    assert anonymize_cv(CV)["target_title"] == "Développeur Full-Stack Angular / FastAPI"


def test_locations_are_removed_everywhere():
    dumped = str(anonymize_cv(CV))
    assert "Marsa" not in dumped
    assert "Tunis" not in dumped


def test_emails_phones_and_urls_are_scrubbed_from_free_text():
    cleaned = scrub_text(CV["profile"])
    assert "camille.martin@example.fr" not in cleaned
    assert "022 345 678" not in cleaned
    assert find_pii(cleaned) == []

    description = scrub_text(CV["experiences"][0]["description"])
    assert "blog.example.org" not in description
    assert find_pii(description) == []


def test_email_local_part_never_survives_the_domain_replacement():
    """
    Régression : un domaine nu est aussi reconnu comme URL. Sans la garde « (?<!@) »,
    « camille.martin@example.fr » devenait « camille.martin@[lien retiré] » — l'identité
    restait dans le prompt alors que find_pii() ne voyait plus aucune adresse.
    """
    for text in ("écris à camille.martin@example.fr merci",
                 "LinkedIn: linkedin.com/in/camille-martin",
                 "dépôt github.com/camille-martin/smartcareer"):
        cleaned = scrub_text(text)
        assert "camille" not in cleaned.lower()
        assert "martin" not in cleaned.lower()
        assert find_pii(cleaned) == []


def test_digest_is_pii_free():
    digest = cv_digest(CV)
    assert find_pii(digest) == []
    assert "LinkedIn" not in digest
    # Le contenu utile est conservé : l'IA doit pouvoir s'appuyer sur les faits.
    assert "ESPRIT" in digest
    assert "TechCorp" in digest
    assert "FastAPI" in digest


def test_digest_is_bounded():
    huge = dict(CV, experiences=[dict(CV["experiences"][0], description="mot " * 4000)])
    assert len(cv_digest(huge)) <= cfg.MAX_CV_DIGEST_CHARS + 1


def test_redact_orgs_flag_replaces_companies_and_schools(monkeypatch):
    monkeypatch.setattr(cfg, "REDACT_ORGS", True)
    dumped = str(anonymize_cv(CV))
    assert "TechCorp" not in dumped and "ESPRIT" not in dumped
    assert "une entreprise" in dumped and "un établissement" in dumped


def test_assert_anonymized_blocks_surviving_pii():
    with pytest.raises(Exception) as excinfo:
        assert_anonymized("écrire à quelqu'un@exemple.com")
    assert "confidentialité" in str(excinfo.value).lower()


def test_prompts_never_contain_pii_with_real_cv():
    """Le garde-fou appelé par le client doit passer sur les trois prompts réels."""
    digest = cv_digest(CV)
    prompts = [
        adam_questions.build(
            job_title="Développeur Full-Stack", seniority="junior", question_type="mixed",
            n_questions=4, language="fr", company="TechCorp",
            job_description="FastAPI, PostgreSQL, docker. Contact: rh@techcorp.tn, +216 71 000 000",
            cv_digest_text=digest, gaps={"missing": ["docker"], "covered": ["FastAPI"]}),
        adam_evaluate.build(question="Parle-moi de ton API.", category="technical",
                            expected_points=["explique un choix"], answer=digest, language="fr",
                            job_title="Développeur Full-Stack"),
        adam_improve.build(question="Raconte une fois où tu as débuggé.", category="hr",
                           answer=digest, language="fr", cv_digest_text=digest),
    ]
    for prompt in prompts:
        assert find_pii(prompt) == [], prompt[:200]
        assert "camille.martin@example.fr" not in prompt
        assert "Camille Martin" not in prompt
