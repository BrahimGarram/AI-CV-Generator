"""
Garde-fous appliqués au CV renvoyé par le LLM.

Ils ne dirigent PAS la conversation : ils vérifient seulement que le CV ne contient
rien que l'utilisateur n'ait dit (ou accepté), et normalisent le format.
- Coordonnées (e-mail, téléphone, liens) : doivent avoir été écrites par l'utilisateur.
- Années : doivent avoir été écrites par l'utilisateur (±1 an pour une durée calculée).
- Compétences, langues, centres d'intérêt : doivent apparaître dans la conversation
  (écrits par l'utilisateur ou proposés par l'assistant puis acceptés).
- Chiffres dans les descriptions : doivent apparaître dans la conversation.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from cv_schema import LIST_SECTIONS, PERSONAL_FIELDS, clean_cv

# ----------------------------------------------------------------------
# Outils de texte
# ----------------------------------------------------------------------


def ascii_lower(text):
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()


def norm(text):
    return re.sub(r"[^a-z0-9+#]", "", ascii_lower(text)) if text else ""


GENERIC_WORDS = {"etudiant", "etudiante", "informatique", "formation", "ecole", "universite", "institut",
                 "superieur", "stage", "tunisie", "dans", "pour", "avec", "les", "des", "une", "est", "sur"}


def mentioned(value, text):
    """Au moins un mot significatif de `value` apparaît dans `text` (5 premières lettres)."""
    if not value:
        return False
    haystack = ascii_lower(text)
    words = [w for w in re.findall(r"[a-z0-9+#]+", ascii_lower(value))
             if (len(w) >= 3 or any(c.isdigit() for c in w)) and w not in GENERIC_WORDS]
    return any(w[:5] in haystack for w in words)


NOT_SKILLS = {"informatique", "ingenieur", "ingenierie", "genielogiciel", "etudiant", "developpement",
              "stage", "esprit"}


def skill_mentioned(skill, text):
    """Compétence présente dans le texte, fautes de frappe tolérées ('flutyter', 'langraph')."""
    target = norm(skill)
    if not target or target in NOT_SKILLS:
        return False
    if len(target) <= 2:  # "C", "R", "Go" : mot exact (pas le "c" de "c'est")
        return bool(re.search(rf"(?<![a-z0-9+#'’]){re.escape(ascii_lower(skill))}(?![a-z0-9+#'’])",
                              ascii_lower(text)))
    if target in norm(text):
        return True
    words = re.findall(r"[a-z0-9+#.]+", ascii_lower(text))
    grams = {"".join(words[i:i + n]).replace(".", "") for n in (1, 2, 3) for i in range(len(words) - n + 1)}
    return any(SequenceMatcher(None, target, g).ratio() >= 0.82 for g in grams if abs(len(g) - len(target)) <= 3)


# ----------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------

MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
          "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
_MONTH_KEYS = {k: i for i, k in enumerate(
    ["janv", "fevr", "mars", "avr", "mai", "juin", "juil", "aout", "sept", "oct", "nov", "dec"], start=1)}


def parse_month_year(value):
    """'Août 2025', 'aout 2025', '08/2025', '2025-08' -> (8, 2025). Année seule -> (None, 2025)."""
    if not value:
        return None
    text = ascii_lower(value)
    year = re.search(r"(19|20)\d{2}", text)
    if not year:
        return None
    year = int(year.group(0))
    m = re.search(r"\b(0?[1-9]|1[0-2])\s*[/-]\s*(19|20)\d{2}\b", text) or \
        re.search(r"\b(19|20)\d{2}\s*[/-]\s*(0?[1-9]|1[0-2])\b", text)
    if m:
        return (min(int(n) for n in re.findall(r"\d+", m.group(0))), year)
    for key, number in _MONTH_KEYS.items():
        if re.search(rf"\b{key}", text):
            return (number, year)
    if re.search(r"\bout\b", text):  # faute fréquente : "out 2025" = août
        return (8, year)
    return (None, year)


def format_month_year(parsed):
    month, year = parsed
    return f"{MONTHS[month - 1]} {year}" if month else str(year)


def _check_date(value, user_text):
    """Date valide si ses années ont été écrites (±1 an : fin calculée à partir d'une durée)."""
    if not value:
        return None
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", value)]
    if not years:
        ongoing = re.search(r"actuel|en cours|aujourd|toujours|pr[eé]sent|maintenant", user_text, re.IGNORECASE)
        return value if ongoing or norm(value) in norm(user_text) else None
    written = {int(y) for y in re.findall(r"(?:19|20)\d{2}", user_text)}
    if not all(y in written or y - 1 in written for y in years):
        return None
    parsed = parse_month_year(value)
    return format_month_year(parsed) if parsed else value


def _remove_invented_numbers(text, conversation):
    if not text:
        return text
    known = set(re.findall(r"\d+", conversation))
    if all(n in known for n in re.findall(r"\d+", text)):
        return text
    kept = [s for s in re.split(r"(?<=[.;])\s+", text) if all(n in known for n in re.findall(r"\d+", s))]
    return " ".join(kept) or None


# ----------------------------------------------------------------------
# Compétences
# ----------------------------------------------------------------------

_CANONICAL = [
    "Spring Boot", "Spring", "Angular", "React", "Vue.js", "Next.js", "Flutter", "React Native", "Django",
    "Flask", "FastAPI", "Laravel", "Symfony", "Express", "Node.js", "NestJS", ".NET", "Hibernate", "Bootstrap",
    "Tailwind CSS", "LangChain", "LangGraph", "TensorFlow", "PyTorch", "Java", "Python", "JavaScript",
    "TypeScript", "SQL", "PHP", "Dart", "Kotlin", "Swift", "C++", "C#", "HTML", "CSS", "Git", "GitHub",
    "Docker", "Kubernetes", "MySQL", "PostgreSQL", "MongoDB", "Oracle", "Firebase", "Linux", "Jenkins",
    "AWS", "Azure", "Power BI", "Pandas", "NumPy", "scikit-learn", "Scrum", "OCR",
]
CANONICAL_SKILLS = {norm(s): s for s in _CANONICAL}
FRAMEWORKS = {norm(s) for s in _CANONICAL[:24]}
LANGUAGE_CATEGORIES = {norm("Langages"), norm("Langages de programmation"), norm("Langage")}


def _fix_skills(cv):
    for group in cv["skills"]:
        group["items"] = [CANONICAL_SKILLS.get(norm(i), i[0].upper() + i[1:] if i.islower() else i)
                          for i in group["items"]]
    misplaced = []
    for group in cv["skills"]:
        if norm(group["category"]) in LANGUAGE_CATEGORIES:
            misplaced += [i for i in group["items"] if norm(i) in FRAMEWORKS]
            group["items"] = [i for i in group["items"] if norm(i) not in FRAMEWORKS]
    if misplaced:
        target = next((g for g in cv["skills"] if norm(g["category"]) == norm("Frameworks")), None)
        if target is None:
            target = {"category": "Frameworks", "items": []}
            cv["skills"].append(target)
        target["items"] = misplaced + target["items"]
    seen = set()
    for group in cv["skills"]:
        group["items"] = [i for i in group["items"] if not (norm(i) in seen or seen.add(norm(i)))]
    cv["skills"] = [g for g in cv["skills"] if g["items"]]


# ----------------------------------------------------------------------
# Doublons
# ----------------------------------------------------------------------

def _company_key(name):
    """'ETAP centre ville', "D'étap", 'etap' -> 'etap'."""
    text = ascii_lower(name or "")
    text = re.sub(r"^(d['’ ]|l['’ ]|la |le |chez |a |au )", "", text)
    return norm(text.split()[0]) if text.split() else ""


def _merge_duplicate_experiences(cv):
    merged = []
    for exp in cv["experiences"]:
        key = _company_key(exp.get("company"))
        twin = next((m for m in merged if key and _company_key(m.get("company")) == key), None)
        if twin is None:
            merged.append(exp)
            continue
        for field, value in exp.items():
            if value and not twin.get(field):
                twin[field] = value
            elif field == "description" and value and len(value) > len(twin.get(field) or ""):
                twin[field] = value
    cv["experiences"] = merged


def _remove_projects_that_are_internships(cv):
    exp_texts = {norm(e.get(k)) for e in cv["experiences"] for k in ("role", "description") if e.get(k)}
    cv["projects"] = [p for p in cv["projects"]
                      if norm(p.get("name")) not in exp_texts and norm(p.get("description")) not in exp_texts]


# ----------------------------------------------------------------------
# Point d'entrée
# ----------------------------------------------------------------------

GROUNDED_CONTACTS = ("email", "phone", "linkedin", "github")


def sanitize(new_cv, previous_cv, user_text, conversation_text):
    """
    new_cv            : CV complet renvoyé par le LLM.
    previous_cv       : CV du tour précédent (valeurs gardées si le LLM invente).
    user_text         : tout ce que l'utilisateur a écrit.
    conversation_text : utilisateur + assistant (suggestions acceptées).
    Retourne (cv_propre, liste_des_corrections).
    """
    cv = clean_cv(new_cv)
    removed = []

    # Coordonnées et nom : écrits par l'utilisateur.
    info, old_info = cv["personal_info"], previous_cv["personal_info"]
    for field in PERSONAL_FIELDS:
        value = info[field]
        if not value:
            continue
        if field in GROUNDED_CONTACTS:
            ok = norm(value) in norm(user_text) or (field == "phone" and re.sub(r"\D", "", value)
                                                    in re.sub(r"\D", "", user_text))
        elif field in ("first_name", "last_name"):
            ok = all(mentioned(w, user_text) for w in value.split() if len(w) >= 3)
        else:
            ok = True
        if not ok:
            removed.append(f"{field}={value}")
            info[field] = old_info.get(field)

    # Dates.
    for section, fields in (("education", ("start", "end")), ("experiences", ("start", "end")),
                            ("certifications", ("year",))):
        for item in cv[section]:
            for field in fields:
                checked = _check_date(item.get(field), user_text)
                if item.get(field) and not checked:
                    removed.append(f"{section}.{field}={item[field]}")
                item[field] = checked

    # Entreprises / établissements : écrits par l'utilisateur.
    for exp in cv["experiences"]:
        if exp.get("company") and not mentioned(exp["company"], user_text):
            removed.append(f"company={exp['company']}")
            exp["company"] = None
    cv["education"] = [e for e in cv["education"]
                       if mentioned(e.get("institution"), user_text) or mentioned(e.get("degree"), user_text)
                       or mentioned(e.get("field"), user_text)]

    # Compétences, langues, intérêts, certifications : présents dans la conversation.
    for group in cv["skills"]:
        kept = [i for i in group["items"] if skill_mentioned(i, conversation_text)]
        removed += [f"skill={i}" for i in group["items"] if i not in kept]
        group["items"] = kept
    cv["languages"] = [l for l in cv["languages"] if mentioned(l.get("name"), conversation_text)]
    for lang in cv["languages"]:
        lang["name"] = lang["name"][0].upper() + lang["name"][1:]
        if lang.get("level") and not mentioned(lang["level"], conversation_text):
            lang["level"] = None
    cv["interests"] = [i for i in cv["interests"] if mentioned(i, conversation_text)]
    cv["certifications"] = [c for c in cv["certifications"] if mentioned(c.get("name"), user_text)]
    cert_names = [norm(c["name"]) for c in cv["certifications"] if c.get("name")]
    for group in cv["skills"]:
        group["items"] = [i for i in group["items"] if norm(i) not in cert_names]

    # Chiffres inventés dans les textes rédigés.
    cv["profile"] = _remove_invented_numbers(cv["profile"], conversation_text)
    for section in ("experiences", "projects"):
        for item in cv[section]:
            item["description"] = _remove_invented_numbers(item.get("description"), conversation_text)

    # Normalisation.
    for section, keys in (("experiences", ("company", "location")), ("education", ("institution", "location"))):
        for item in cv[section]:
            for key in keys:
                if item.get(key) and item[key].islower():
                    item[key] = item[key][0].upper() + item[key][1:]
    _merge_duplicate_experiences(cv)
    _remove_projects_that_are_internships(cv)
    _fix_skills(cv)

    return clean_cv(cv), removed


__all__ = ["sanitize", "parse_month_year", "format_month_year", "LIST_SECTIONS"]
