"""
Construit le dataset de fine-tuning : données du CV -> corps LaTeX.

    python build_dataset.py --train 700 --val 60

Les réponses (cibles) sont produites par latex.render_body : elles sont
donc toujours cohérentes, complètes et du LaTeX valide. Une partie des
projets / expériences est réservée à la validation pour vérifier que le
modèle sait reformuler des descriptions qu'il n'a jamais vues.
"""

import argparse
import json
import random
import unicodedata
from pathlib import Path

import dataset_pools as P
from cv_schema import empty_cv, clean_cv
from latex import escape, escape_cv, render_body
from prompts import build_messages

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.lower().replace(" ", "")


def split_pool(items, rng, val_ratio=0.2):
    """Sépare une liste en (train, val). Au moins un élément de chaque côté si possible."""
    items = list(items)
    rng.shuffle(items)
    n_val = max(1, int(len(items) * val_ratio)) if len(items) >= 3 else 0
    return items[n_val:], items[:n_val]


def build_pools(seed):
    rng = random.Random(seed)
    pools = {"train": {}, "val": {}}
    for name, track in P.TRACKS.items():
        p_train, p_val = split_pool(track["projects"], rng)
        e_train, e_val = split_pool(track["experiences"], rng)
        pools["train"][name] = {"projects": p_train, "experiences": e_train}
        # La validation utilise surtout des éléments jamais vus.
        pools["val"][name] = {
            "projects": p_val or p_train,
            "experiences": e_val or e_train,
        }
    return pools


def random_year_range(rng, length, end_max=2027):
    end = rng.randint(2019, end_max)
    return str(end - length), str(end)


def random_month_date(rng, year, style=None):
    style = rng.choice(["month", "month", "month", "numeric", "year"]) if style is None else style
    if style == "month":
        return f"{rng.choice(P.MONTHS)} {year}"
    if style == "numeric":
        return f"{rng.randint(1, 12):02d}/{year}"
    return str(year)


def make_person(rng, data):
    first = rng.choice(P.FIRST_NAMES)
    if rng.random() < 0.25:  # prénom composé : "Mohamed Brahim"
        second = rng.choice(P.FIRST_NAMES)
        if second != first:
            first = f"{first} {second}"
    last = rng.choice(P.LAST_NAMES)
    if rng.random() < 0.1:   # nom composé
        last = f"{last} {rng.choice(P.LAST_NAMES)}"
    info = data["personal_info"]
    info["first_name"], info["last_name"] = first, last

    # E-mail : souvent SANS lien avec le nom, pour que le modèle apprenne
    # à le recopier et non à le reconstruire à partir du nom.
    other = slug(rng.choice(P.FIRST_NAMES))
    first_part, last_part = slug(first.split()[-1]), slug(last.split()[0])
    user = rng.choice([
        f"{slug(first.split()[0])}.{slug(last)}",
        f"{first_part}{rng.randint(1, 999)}",
        f"{other}",
        f"{other}.{last_part}",
        f"{other}{rng.randint(1, 99)}",
        f"{rng.choice(['dev', 'pro', 'contact', 'its', 'mr', 'the'])}{other}",
        f"{last_part}_{other[:3]}",
        "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(4, 9))),
    ])
    info["email"] = f"{user}@{rng.choice(P.EMAIL_DOMAINS)}"

    tunisian = rng.random() < 0.8
    if rng.random() < 0.7:
        if tunisian:
            info["phone"] = f"+216 {rng.randint(20, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}"
        else:
            info["phone"] = "+33 6 " + " ".join(f"{rng.randint(0, 99):02d}" for _ in range(4))
    if rng.random() < 0.6:
        info["location"] = rng.choice(P.CITIES_TN if tunisian else P.CITIES_FR)
    if rng.random() < 0.35:
        info["linkedin"] = f"linkedin.com/in/{slug(first)}-{slug(last)}"
    if rng.random() < 0.35:
        info["github"] = f"github.com/{rng.choice([slug(first) + slug(last)[:3], slug(first) + '_dev', slug(last) + str(rng.randint(1, 99))])}"
    return info


def make_education(rng, track):
    field = rng.choice(track["fields"])
    inst, city = rng.choice(P.INSTITUTIONS)
    level = rng.random()
    if level < 0.4:
        degree, length = rng.choice(["Cycle ingénieur", "Diplôme d'ingénieur"]), 3
    elif level < 0.65:
        degree, length = rng.choice(["Licence", "Licence appliquée", "Licence fondamentale"]), 3
    elif level < 0.9:
        degree, length = rng.choice(["Master", "Master de recherche", "Mastère professionnel"]), 2
    else:
        degree, length = rng.choice(["BTS", "Doctorat"]), rng.choice([2, 3])

    start, end = random_year_range(rng, length)
    edu = {
        "degree": degree,
        "field": field if rng.random() < 0.9 else None,
        "institution": inst,
        "location": city if rng.random() < 0.5 else None,
        "start": start if rng.random() < 0.75 else None,
        "end": end if rng.random() < 0.85 else None,
    }
    if edu["end"] and int(end) >= 2026 and rng.random() < 0.3:
        edu["end"] = "En cours"

    result = [edu]
    if rng.random() < 0.35:
        bac_year = str(int(start) - rng.choice([1, 2, 3]))
        result.append({
            "degree": "Baccalauréat",
            "field": rng.choice(P.BAC_FIELDS),
            "institution": rng.choice(P.LYCEES),
            "location": None,
            "start": None,
            "end": bac_year,
        })
    return result


def make_skills(rng, track):
    categories = list(track["skills"].items())
    rng.shuffle(categories)
    groups = []
    for category, items in categories[: rng.randint(1, min(4, len(categories)))]:
        chosen = rng.sample(items, rng.randint(1, min(5, len(items))))
        groups.append({"category": category, "items": chosen})
    if rng.random() < 0.2:
        groups.append({"category": "Soft skills", "items": rng.sample(P.SOFT_SKILLS, rng.randint(2, 4))})
    return groups


PROFILE_OPENERS = [
    "{deg} à {inst}, avec de solides bases en {skills}.",
    "Profil {field} formé à {inst}, maîtrisant {skills}.",
    "Formation en {field} ({inst}) et compétences confirmées en {skills}.",
    "{deg} ({inst}), à l'aise avec {skills}.",
    "Parcours en {field} à {inst}, centré sur {skills}.",
]
PROFILE_MIDDLES = [
    "Expérience acquise en tant que {role} chez {company}.",
    "Une expérience de {role} chez {company} a permis de mettre ces compétences en pratique.",
    "Réalisation de projets concrets, dont {project}.",
    "Plusieurs projets menés, notamment {project}.",
]
PROFILE_GOALS = [
    "À la recherche d'une opportunité en tant que {title}.",
    "Souhaite évoluer vers un poste de {title}.",
    "Objectif : {title}.",
    "Motivé par les projets techniques et le travail en équipe.",
    "Intérêt marqué pour les technologies modernes et la qualité logicielle.",
]


def synthetic_profile(rng, data):
    """Résumé « déjà rédigé » (comme le ferait le LLM de conversation) : le modèle doit le recopier."""
    from latex import degree_label, join_fr, lower_first

    edu = data["education"][0]
    skills = [i for g in data["skills"] for i in g["items"]]
    values = {
        "deg": degree_label(edu) or "Formation",
        "inst": edu.get("institution") or "l'université",
        "field": lower_first(edu.get("field") or "informatique"),
        "skills": join_fr(rng.sample(skills, min(3, len(skills)))),
    }
    sentences = [rng.choice(PROFILE_OPENERS).format(**values)]
    if data["experiences"] and data["experiences"][0].get("company"):
        exp = data["experiences"][0]
        sentences.append(rng.choice(PROFILE_MIDDLES[:2]).format(
            role=lower_first(exp["role"]), company=exp["company"]))
    elif data["projects"]:
        sentences.append(rng.choice(PROFILE_MIDDLES[2:]).format(project=lower_first(data["projects"][0]["name"])))
    goals = PROFILE_GOALS if data["personal_info"]["title"] else PROFILE_GOALS[3:]
    sentences.append(rng.choice(goals).format(title=lower_first(data["personal_info"]["title"] or "")))
    return " ".join(sentences)


def make_example(rng, pools):
    track_name = rng.choice(list(P.TRACKS))
    track = P.TRACKS[track_name]
    pool = pools[track_name]
    data = empty_cv()
    bullets = {}

    make_person(rng, data)
    if rng.random() < 0.55:
        data["personal_info"]["title"] = rng.choice(track["titles"])
    data["education"] = make_education(rng, track)
    if rng.random() < 0.07:
        data["education"][0]["degree"] = None  # ex. "étudiant en informatique à ESPRIT"
    data["skills"] = make_skills(rng, track)

    # Expériences
    n_exp = rng.choices([0, 1, 2], weights=[0.35, 0.45, 0.2])[0]
    for exp in rng.sample(pool["experiences"], min(n_exp, len(pool["experiences"]))):
        company, city = rng.choice(P.COMPANIES)
        year = rng.randint(2019, 2026)
        style = rng.choice(["month", "month", "month", "numeric", "year"])
        has_desc = rng.random() < 0.9
        entry = {
            "role": exp["role"],
            "company": company,
            "location": city if rng.random() < 0.6 else None,
            "start": random_month_date(rng, year, style) if rng.random() < 0.85 else None,
            "end": None,
            "description": rng.choice(exp["raw"]) if has_desc else None,
        }
        if entry["start"]:
            end_year = year + (1 if style == "year" else rng.choice([0, 1]))
            entry["end"] = rng.choice(["Présent", random_month_date(rng, end_year, style)])
        if has_desc:
            bullets[("experiences", len(data["experiences"]))] = exp["bullets"]
        data["experiences"].append(entry)

    # Projets
    n_proj = rng.choices([0, 1, 2, 3], weights=[0.15, 0.35, 0.35, 0.15])[0]
    for proj in rng.sample(pool["projects"], min(n_proj, len(pool["projects"]))):
        has_desc = rng.random() < 0.92
        entry = {
            "name": proj["name"],
            "technologies": list(proj["technologies"]) if rng.random() < 0.85 else [],
            "description": rng.choice(proj["raw"]) if has_desc else None,
        }
        if has_desc:
            bullets[("projects", len(data["projects"]))] = proj["bullets"]
        data["projects"].append(entry)

    # Langues
    if rng.random() < 0.7:
        names = ["Arabe", "Français", "Anglais"][: rng.randint(1, 3)]
        if rng.random() < 0.3:
            names.append(rng.choice(["Allemand", "Espagnol", "Italien"]))
        data["languages"] = [{"name": n, "level": rng.choice(P.LANGUAGES[n])} for n in names]

    # Certifications
    if rng.random() < 0.3:
        for name, issuer in rng.sample(P.CERTIFICATIONS, rng.randint(1, 2)):
            data["certifications"].append({
                "name": name,
                "issuer": issuer if rng.random() < 0.8 else None,
                "year": str(rng.randint(2021, 2026)) if rng.random() < 0.7 else None,
            })

    # Centres d'intérêt
    if rng.random() < 0.4:
        data["interests"] = rng.sample(P.INTERESTS, rng.randint(1, 4))

    # Profil : surtout rédigé à l'avance (proposé par le LLM et validé par l'utilisateur),
    # parfois écrit par l'utilisateur, sinon absent (le modèle en construit un).
    choice = rng.random()
    if choice < 0.45:
        data["profile"] = synthetic_profile(rng, data)
    elif choice < 0.55:
        data["profile"] = rng.choice(P.USER_PROFILES)

    data = clean_cv(data)
    escaped = escape_cv(data)
    escaped_bullets = {k: [escape(b) for b in v] for k, v in bullets.items()}
    target = render_body(escaped, bullets=escaped_bullets)

    messages = build_messages(escaped)
    messages.append({"role": "assistant", "content": target})
    return {"messages": messages}


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=700)
    parser.add_argument("--val", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    pools = build_pools(args.seed)
    rng = random.Random(args.seed)

    def generate(n, split):
        records, seen = [], set()
        while len(records) < n:
            record = make_example(rng, pools[split])
            key = record["messages"][1]["content"]
            if key not in seen:
                seen.add(key)
                records.append(record)
        return records

    train = generate(args.train, "train")
    val = generate(args.val, "val")

    DATASET_DIR.mkdir(exist_ok=True)
    write_jsonl(DATASET_DIR / "cv_latex_train.jsonl", train)
    write_jsonl(DATASET_DIR / "cv_latex_val.jsonl", val)
    print(f"Train : {len(train)} exemples -> dataset/cv_latex_train.jsonl")
    print(f"Val   : {len(val)} exemples -> dataset/cv_latex_val.jsonl")


if __name__ == "__main__":
    main()
