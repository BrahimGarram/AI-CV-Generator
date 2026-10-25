"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Anonymisation des données du CV avant tout envoi au modèle.

Règle du module : aucune donnée personnelle brute ne quitte l'application.
- `personal_info` est intégralement supprimé (nom, prénom, e-mail, téléphone, lieu, LinkedIn, GitHub) ;
  seul le poste visé (`title`) est lu avant suppression, pour préremplir le contexte de l'offre ;
- les champs `location` sont supprimés partout (adresse) ;
- e-mails, téléphones et URL sont effacés par expression régulière de tout texte libre ;
- entreprises et écoles : conservées par défaut (elles servent à adapter les questions),
  neutralisées si ADAM_REDACT_ORGS=true.

Mistral tourne en local via Ollama : rien n'est envoyé à un tiers, mais la règle est
appliquée quand même (aucune PII dans les journaux, les prompts ou la base de données).
"""

import re

from cv_schema import clean_cv

from interview_adam import config_adam as cfg


class PrivacyError(RuntimeError):
    """Contenu pouvant révéler l'identité refusé d'être envoyé au modèle."""


# Deuxième branche : un nom de domaine écrit en clair (github.com/…, example.fr).
# `(?<!@)` est essentiel : sans lui, la fin d'une adresse e-mail serait remplacée par
# « [lien retiré] » et la partie locale — nadia.benali@ — survivrait dans le prompt.
URL_RE = re.compile(r"(?:https?://|www\.|mailto:)\S+|(?<!@)\b[\w.-]+\.(?:com|fr|net|org|io|dev|tn|ma|dz|be|ca)\b\S*",
                    re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Téléphone : forme internationale (+/00 puis 8 chiffres minimum) ou locale nationale.
# La variante locale commence par 0 et compte de 8 à 11 chiffres groupés par 2 ou 3 :
# elle couvre « 06 12 34 56 78 » (France) comme « 020 12 34 56 » (Tunisie).
# Contrepartie assumée : une date écrite 01/02/2023 est effacée elle aussi ; un numéro
# non effacé coûterait beaucoup plus cher qu'une date perdue dans un prompt.
PHONE_INTL_RE = re.compile(r"(?:\+|00)\d[\d\s().-]{6,}\d")
PHONE_LOCAL_RE = re.compile(r"\b0\d(?:[\s.\-]?\d){6,9}\b")

_EMAIL_MARK = "[adresse e-mail retirée]"
_PHONE_MARK = "[téléphone retiré]"
_URL_MARK = "[lien retiré]"

_PERSONAL_KEYS = ("personal_info", "location")
_ORG_FIELDS = {
    "experiences": ("company",),
    "education": ("institution",),
    "certifications": ("issuer",),
}
_ORG_LABELS = {
    "company": "une entreprise",
    "institution": "un établissement",
    "issuer": "un organisme",
}


def scrub_text(text):
    """Efface e-mails, téléphones et URL d'un texte libre (ordre important : URL avant e-mail)."""
    if not text:
        return ""
    out = str(text)
    out = URL_RE.sub(_URL_MARK, out)
    out = EMAIL_RE.sub(_EMAIL_MARK, out)
    out = PHONE_INTL_RE.sub(_PHONE_MARK, out)
    out = PHONE_LOCAL_RE.sub(_PHONE_MARK, out)
    return out


def find_pii(text):
    """Liste ce qui ressemble encore à une donnée personnelle (utilisé par les contrôles et tests)."""
    found = []
    if not text:
        return found
    for label, pattern in (("url", URL_RE), ("email", EMAIL_RE),
                           ("phone", PHONE_INTL_RE), ("phone", PHONE_LOCAL_RE)):
        if pattern.search(text):
            found.append(label)
    return found


def _scrub_item(item, section):
    if not isinstance(item, dict):
        return item
    out = {k: v for k, v in item.items() if k not in _PERSONAL_KEYS}
    for field in _ORG_FIELDS.get(section, ()):
        if out.get(field):
            if cfg.REDACT_ORGS:
                out[field] = _ORG_LABELS.get(field, "[entité retirée]")
            else:
                out[field] = scrub_text(out[field])
    for key, value in out.items():
        if isinstance(value, str):
            out[key] = scrub_text(value)
    return out


def anonymize_cv(cv_data):
    """
    Copie anonymisée du CV prête pour un prompt : sans identité, sans lieu,
    sans texte contenant e-mail / téléphone / URL.
    """
    cv = clean_cv(cv_data or {})
    result = {"target_title": cv["personal_info"].get("title")}
    profile = cv.get("profile")
    result["profile"] = scrub_text(profile) if profile else None
    for section in ("education", "experiences", "projects", "skills", "languages", "certifications"):
        result[section] = [_scrub_item(item, section) for item in cv.get(section) or []]
    result["interests"] = [scrub_text(i) for i in cv.get("interests") or []]
    return result


def target_title_of(cv_data):
    """Intitulé du poste visé, lu dans le CV avant son anonymisation (préremplissage du formulaire)."""
    cv = clean_cv(cv_data or {})
    return scrub_text(cv["personal_info"].get("title")) or None


def _line(label, value):
    return f"{label} : {value}" if value else None


def cv_digest(cv_data):
    """
    Représentation texte compacte et anonymisée du CV, injectée dans le prompt de questions.
    Bornée à MAX_CV_DIGEST_CHARS : un CV complet dépasse rarement cette limite utile.
    """
    from interview_adam.security import clip  # local : évite un cycle d'import au chargement

    cv = anonymize_cv(cv_data)
    lines = []

    if cv.get("profile"):
        lines.append(f"[RÉSUMÉ] {cv['profile']}")

    if cv.get("education"):
        lines.append("[FORMATION]")
        for edu in cv["education"][:6]:
            period = " ".join(x for x in (edu.get("start"), edu.get("end")) if x)
            lines.append("- " + " | ".join(
                x for x in (_line("diplôme", edu.get("degree")), _line("domaine", edu.get("field")),
                            _line("établissement", edu.get("institution")), period) if x))

    if cv.get("experiences"):
        lines.append("[EXPÉRIENCES]")
        for exp in cv["experiences"][:8]:
            period = " ".join(x for x in (exp.get("start"), exp.get("end")) if x)
            lines.append("- " + " | ".join(
                x for x in (_line("poste", exp.get("role")), _line("entreprise", exp.get("company")),
                            period, _line("missions", exp.get("description"))) if x))

    if cv.get("projects"):
        lines.append("[PROJETS]")
        for project in cv["projects"][:8]:
            tech = ", ".join(project.get("technologies") or [])
            lines.append("- " + " | ".join(
                x for x in (_line("nom", project.get("name")), _line("technologies", tech),
                            _line("description", project.get("description"))) if x))

    if cv.get("skills"):
        groups = [f"{g.get('category')} : {', '.join(g.get('items') or [])}" for g in cv["skills"] if g.get("items")]
        if groups:
            lines.append("[COMPÉTENCES] " + " ; ".join(groups))

    if cv.get("languages"):
        names = [f"{l.get('name')} ({l['level']})" if l.get("level") else l.get("name")
                 for l in cv["languages"] if l.get("name")]
        if names:
            lines.append("[LANGUES] " + ", ".join(names))

    return clip("\n".join(x for x in lines if x), cfg.MAX_CV_DIGEST_CHARS)


def assert_anonymized(text, context="prompt"):
    """
    Garde-fou appelé avant chaque appel au modèle : n'envoie rien si une PII a survécu.
    Une exception ici est un bug du module, pas une erreur utilisateur.
    """
    leftovers = find_pii(text)
    if leftovers:
        raise PrivacyError(
            f"confidentialité : données personnelles résiduelles dans le {context} "
            f"({', '.join(sorted(set(leftovers)))})")
    return True
