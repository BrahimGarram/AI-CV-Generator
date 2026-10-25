"""
Schéma unique des données du CV.

Ce schéma est utilisé partout :
- par l'extracteur (Ollama 8B) qui remplit les données ;
- par le générateur de dataset ;
- par le modèle fine-tuné qui transforme ces données en LaTeX.
"""

import copy
import re


def empty_cv():
    return {
        "personal_info": {
            "first_name": None,
            "last_name": None,
            "title": None,        # poste visé / intitulé, ex. "Développeur Full-Stack"
            "email": None,
            "phone": None,
            "location": None,
            "linkedin": None,
            "github": None,
        },
        "profile": None,          # résumé écrit par l'utilisateur (sinon le modèle en rédige un)
        "education": [],          # {degree, field, institution, location, start, end}
        "experiences": [],        # {role, company, location, start, end, description}
        "projects": [],           # {name, description, technologies[]}
        "skills": [],             # {category, items[]}
        "languages": [],          # {name, level}
        "certifications": [],     # {name, issuer, year}
        "interests": [],          # [str]
    }


PERSONAL_FIELDS = list(empty_cv()["personal_info"].keys())
LIST_SECTIONS = [
    "education", "experiences", "projects", "skills",
    "languages", "certifications", "interests",
]

ITEM_FIELDS = {
    "education": ["degree", "field", "institution", "location", "start", "end"],
    "experiences": ["role", "company", "location", "start", "end", "description"],
    "projects": ["name", "description", "technologies"],
    "skills": ["category", "items"],
    "languages": ["name", "level"],
    "certifications": ["name", "issuer", "year"],
}

# Clé utilisée pour reconnaître le même élément (fusion / correction).
ITEM_KEYS = {
    "education": ["degree", "institution"],
    "experiences": ["role", "company"],
    "projects": ["name"],
    "skills": ["category"],
    "languages": ["name"],
    "certifications": ["name"],
}

# Champs indispensables pour générer le CV.
REQUIRED = [
    "personal_info.first_name",
    "personal_info.last_name",
    "personal_info.email",
    "education",
    "skills",
]

LABELS = {
    "personal_info.first_name": "ton prénom",
    "personal_info.last_name": "ton nom de famille",
    "personal_info.email": "ton adresse e-mail",
    "education": "ta formation (diplôme, spécialité, établissement, années)",
    "skills": "tes compétences techniques",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ----------------------------------------------------------------------
# Accès aux champs
# ----------------------------------------------------------------------

def get_field(data, path):
    value = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def is_filled(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def missing_required(data):
    return [path for path in REQUIRED if not is_filled(get_field(data, path))]


# ----------------------------------------------------------------------
# Nettoyage
# ----------------------------------------------------------------------

def _clean_str(value):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r"\s+", " ", value).strip()
    if value.lower() in {"", "null", "none", "n/a", "aucun", "aucune", "inconnu"}:
        return None
    return value


def _clean_str_list(values):
    if values is None:
        return []
    if isinstance(values, str):
        values = re.split(r"[,;]", values)
    result = []
    seen = set()
    for item in values:
        item = _clean_str(item)
        if item and item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return result


def clean_item(section, item):
    """Normalise un élément d'une section de liste. Retourne None s'il est vide."""
    if section == "interests":
        return _clean_str(item)

    if not isinstance(item, dict):
        return None

    cleaned = {}
    for field in ITEM_FIELDS[section]:
        if field in ("technologies", "items"):
            cleaned[field] = _clean_str_list(item.get(field))
        else:
            cleaned[field] = _clean_str(item.get(field))

    if section == "skills" and not cleaned["items"]:
        return None
    if section == "skills" and not cleaned["category"]:
        cleaned["category"] = "Compétences"

    useful = [v for k, v in cleaned.items() if is_filled(v)]
    return cleaned if useful else None


def clean_cv(data):
    """Retourne une copie propre et complète du CV (toutes les clés présentes)."""
    result = empty_cv()
    data = data or {}

    personal = data.get("personal_info") or {}
    for field in PERSONAL_FIELDS:
        result["personal_info"][field] = _clean_str(personal.get(field))

    email = result["personal_info"]["email"]
    if email and not EMAIL_RE.fullmatch(email):
        result["personal_info"]["email"] = None

    result["profile"] = _clean_str(data.get("profile"))

    for section in LIST_SECTIONS:
        items = data.get(section) or []
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item = clean_item(section, item)
            if item is not None:
                result[section].append(item)

    return result


def copy_cv(data):
    return copy.deepcopy(data)
