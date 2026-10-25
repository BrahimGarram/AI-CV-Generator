"""
Prompt du modèle générateur (Qwen3-0.6B fine-tuné).

IMPORTANT : ce fichier est utilisé à la fois par build_dataset.py,
train.py et generator.py. Le modèle voit donc exactement le même format
à l'entraînement et à l'utilisation. Si tu modifies ce fichier, il faut
régénérer le dataset et réentraîner.
"""

GENERATOR_SYSTEM_PROMPT = (
    "Tu convertis des données de CV en corps de document LaTeX. "
    "Utilise uniquement les macros \\cvheader, \\section, \\cventry, \\cvproject, "
    "\\cvskill, \\cvsep et l'environnement itemize. "
    "Recopie les valeurs exactement comme elles sont écrites (elles sont déjà échappées). "
    "Reformule les descriptions en puces professionnelles sans ajouter aucun fait, "
    "chiffre, technologie ou responsabilité. "
    "Si le profil est absent, rédige un profil court uniquement à partir des données. "
    "N'écris aucune section vide."
)


def _line(label, value):
    return f"{label}: {value}" if value else None


def format_input(data):
    """Représentation texte compacte d'un CV propre et échappé."""
    info = data["personal_info"]
    lines = ["[IDENTITE]"]
    for label, key in [
        ("prenom", "first_name"), ("nom", "last_name"), ("titre", "title"),
        ("email", "email"), ("telephone", "phone"), ("lieu", "location"),
        ("linkedin", "linkedin"), ("github", "github"),
    ]:
        lines.append(_line(label, info.get(key)))

    if data.get("profile"):
        lines += ["[PROFIL]", data["profile"]]

    def block(title, items, fields):
        if not items:
            return []
        out = [f"[{title}]"]
        for item in items:
            parts = []
            for label, key in fields:
                value = item.get(key)
                if isinstance(value, list):
                    value = ", ".join(value)
                if value:
                    parts.append(f"{label}={value}")
            out.append("- " + " | ".join(parts))
        return out

    lines += block("FORMATION", data["education"], [
        ("diplome", "degree"), ("domaine", "field"), ("etablissement", "institution"),
        ("lieu", "location"), ("debut", "start"), ("fin", "end"),
    ])
    lines += block("EXPERIENCES", data["experiences"], [
        ("poste", "role"), ("entreprise", "company"), ("lieu", "location"),
        ("debut", "start"), ("fin", "end"), ("description", "description"),
    ])
    lines += block("PROJETS", data["projects"], [
        ("nom", "name"), ("technologies", "technologies"), ("description", "description"),
    ])
    lines += block("COMPETENCES", data["skills"], [
        ("categorie", "category"), ("elements", "items"),
    ])
    lines += block("LANGUES", data["languages"], [
        ("langue", "name"), ("niveau", "level"),
    ])
    lines += block("CERTIFICATIONS", data["certifications"], [
        ("nom", "name"), ("organisme", "issuer"), ("annee", "year"),
    ])
    if data["interests"]:
        lines += ["[INTERETS]", ", ".join(data["interests"])]

    return "\n".join(l for l in lines if l)


def build_messages(escaped_data):
    return [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": format_input(escaped_data)},
    ]
