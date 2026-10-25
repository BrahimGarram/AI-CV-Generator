"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Découpage de la base de connaissances (`interview_adam/knowledge/*.md`) en fragments
indexables.

Format volontairement minimal, tenu par la documentation des fichiers eux-mêmes :

    ---
    domain: web-dev            # front matter : domaine par défaut du fichier
    ---

    ## Titre du fragment       # un fragment = une section de niveau 2
    type: question             # question | guideline | rubric
    difficulty: intermediate   # junior | intermediate | senior
    tags: fastapi, pydantic    # libre, sert surtout au debug et au CLI de recherche

    Corps du fragment, en anglais, plusieurs paragraphes.

L'identifiant d'un fragment est dérivé du nom de fichier et du titre (`web-dev/mon-titre`) :
il est donc stable entre deux exécutions, ce qui rend l'ingestion idempotente — réindexer
le même markdown produit exactement les mêmes clés, et le comparatif de l'ingestion peut
signaler un titre qui change au lieu de créer un doublon silencieux.

Aucune dépendance externe : ce module doit rester importable même sans torch ni faiss.
"""

import re
from dataclasses import dataclass
from pathlib import Path

TYPES = ("question", "guideline", "rubric")
DIFFICULTIES = ("junior", "intermediate", "senior")

DEFAULT_TYPE = "guideline"
DEFAULT_DIFFICULTY = "intermediate"

# Un titre de fragment est une ligne qui commence par exactement deux dièses : les titres
# de niveau 3 restent dans le corps du fragment qui les précède.
_HEADING = re.compile(r"^##\s+(?![#])(.+?)\s*$")
_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_META_LINE = re.compile(r"^(type|difficulty|tags|domain)\s*:\s*(.+?)\s*$")
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class AdamChunk:
    """
    Un fragment indexé. `text` est le corps seul (ce qu'on montre au modèle) ;
    `embedding_text` ajoute le titre et les étiquettes, parce qu'un chunk sans son
    intitulé perd une partie du signal récupérable par similarité.
    """

    id: str
    domain: str
    title: str
    type: str
    difficulty: str
    tags: tuple
    text: str
    source: str

    @property
    def embedding_text(self):
        return "\n".join((
            self.title,
            f"domain: {self.domain}",
            f"type: {self.type}",
            f"difficulty: {self.difficulty}",
            ", ".join(self.tags),
            self.text,
        ))

    @property
    def label(self):
        return f"{self.domain} / {self.type} / {self.difficulty}"

    def as_record(self):
        """Version sérialisable, écrite dans le fichier de méta de l'index."""
        return {"id": self.id, "domain": self.domain, "title": self.title, "type": self.type,
                "difficulty": self.difficulty, "tags": list(self.tags), "text": self.text,
                "source": self.source}


def slugify(value, limit=60):
    """Normalise un titre en identifiant lisible : « N+1 queries & ORM » -> « n-1-queries-orm »."""
    slug = _SLUG_STRIP.sub("-", (value or "").lower()).strip("-")
    return (slug[:limit].rstrip("-")) or "chunk"


def _clean_metadata(values):
    """
    Les étiquettes du fragment sont des valeurs contrôlées : une faute de frappe dans
    « rubric » ne doit pas inventer un quatrième type que les filtres ne connaissent pas.
    """
    chunk_type = values.get("type", DEFAULT_TYPE).lower()
    if chunk_type not in TYPES:
        chunk_type = DEFAULT_TYPE
    difficulty = values.get("difficulty", DEFAULT_DIFFICULTY).lower()
    if difficulty not in DIFFICULTIES:
        difficulty = DEFAULT_DIFFICULTY
    tags = tuple(t.strip().lower() for t in values.get("tags", "").split(",") if t.strip())
    return chunk_type, difficulty, tags


def parse_document(path):
    """
    Lit un fichier markdown et rend la liste de ses fragments. Le domaine du front matter
    s'applique à tout le fichier ; un fragment peut le surcharger avec sa propre ligne
    `domain:` (utile pour une note à cheval sur deux domaines).
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")

    file_domain = path.stem.lower().replace("_", "-")
    front = _FRONT_MATTER.match(raw)
    if front:
        for line in front.group(1).splitlines():
            found = _META_LINE.match(line.strip())
            if found and found.group(1) == "domain":
                file_domain = found.group(2).lower().replace("_", "-")
        raw = raw[front.end():]

    chunks = []
    sections = []
    current = None
    for line in raw.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = {"title": heading.group(1), "meta": [], "body": [], "in_body": False}
            sections.append(current)
            continue
        if current is None:
            continue            # avant-texte du fichier : de la doc pour l'humain, pas indexée
        if current["in_body"]:
            current["body"].append(line)
            continue
        stripped = line.strip()
        found = _META_LINE.match(stripped)
        if found:
            current["meta"].append((found.group(1), found.group(2)))
        elif stripped:
            current["in_body"] = True     # première ligne de prose : les étiquettes sont finies
            current["body"].append(line)

    for section in sections:
        chunks.append(_build(section, file_domain, path))
    return file_domain, chunks


def _build(section, file_domain, path):
    values = dict(section["meta"])
    domain = values.get("domain", file_domain).lower().replace("_", "-")
    chunk_type, difficulty, tags = _clean_metadata(values)
    text = "\n".join(section["body"]).strip()
    return AdamChunk(
        id=f"{slugify(path.stem)}/{slugify(section['title'])}",
        domain=domain,
        title=section["title"],
        type=chunk_type,
        difficulty=difficulty,
        tags=tags,
        text=text,
        source=path.name,
    )


def load_chunks(knowledge_dir=None):
    """
    Tous les fragments du répertoire de connaissances, dans un ordre déterministe
    (nom de fichier puis position dans le fichier) : c'est cet ordre qui rend
    l'ingestion reproductible et donc comparables deux index successifs.
    """
    from interview_adam import config_adam as cfg

    directory = Path(knowledge_dir) if knowledge_dir else cfg.KNOWLEDGE_DIR
    documents = sorted(directory.glob("*.md"))
    chunks = []
    for document in documents:
        _, parsed = parse_document(document)
        for chunk in parsed:
            if chunk.text:
                chunks.append(chunk)

    seen = {}
    for chunk in chunks:
        if chunk.id in seen:
            raise ValueError(f"Identifiant de fragment dupliqué : {chunk.id} "
                             f"(deux titres identiques dans {chunk.source})")
        seen[chunk.id] = chunk
    return chunks


def describe(chunk_lists):
    """Résumé « domaine -> type -> nombre » affiché par l'ingestion."""
    summary = {}
    for chunk in chunk_lists:
        row = summary.setdefault(chunk.domain, {"total": 0, "types": {}, "difficulties": {}})
        row["total"] += 1
        row["types"][chunk.type] = row["types"].get(chunk.type, 0) + 1
        row["difficulties"][chunk.difficulty] = row["difficulties"].get(chunk.difficulty, 0) + 1
    return summary
