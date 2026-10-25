"""
Tout ce qui concerne le LaTeX du CV.

Principe :
- Le préambule (packages + macros) est FIXE et ajouté par Python.
- Le modèle fine-tuné génère uniquement le CORPS du document, avec un
  petit ensemble de macros (\\cvheader, \\section, \\cventry, ...).
- Les données sont échappées pour LaTeX AVANT d'être données au modèle :
  le modèle n'a qu'à recopier les valeurs, jamais à échapper lui-même.
- `render_body` produit exactement le format attendu. Il sert à créer les
  réponses du dataset et de solution de secours si la sortie du modèle
  est invalide.
"""

import re

from cv_schema import LIST_SECTIONS, ITEM_FIELDS


# ----------------------------------------------------------------------
# Préambule fixe
# ----------------------------------------------------------------------

PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[french]{babel}
\usepackage{lmodern}
\usepackage[a4paper,margin=1.7cm]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}

\definecolor{accent}{RGB}{31,78,121}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlist[itemize]{label=\textbullet,leftmargin=1.3em,itemsep=1pt,topsep=2pt,parsep=0pt}
\titleformat{\section}{\large\bfseries\color{accent}}{}{0em}{}[\vspace{-0.7em}\textcolor{accent}{\rule{\linewidth}{0.6pt}}]
\titlespacing*{\section}{0pt}{10pt}{6pt}

% \cvheader{Nom complet}{Titre (peut être vide)}{Contacts}
\newcommand{\cvheader}[3]{%
  \begin{center}
    {\LARGE\bfseries #1}\par\smallskip
    \if\relax\detokenize{#2}\relax\else{\large\color{accent}#2}\par\smallskip\fi
    {\small #3}
  \end{center}}
\newcommand{\cvsep}{\enspace|\enspace}
% \cventry{Intitulé}{Dates}{Établissement / Entreprise}{Lieu}
\newcommand{\cventry}[4]{%
  \textbf{#1}\hfill{\small #2}\par
  \if\relax\detokenize{#3#4}\relax\else\textit{#3}\hfill{\small\textit{#4}}\par\fi
  \smallskip}
% \cvproject{Nom}{Technologies (peut être vide)}
\newcommand{\cvproject}[2]{%
  \textbf{#1}\if\relax\detokenize{#2}\relax\else\ -- {\small\textit{#2}}\fi\par}
% \cvskill{Catégorie}{Éléments}
\newcommand{\cvskill}[2]{\textbf{#1} : #2\par}
"""

DOCUMENT_START = "\\begin{document}\n"
DOCUMENT_END = "\n\\end{document}\n"


def wrap_document(body):
    return PREAMBLE + "\n" + DOCUMENT_START + body.strip() + DOCUMENT_END


# ----------------------------------------------------------------------
# Échappement
# ----------------------------------------------------------------------

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_ESCAPE_RE = re.compile("|".join(re.escape(k) for k in _ESCAPES))


def escape(text):
    if text is None:
        return None
    text = str(text).replace("\u2019", "'")
    return _ESCAPE_RE.sub(lambda m: _ESCAPES[m.group(0)], text)


def escape_cv(data):
    """Copie du CV dont toutes les chaînes sont échappées pour LaTeX."""

    def walk(value):
        if isinstance(value, str):
            return escape(value)
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    return walk(data)


# ----------------------------------------------------------------------
# Règles de rédaction (identiques pour le dataset et le secours)
# ----------------------------------------------------------------------

SECTION_TITLES = {
    "profile": "Profil",
    "education": "Formation",
    "experiences": "Expériences professionnelles",
    "projects": "Projets",
    "skills": "Compétences",
    "languages": "Langues",
    "certifications": "Certifications",
    "interests": "Centres d'intérêt",
}


def lower_first(text):
    if not text:
        return text
    # Ne pas toucher aux sigles et niveaux (ex. "BTS", "IoT", "C1", "B2").
    first_word = text.split()[0]
    if len(first_word) > 1 and not first_word[1].islower():
        return text
    return text[0].lower() + text[1:]


def join_fr(items):
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " et " + items[-1]


def format_dates(start, end):
    if start and end:
        return f"{start} -- {end}"
    if end:
        return end
    if start:
        return f"Depuis {start}"
    return ""


def degree_label(edu):
    degree, field = edu.get("degree"), edu.get("field")
    if degree and field:
        return f"{degree} en {lower_first(field)}"
    return degree or field or ""


def _is_ongoing(edu, current_year=2026):
    end = edu.get("end") or ""
    if not end:
        return True
    if re.search(r"cours|présent|actuel|aujourd", end, re.IGNORECASE):
        return True
    years = re.findall(r"\d{4}", end)
    return bool(years) and int(years[-1]) >= current_year


def build_profile(data):
    """Résumé factuel construit uniquement à partir des données fournies."""

    sentences = []
    info = data["personal_info"]
    education = data["education"]

    if education:
        edu = education[0]
        label = lower_first(degree_label(edu))
        inst = edu.get("institution")
        place = f" à {inst}" if inst else ""
        if label and not edu.get("degree"):
            sentences.append(f"Formation en {label}{place}.")
        elif label and _is_ongoing(edu):
            sentences.append(f"Actuellement en {label}{place}.")
        elif label:
            obtained = "obtenue" if label.startswith("licence") else "obtenu"
            year = re.findall(r"\d{4}", edu.get("end") or "")
            when = f" en {year[-1]}" if year else ""
            sentences.append(f"{label[0].upper() + label[1:]} {obtained}{place}{when}.")

    skills = [item for group in data["skills"] for item in group["items"]][:4]
    if skills:
        sentences.append(f"Compétences en {join_fr(skills)}.")

    if data["experiences"]:
        exp = data["experiences"][0]
        role, company = exp.get("role"), exp.get("company")
        if role and company:
            sentences.append(f"Expérience en tant que {lower_first(role)} chez {company}.")
        elif role:
            sentences.append(f"Expérience en tant que {lower_first(role)}.")
    elif data["projects"]:
        names = [lower_first(p["name"]) for p in data["projects"][:2] if p.get("name")]
        if names:
            sentences.append(f"Réalisation de projets, notamment : {join_fr(names)}.")

    if info.get("title"):
        sentences.append(f"Objectif : {lower_first(info['title'])}.")

    return " ".join(sentences)


def description_to_bullets(description):
    """Secours : découpe une description brute en puces, sans reformuler."""
    if not description:
        return []
    parts = re.split(r"(?<=[.!?;])\s+|\s*\n\s*", description)
    bullets = []
    for part in parts:
        part = part.strip(" .;-•")
        if part:
            bullets.append(part[0].upper() + part[1:])
    return bullets


# ----------------------------------------------------------------------
# Rendu du corps du document
# ----------------------------------------------------------------------

def _itemize(bullets):
    lines = ["\\begin{itemize}"]
    lines += [f"\\item {b}" for b in bullets]
    lines.append("\\end{itemize}")
    return lines


def render_body(data, profile=None, bullets=None):
    """
    data    : CV propre ET déjà échappé.
    profile : texte du profil (échappé). None -> profil fourni ou construit.
    bullets : dict {("experiences"|"projects", index): [puces échappées]}.
              Absent -> découpage simple de la description.
    """
    bullets = bullets or {}
    info = data["personal_info"]
    lines = []

    full_name = " ".join(x for x in [info.get("first_name"), info.get("last_name")] if x)
    contacts = [info.get(k) for k in ("email", "phone", "location", "linkedin", "github")]
    contacts = " \\cvsep ".join(c for c in contacts if c)
    lines.append(f"\\cvheader{{{full_name}}}{{{info.get('title') or ''}}}{{{contacts}}}")

    profile = profile or data.get("profile") or build_profile(data)
    if profile:
        lines += ["", f"\\section{{{SECTION_TITLES['profile']}}}", profile]

    if data["education"]:
        lines += ["", f"\\section{{{SECTION_TITLES['education']}}}"]
        for edu in data["education"]:
            lines.append(
                f"\\cventry{{{degree_label(edu)}}}"
                f"{{{format_dates(edu.get('start'), edu.get('end'))}}}"
                f"{{{edu.get('institution') or ''}}}{{{edu.get('location') or ''}}}"
            )

    if data["experiences"]:
        lines += ["", f"\\section{{{SECTION_TITLES['experiences']}}}"]
        for i, exp in enumerate(data["experiences"]):
            lines.append(
                f"\\cventry{{{exp.get('role') or ''}}}"
                f"{{{format_dates(exp.get('start'), exp.get('end'))}}}"
                f"{{{exp.get('company') or ''}}}{{{exp.get('location') or ''}}}"
            )
            items = bullets.get(("experiences", i)) or description_to_bullets(exp.get("description"))
            if items:
                lines += _itemize(items)

    if data["projects"]:
        lines += ["", f"\\section{{{SECTION_TITLES['projects']}}}"]
        for i, proj in enumerate(data["projects"]):
            lines.append(f"\\cvproject{{{proj.get('name') or 'Projet'}}}{{{', '.join(proj.get('technologies') or [])}}}")
            items = bullets.get(("projects", i)) or description_to_bullets(proj.get("description"))
            if items:
                lines += _itemize(items)

    if data["skills"]:
        lines += ["", f"\\section{{{SECTION_TITLES['skills']}}}"]
        for group in data["skills"]:
            lines.append(f"\\cvskill{{{group['category']}}}{{{', '.join(group['items'])}}}")

    if data["languages"]:
        lines += ["", f"\\section{{{SECTION_TITLES['languages']}}}"]
        langs = [
            f"{l['name']} ({lower_first(l['level'])})" if l.get("level") else l["name"]
            for l in data["languages"] if l.get("name")
        ]
        lines.append(" \\cvsep ".join(langs))

    if data["certifications"]:
        lines += ["", f"\\section{{{SECTION_TITLES['certifications']}}}"]
        items = []
        for cert in data["certifications"]:
            text = cert.get("name") or ""
            if cert.get("issuer"):
                text += f" -- {cert['issuer']}"
            if cert.get("year"):
                text += f" ({cert['year']})"
            items.append(text)
        lines += _itemize(items)

    if data["interests"]:
        lines += ["", f"\\section{{{SECTION_TITLES['interests']}}}"]
        lines.append(", ".join(data["interests"]))

    return "\n".join(lines)


# ----------------------------------------------------------------------
# Validation de la sortie du modèle
# ----------------------------------------------------------------------

ALLOWED_COMMANDS = {
    "cvheader", "cvsep", "cventry", "cvproject", "cvskill", "section",
    "begin", "end", "item", "textbackslash", "textasciitilde", "textasciicircum",
}
_COMMAND_RE = re.compile(r"\\([A-Za-z]+)")


def _strip_escaped(text):
    return re.sub(r"\\[&%$#_{}]", "", text)


_PROFILE_RE = re.compile(r"(\\section\{Profil\}\n)(.*?)(?=\n\n|\n\\section|\Z)", re.DOTALL)


MACRO_ARITY = {"cvheader": 3, "cventry": 4, "cvproject": 2, "cvskill": 2, "section": 1}


def _count_groups(text, pos):
    """Nombre de groupes {...} consécutifs à partir de pos, et position de fin."""
    count = 0
    while pos < len(text) and text[pos] == "{":
        depth, i = 0, pos
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in "{}":
                i += 2
                continue
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth != 0:
            return count, pos
        count += 1
        pos = i + 1
    return count, pos


def fix_macro_arity(body):
    """Complète les macros auxquelles il manque des arguments (ex. \\cventry à 3 arguments)."""
    out, pos = [], 0
    for match in re.finditer(r"\\(cvheader|cventry|cvproject|cvskill|section)(?=\{)", body):
        if match.start() < pos:
            continue
        count, end = _count_groups(body, match.end())
        out.append(body[pos:end])
        missing = MACRO_ARITY[match.group(1)] - count
        if missing > 0:
            out.append("{}" * missing)
        pos = end
    out.append(body[pos:])
    return "".join(out)


def repair_body(body, data):
    """Corrige les écarts connus du modèle sans perdre ses reformulations."""
    body = fix_macro_arity(body)
    body = re.sub(r"\{([^{}]+?) -- \}", r"{Depuis \1}", body)  # "2025 -- " sans fin
    match = _PROFILE_RE.search(body)
    if not match:
        return body
    profile = match.group(2)
    if data.get("profile"):
        # Le résumé validé par l'utilisateur doit être recopié à l'identique.
        profile = data["profile"]
    else:
        # Pas de résumé validé : profil factuel construit à partir des données
        # (évite les erreurs du petit modèle, ex. « obtenu en 2027 » ou un objectif inventé).
        profile = build_profile(data)
    return body[:match.start(2)] + profile + body[match.end(2):]


def validate_body(body, data):
    """Retourne la liste des problèmes trouvés (vide = OK)."""
    problems = []

    if not body.lstrip().startswith("\\cvheader{"):
        problems.append("Le document ne commence pas par \\cvheader.")

    unknown = set(_COMMAND_RE.findall(body)) - ALLOWED_COMMANDS
    if unknown:
        problems.append(f"Commandes non autorisées : {sorted(unknown)}")

    depth = 0
    for char in _strip_escaped(body):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                break
    if depth != 0:
        problems.append("Accolades non équilibrées.")

    for match in re.finditer(r"\\(cvheader|cventry|cvproject|cvskill|section)(?=\{)", body):
        count, _ = _count_groups(body, match.end())
        if count != MACRO_ARITY[match.group(1)]:
            problems.append(f"\\{match.group(1)} a {count} argument(s) au lieu de {MACRO_ARITY[match.group(1)]}.")
            break

    for env in re.findall(r"\\begin\{(\w+)\}", body):
        if env != "itemize":
            problems.append(f"Environnement non autorisé : {env}")
    if body.count("\\begin{itemize}") != body.count("\\end{itemize}"):
        problems.append("itemize non fermé.")

    info = data["personal_info"]
    for key in ("first_name", "last_name", "email"):
        if info.get(key) and info[key] not in body:
            problems.append(f"Valeur absente du CV : {key}")

    # Aucun nombre (date, durée, chiffre) ne doit être inventé.
    source = str(data)
    for number in set(re.findall(r"\d+", body)):
        if number not in source:
            problems.append(f"Nombre inventé : {number}")

    # Détection des boucles de répétition.
    lines = [l for l in body.splitlines() if l.strip()]
    if lines and len(set(lines)) < len(lines) * 0.6:
        problems.append("Répétitions anormales.")

    return problems
