"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Retriever du RAG : il transforme une requête métier (« questions sur un poste de DevOps »,
« grille d'évaluation de cette réponse ») en quelques fragments de la base de connaissances,
prêts à être injectés dans le prompt.

Deux responsabilités :

1. **Le déclinaison par étape.** `kind` ("questions" | "evaluate" | "improve") module
   l'ordre de priorité des domaines : pour générer des questions on veut la documentation
   technique et comportementale, pour noter une réponse on veut avant tout les grilles.
   Le boost n'est qu'un ordre de tri — le score exposé reste la similarité cosinus réelle,
   sinon l'UI afficherait une confiance inventée.

2. **La dégradation silencieuse.** plonger indisponible, index absent, modèle d'embeddings
   non téléchargé, faiss manquant : `search` rend une liste vide et le module d'entretien
   fonctionne exactement comme en 2a, prompt sans bloc `<references>` et `rag_used=false`.
   Un entretien ne doit jamais échouer à cause de la base documentaire.
"""

import logging

import re
import unicodedata

from interview_adam import config_adam as cfg
from interview_adam.rag.embeddings import AdamEmbedder, AdamEmbeddingError
from interview_adam.rag.store import AdamRagUnavailable, AdamVectorStore

logger = logging.getLogger("smartcareer.interview.rag")

# Priorité relative des domaines selon l'étape du pipeline qui demande de la documentation.
DOMAIN_PRIORITY = {
    "questions": {"web-dev": 1.15, "data-ai": 1.15, "devops": 1.15,
                  "hr-behavioral": 1.15, "star-method": 1.05, "rubrics": 0.85},
    "evaluate": {"rubrics": 1.35, "star-method": 1.15, "hr-behavioral": 1.05,
                 "web-dev": 1.0, "data-ai": 1.0, "devops": 1.0},
    "improve": {"star-method": 1.30, "rubrics": 1.10, "web-dev": 1.05,
                "data-ai": 1.05, "devops": 1.05, "hr-behavioral": 1.05},
}

# Limite connue et assumée de la 2b. La base est en anglais (décision 2b) mais l'application
# est française et Mistral pose les questions en français. all-MiniLM-L6-v2 reste correct sur
# une requête anglaise, mais « parle-moi d'un échec » plafonne à ~0,07 de cosinus contre le
# bon fragment : la langue casse la récupération. Ce glossaire ajoute l'équivalent anglais des
# termes d'entretien les plus fréquents (le français est conservé : une requête mixte garde ses
# mots déjà alignés sur la base). Il est volontairement court — un dictionnaire exhaustif serait
# un faux ami. Un terme absent n'est pas bloquant : la requête garde ses propres mots, et si rien
# ne franchit RAG_MIN_SCORE on rend un contexte vide (l'entretien a lieu, sans référence).
# Vérifié sur le modèle réel : les requêtes FR courantes atteignent le bon domaine (0,44-0,54).
FR_TO_EN = {
    "api": "api rest endpoint", "collegue": "teammate colleague", "competence": "skill competency",
    "conflit": "conflict disagreement", "conteneur": "container image",
    "delai": "deadline", "deploiement": "deployment release", "distance": "remote work",
    "documentation": "documentation communication", "donnees": "database data", "echec": "failure",
    "equipe": "team teamwork", "experience": "experience", "faiblesse": "weakness",
    "force": "strength", "politique": "policy", "projet": "project", "qualite": "quality",
    "requete": "query", "resultat": "result outcome", "revue": "review", "structure": "architecture design",
    "teletravail": "remote work", "test": "testing", "travail": "work job",
}

_TOKEN = re.compile(r"[a-zà-ÿ]+")


def _ascii_fold(text):
    """« défaillance » -> « defaillance » : les accents ne doivent pas couper le vocabulaire."""
    return "".join(character for character in unicodedata.normalize("NFD", (text or "").lower())
                   if unicodedata.category(character) != "Mn")


def _gloss(token):
    """
    Équivalent anglais d'un token français : correspondance exacte d'abord, puis la forme
    singulière (« compétences » -> « competence ») parce que le glossaire est indexé au singulier.
    """
    return FR_TO_EN.get(token) or (FR_TO_EN.get(token[:-1]) if token.endswith("s") else None)


def expand_query(query):
    """
    Ajoute les équivalents anglais des termes français repérés. On ne remplace pas le
    français : une requête mixte (« Développeur Back-End Python ») doit garder ses mots
    qui correspondent déjà à la base.
    """
    tokens = {token for token in _TOKEN.findall(_ascii_fold(query)) if len(token) >= 3}
    if not tokens:
        return query

    additions = []
    for token in tokens:
        exact = _gloss(token)
        if exact:
            additions.append(exact)
    if not additions:
        return query
    return query + " " + " ".join(additions)


_HIT_FIELDS = ("id", "domain", "title", "type", "difficulty", "score")

# Mode optionnel `require_overlap` (voir cfg.RAG_REQUIRE_OVERLAP) : un fragment n'est retenu
# que s'il partage au moins un mot réel avec la requête. Conçu pour un plongeur lexical dont
# le bruit de hachage attribue un cosinus non nul à un fragment qui ne contient aucun des mots
# cherchés — injecter cette référence serait du bruit déguisé en preuve. Désactivé par défaut
# avec un plongeur dense : il rapproche utilement des synonymes sans mot commun.
_CONTENT = re.compile(r"[a-z0-9][a-z0-9+#./-]{2,}")


def _content_tokens(text):
    return {token for token in _CONTENT.findall(_ascii_fold(text))}



class AdamRetriever:
    """
    `store` et `embedder` sont injectables : les tests remplacent le plongeur réel par un
    plongeur déterministe et n'ont besoin ni de torch, ni de faiss, ni du réseau.
    """

    def __init__(self, store=None, embedder=None, top_k=None, min_score=None, candidates=None,
                 require_overlap=None):
        self.store = store
        self.embedder = embedder if embedder is not None else AdamEmbedder()
        self.top_k = top_k if top_k is not None else cfg.RAG_TOP_K
        self.min_score = min_score if min_score is not None else cfg.RAG_MIN_SCORE
        self.candidates = candidates if candidates is not None else cfg.RAG_CANDIDATES
        self.require_overlap = (cfg.RAG_REQUIRE_OVERLAP if require_overlap is None
                                else require_overlap)

    # ------------------------------------------------------------------
    # État, pour le diagnostic et la route /interview/status
    # ------------------------------------------------------------------

    def available(self):
        """(bool, motif) — le motif est destine a l'humain, jamais a un log sensible."""
        if self.store is None:
            return False, "index RAG non chargé"
        if not self.store.loaded:
            return False, "index RAG absent : lance python -m interview_adam.rag.ingest"
        return True, f"{self.store.size} fragments ({self.store.meta.get('model', '?')})"

    @property
    def model_name(self):
        if self.store is not None and self.store.loaded:
            return self.store.meta.get("model") or self.embedder.model_name
        return None

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------

    def search(self, kind, query, k=None):
        """
        Rend une liste de hits `dict`, triée, toujours au moins 0 : c'est le contrat de
        dégradation. Un hit porte id, domaine, titre, type, difficulté, score (cosinus) et
        le texte du fragment.
        """
        if not query or self.store is None or not self.store.loaded:
            return []

        expanded = expand_query(query)
        query_terms = _content_tokens(expanded) if self.require_overlap else None

        try:
            vector = self.embedder.embed_one(expanded)
        except AdamEmbeddingError as error:
            logger.warning("RAG désactivé pour cette requête : %s", error)
            return []

        limit = k or self.top_k
        try:
            raw = self.store.search(vector, max(self.candidates, limit))
        except AdamRagUnavailable as error:
            logger.warning("RAG désactivé pour cette requête : %s", error)
            return []

        priority = DOMAIN_PRIORITY.get(kind, {})
        ranked = sorted(raw, key=lambda hit: (hit[1] * priority.get(hit[0]["domain"], 1.0), hit[1]),
                        reverse=True)

        hits = []
        for record, score in ranked[:limit]:
            if score < self.min_score:
                continue
            if query_terms is not None and not (
                    query_terms & _content_tokens(record.get("title", "") + " " + record.get("text", ""))):
                continue
            hit = {field: record.get(field) for field in _HIT_FIELDS}
            hit["score"] = round(score, 3)
            hit["text"] = record.get("text", "")
            hits.append(hit)
        return hits

    def sources(self, hits):
        """Vue légère des hits pour l'API : ce que l'interface affiche sous « sources »."""
        return [{field: hit.get(field) for field in _HIT_FIELDS} for hit in hits]

    def context(self, hits, limit=None):
        """
        Mise en forme pour le bloc `<references>` du prompt. Les fragments restent en
        anglais (langue de la base) même pour une interview en français : le modèle est
        instruit de répondre dans la langue demandée, et une traduction préalable de la
        base ne ferait qu'ajouter une source d'erreur.

        Un fragment trop long pour le budget n'est entaillé que s'il est le seul : mieux
        vaut une référence complète qu'une moitié de chacune.
        """
        budget = limit or cfg.MAX_RAG_CONTEXT_CHARS
        parts = []
        used = 0
        for hit in hits:
            # Chaque fragment est borné à son tour : une fiche entière est plus longue que
            # l'utilité de sa référence ; l'amorce suffit au modèle pour caler le barème.
            snippet = str(hit["text"])
            if len(snippet) > cfg.MAX_RAG_CHUNK_CHARS:
                snippet = snippet[:cfg.MAX_RAG_CHUNK_CHARS].rstrip() + "…"
            block = (f"### {hit['title']}\n"
                     f"({hit['domain']} / {hit['type']} / {hit['difficulty']})\n"
                     f"{snippet}")
            if used + len(block) > budget:
                if parts:
                    break
                # Le point de suspension compte dans le budget : on coupe à budget-1.
                return block[:max(budget - 1, 1)].rstrip() + "…"
            parts.append(block)
            used += len(block) + 2
        return "\n\n".join(parts)

    def retrieve(self, kind, query, k=None, limit=None):
        """(contexte, sources) en un appel — le couple que le service injecte dans le prompt."""
        hits = self.search(kind, query, k=k)
        return self.context(hits, limit=limit), self.sources(hits)

    def warm(self):
        """Charge modèle d'embeddings + index au démarrage : le premier candidat ne paie pas le téléchargement."""
        if self.store is not None:
            self.store.load()
        if self.available()[0]:
            self.embedder.warm()
        return self.available()

    @classmethod
    def build(cls, index_path=None, meta_path=None, embedder=None):
        """
        Fabrique le retriever de production depuis l'index persisté. Rend None quand rien
        n'est ingéré : l'appelant (le routeur) passe alors `retriever=None` au service, et
        le module tourne sans RAG.
        """
        store = AdamVectorStore.load_if_present(index_path, meta_path)
        if store is None:
            return None
        return cls(store=store, embedder=embedder)
