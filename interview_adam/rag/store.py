"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Index vectoriel FAISS du module, persisté sous `data/interview_adam/`.

Choix d'index : `IndexFlatIP` (produit scalaire interne). Les vecteurs sont déjà normalisés
en L2 à la plongée, donc le produit scalaire **est** la similarité cosinus. Un plateau
brute-force sur ~70 fragments de 384 dimensions coûte une fraction de milliseconde : un
index approché (`IndexHNSW`) n'apporte rien et rendrait les scores non reproductibles à la
soutenance.

Le disque contient deux fichiers qui doivent rester synchrones :

* `knowledge.faiss`       — les vecteurs, dans l'ordre des enregistrements ci-dessous ;
* `knowledge_meta.json`   — les métadonnées lisibles (id, domaine, titre, type, difficulté,
                            tags, texte) + le nom du modèle et la date de construction.

Les écritures passent par un fichier temporaire puis `os.replace` : une ingestion tuée en
cours de route ne doit pas laisser un index à moitié écrit que la première requête
chargerait et sur lequel les scores seraient absurdes.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from interview_adam import config_adam as cfg

SCHEMA_VERSION = 1


class AdamRagUnavailable(RuntimeError):
    """faiss absent, index absent ou illisible : le module continue sans RAG."""


def _faiss():
    """Import différé : le runtime de l'API ne doit pas échouer si faiss n'est pas installé."""
    try:
        import faiss
    except ImportError as error:
        raise AdamRagUnavailable(
            f"faiss absent de l'environnement ({error}). Installe requirements_interview_adam.txt.") from error
    return faiss


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AdamVectorStore:
    """
    `build(...)` écrit, `load()` lit, `search(vector, k)` rend des couples
    (enregistrement, score). Les instances sont petites : ce qui coûte cher est le contenu
    de l'index, chargé une fois puis partagé.
    """

    def __init__(self, index_path=None, meta_path=None):
        self.index_path = Path(index_path) if index_path else cfg.RAG_INDEX_PATH
        self.meta_path = Path(meta_path) if meta_path else cfg.RAG_META_PATH
        self._index = None
        self._records = []
        self.meta = {}

    # ------------------------------------------------------------------
    # État
    # ------------------------------------------------------------------

    @property
    def loaded(self):
        return self._index is not None and bool(self._records)

    @property
    def size(self):
        return len(self._records)

    @property
    def on_disk(self):
        return self.index_path.exists() and self.meta_path.exists()

    @property
    def records(self):
        return list(self._records)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self, chunks, vectors, model_name):
        """
        (Re)construit l'index complet depuis les fragments : on ne fait jamais d'ajout
        incrémental, l'index est petit et un ajout incrémental laisserait des lignes
        orphelines quand un titre est renommé. `vectors` doit avoir exactement une ligne
        par chunk, dans le même ordre.
        """
        faiss = _faiss()
        import numpy as np

        if len(chunks) != len(vectors):
            raise AdamRagUnavailable(f"{len(chunks)} fragments pour {len(vectors)} vecteurs : "
                                     "plongée et index désynchronisés.")
        if not chunks:
            raise AdamRagUnavailable("aucun fragment à indexer : la base de connaissances est vide.")

        matrix = np.ascontiguousarray(np.asarray(vectors, dtype="float32"))
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)

        records = [chunk.as_record() for chunk in chunks]
        meta = {
            "schema": SCHEMA_VERSION,
            "model": model_name,
            "dim": int(matrix.shape[1]),
            "count": len(records),
            "built_at": _utc_now(),
            "domains": sorted({r["domain"] for r in records}),
            "records": records,
        }
        self._write(index, meta)
        self._index = index
        self._records = records
        self.meta = meta
        return meta

    def _write(self, index, meta):
        faiss = _faiss()
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        temporary = self.index_path.with_suffix(".tmp")
        faiss.write_index(index, str(temporary))
        os.replace(temporary, self.index_path)

        temporary_meta = self.meta_path.with_suffix(".tmp")
        temporary_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary_meta, self.meta_path)

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def load(self):
        """
        Charge l'index en mémoire. Retourne False (sans lever) si les fichiers sont
        absents : ce n'est pas une erreur, c'est « le RAG n'est pas encore ingéré ».
        Lève AdamRagUnavailable si les fichiers existent mais sont incohérents, pour que
        l'ingestion suivante reparte d'un état propre.
        """
        if self.loaded:
            return True
        if not self.on_disk:
            return False

        faiss = _faiss()
        try:
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            records = meta["records"]
            index = faiss.read_index(str(self.index_path))
        except (OSError, ValueError, KeyError) as error:
            raise AdamRagUnavailable(f"index RAG illisible ({error}) : relance "
                                     "`python -m interview_adam.rag.ingest`.") from error

        if index.ntotal != len(records):
            raise AdamRagUnavailable(
                f"index RAG incohérent : {index.ntotal} vecteurs pour {len(records)} notices. "
                "Relance `python -m interview_adam.rag.ingest`.")

        self._index = index
        self._records = records
        self.meta = meta
        return True

    @classmethod
    def load_if_present(cls, index_path=None, meta_path=None):
        """Fabrique un store chargé, ou None si rien n'est ingéré / l'index est cassé."""
        store = cls(index_path, meta_path)
        try:
            return store if store.load() else None
        except AdamRagUnavailable:
            return None

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------

    def search(self, vector, k=4):
        """
        Top-k par similarité cosinus. Rend [(record, score), ...] trié par score décroissant,
        et [] si l'index n'est pas chargé — jamais d'exception, l'appelant est un service
        d'entretien qui doit répondre même sans documentation de référence.
        """
        if not self.loaded:
            return []
        import numpy as np

        query = np.asarray([vector], dtype="float32")
        if query.shape[1] != self.meta.get("dim", query.shape[1]):
            return []
        scores, positions = self._index.search(query, min(k, self.size))
        hits = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0:            # FAISS rend -1 quand moins de k résultats existent
                continue
            hits.append((self._records[position], float(score)))
        return hits

    def count_by_domain(self):
        counts = {}
        for record in self._records:
            counts[record["domain"]] = counts.get(record["domain"], 0) + 1
        return counts
