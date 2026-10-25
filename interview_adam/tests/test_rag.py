"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Tests du pipeline RAG (2b) : découpage du markdown, index FAISS persisté, retriever et
ses replis, ingestion idempotente, et les deux CLI.

Un plongeur lexical déterministe (`HashingEmbedder`) remplace MiniLM : les tests vérifient
la mécanique de récupération — un bon terme commun doit ramener le bon domaine — sans
dépendre d'un téléchargement de 90 Mo ni de torch. Le chemin réel transformers + faiss est
couvert par `test_real_embedder_routes_queries_on_the_full_index`, sauté sauf demande explicite
(ADAM_RAG_TESTS=1), parce qu'il suppose le modèle en cache HF et n'apporte rien aux autres
tests.
"""

import json
import math
import os
import re
import shutil
import zlib
from collections import Counter
from pathlib import Path

import pytest

from interview_adam import config_adam as cfg
from interview_adam.rag import ingest as ingest_module
from interview_adam.rag import search as search_module
from interview_adam.rag.chunking import describe, load_chunks, parse_document, slugify
from interview_adam.rag.embeddings import AdamEmbedder, AdamEmbeddingError
from interview_adam.rag.retriever import DOMAIN_PRIORITY, AdamRetriever, expand_query
from interview_adam.rag.store import AdamRagUnavailable, AdamVectorStore

KNOWLEDGE = Path(cfg.KNOWLEDGE_DIR)
DOMAINS = {"web-dev", "data-ai", "devops", "hr-behavioral", "star-method", "rubrics"}


class HashingEmbedder:
    """
    Un sac-de-mots haché sur 16 384 dimensions, normalisé en L2 : le cosinus devient un
    recouvrement de vocabulaire, ce qui est exactement ce qu'on veut tester — « kubernetes »
    doit rapprocher un fragment devops, pas un fragment de notes de bas de page. La
    dimension est volontairement grande : à 1 024 dimensions le hachage de quelques milliers
    de termes collide autant qu'il discrimine, et le bruit noie le vrai recouvrement.
    """

    dim = 16384

    def __init__(self):
        self.model_name = "test-hashing-embedder"
        self.calls = []

    def _vector(self, text):
        self.calls.append(text)
        counts = Counter(re.findall(r"[a-z0-9+#./-]{3,}", (text or "").lower()))
        vector = [0.0] * self.dim
        for term, weight in counts.items():
            # crc32 et non hash() : ce dernier est salé par PYTHONHASHSEED, donc deux
            # processus verraient le même terme dans deux dimensions différentes.
            vector[zlib.crc32(term.encode()) % self.dim] += weight
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed(self, texts):
        import numpy as np
        return np.asarray([self._vector(text) for text in texts], dtype="float32")

    def embed_one(self, text):
        import numpy as np
        return np.asarray(self._vector(text), dtype="float32")

    def warm(self):
        return self.model_name


@pytest.fixture(scope="module")
def chunks():
    return load_chunks(KNOWLEDGE)


@pytest.fixture
def rag_store(tmp_path, chunks):
    """Index construit sur le vrai markdown, dans un répertoire jetable, avec le plongeur lexical."""
    store = AdamVectorStore(tmp_path / "knowledge.faiss", tmp_path / "knowledge_meta.json")
    meta = store.build(chunks, HashingEmbedder().embed([c.embedding_text for c in chunks]),
                       model_name="test-hashing-embedder")
    return store, meta


# ----------------------------------------------------------------------
# Découpage de la base de connaissances
# ----------------------------------------------------------------------

def test_every_domain_file_is_present():
    stems = {path.stem for path in KNOWLEDGE.glob("*.md")}
    assert stems == DOMAINS, "un domaine promis sans fichier = un filtre de retrieval silencieux"


def test_knowledge_base_is_substantial_per_domain(chunks):
    counts = Counter(chunk.domain for chunk in chunks)
    assert set(counts) == DOMAINS
    for domain, size in counts.items():
        assert size >= 8, f"{domain} n'a que {size} fragments : récupération peu discriminante"
    assert len(chunks) >= 60


def test_each_chunk_is_tagged_with_the_three_axes(chunks):
    for chunk in chunks:
        assert chunk.domain in DOMAINS
        assert chunk.type in ("question", "guideline", "rubric")
        assert chunk.difficulty in ("junior", "intermediate", "senior")
        assert chunk.text and len(chunk.text) > 200
        assert chunk.title and chunk.source.endswith(".md")


def test_each_domain_mixes_questions_and_reference_notes(chunks):
    per_domain = describe(chunks)
    assert per_domain["web-dev"]["types"].get("question", 0) >= 4
    assert per_domain["rubrics"]["types"].get("rubric", 0) >= 5
    assert per_domain["hr-behavioral"]["types"].get("question", 0) >= 8


def test_knowledge_base_is_in_english(chunks):
    """La base est en anglais (décision 2b) : les prompts, eux, restent en français."""
    joined = " ".join(chunk.text for chunk in chunks).lower()
    for french in ("réponse", "compétence", "entreprise", "méthode", "notamment"):
        assert french not in joined


def test_chunk_ids_are_stable_and_unique(chunks):
    ids = [chunk.id for chunk in chunks]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"[a-z0-9-]+/[a-z0-9-]+", identifier) for identifier in ids)
    # Re-analyse du même fichier : mêmes identifiants, donc ingestion idempotente.
    again = load_chunks(KNOWLEDGE)
    assert [chunk.id for chunk in again] == ids


def test_slugify_is_readable_and_bounded():
    assert slugify("N+1 queries and how to fix them") == "n-1-queries-and-how-to-fix-them"
    assert slugify("  !!! ??? ") == "chunk"
    assert len(slugify("mot-" * 40)) <= 60


def test_parser_reads_metadata_and_ignores_prose():
    markdown = """---
domain: demo
---

Intro humaine, non indexée.

## Alpha chunk
type: question
difficulty: senior
tags: un, deux

Corps du fragment alpha.

### Nested heading stays inside the chunk
taille ligne de prose
"""
    directory = Path(os.getcwd())
    path = directory / "tmp_demo_knowledge.md"
    try:
        path.write_text(markdown, encoding="utf-8")
        domain, parsed = parse_document(path)
        assert domain == "demo"
        assert len(parsed) == 1
        chunk = parsed[0]
        assert (chunk.domain, chunk.type, chunk.difficulty) == ("demo", "question", "senior")
        assert chunk.tags == ("un", "deux")
        assert "Corps du fragment alpha." in chunk.text
        assert "### Nested heading stays inside the chunk" in chunk.text
        assert "non indexée" not in chunk.text
    finally:
        path.unlink(missing_ok=True)


def test_parser_defaults_a_missing_or_bogus_tag():
    """Une faute de frappe sur « rubbric » ne doit pas inventer un quatrième type."""
    markdown = "## Beta chunk\ntype: rubbric\ndifficulty: wizard\n\ncorps suffisant pour le test.\n"
    path = Path(os.getcwd()) / "tmp_demo_defaults.md"
    try:
        path.write_text(markdown, encoding="utf-8")
        _, parsed = parse_document(path)
        assert (parsed[0].type, parsed[0].difficulty) == ("guideline", "intermediate")
        assert parsed[0].domain == "tmp-demo-defaults"
    finally:
        path.unlink(missing_ok=True)


def test_embedding_text_carries_title_and_tags(chunks):
    chunk = chunks[0]
    blob = chunk.embedding_text
    assert blob.startswith(chunk.title)
    assert f"domain: {chunk.domain}" in blob
    assert chunk.text in blob


# ----------------------------------------------------------------------
# Index FAISS persisté
# ----------------------------------------------------------------------

def test_index_round_trips_through_disk(rag_store, tmp_path):
    store, meta = rag_store
    assert meta["count"] == store.size == len(meta["records"])
    assert store.index_path.exists() and store.meta_path.exists()
    assert meta["dim"] == HashingEmbedder.dim and meta["domains"] == sorted(DOMAINS)

    reopened = AdamVectorStore(store.index_path, store.meta_path)
    assert reopened.load() is True
    assert reopened.size == store.size
    assert reopened.count_by_domain() == store.count_by_domain()


def test_missing_index_is_not_an_error(tmp_path):
    store = AdamVectorStore(tmp_path / "absent.faiss", tmp_path / "absent.json")
    assert store.load() is False
    assert store.loaded is False
    assert store.search([0.1] * 4) == []


def test_incoherent_index_is_reported(rag_store):
    """index FAISS et méta désynchronisés : on lève un message qui dit quoi relancer."""
    store, _ = rag_store
    store.meta_path.write_text(json.dumps({"records": [{"id": "x"}], "dim": 1024}), encoding="utf-8")
    orphan = AdamVectorStore(store.index_path, store.meta_path)
    with pytest.raises(AdamRagUnavailable) as excinfo:
        orphan.load()
    assert "ingest" in str(excinfo.value)


def test_load_if_present_returns_none_on_any_damage(tmp_path):
    assert AdamVectorStore.load_if_present(tmp_path / "nope.faiss", tmp_path / "nope.json") is None


def test_build_refuses_desynchronized_vectors(chunks, tmp_path):
    store = AdamVectorStore(tmp_path / "k.faiss", tmp_path / "k.json")
    with pytest.raises(AdamRagUnavailable):
        store.build(chunks[:3], HashingEmbedder().embed(["a", "b"]), model_name="m")


def test_empty_knowledge_directory_is_refused(tmp_path):
    with pytest.raises(AdamRagUnavailable):
        ingest_module.ingest(knowledge_dir=tmp_path, embedder=HashingEmbedder(), dry_run=True)


# ----------------------------------------------------------------------
# Récupération : le bon domaine pour la bonne requête
# ----------------------------------------------------------------------

@pytest.fixture
def retriever(rag_store):
    """
    Retrieval sur le proxy haché. `require_overlap=True` : contrairement à all-MiniLM-L6-v2,
    le proxy lexical renvoie des hors-sujets au cosinus non nul (bruit de hachage), exactement
    le cas que le filtre de recouvrement protège en production. Ces tests verrouillent donc le
    MODE garde-activée ; le défaut (garde coupée, `ADAM_RAG_REQUIRE_OVERLAP=0`) est vérifié par
    `test_the_overlap_guard_is_off_by_default`.
    """
    store, _ = rag_store
    return AdamRetriever(store=store, embedder=HashingEmbedder(), min_score=0.0, require_overlap=True)


def test_the_overlap_guard_is_off_by_default():
    """Production (MiniLM dense) : on n'impose pas le recouvrement lexical par défaut."""
    assert AdamRetriever(store=None).require_overlap is False



@pytest.mark.parametrize("query,expected", [
    ("React developer frontend TypeScript single page application", "web-dev"),
    ("FastAPI Pydantic backend REST API endpoint", "web-dev"),
    ("Data scientist machine learning model training precision recall", "data-ai"),
    ("ETL pipeline data quality feature engineering pandas", "data-ai"),
    ("DevOps engineer Kubernetes Docker CI/CD Terraform deployment", "devops"),
    ("Docker container image multi-stage build dockerfile", "devops"),
    ("tell me about a time you failed a project", "hr-behavioral"),
    ("conflict with a teammate disagreement", "hr-behavioral"),
    ("STAR method situation task action result quantified", "star-method"),
    ("scoring rubric verdict criteria relevance", "rubrics"),
])
def test_retrieval_finds_the_expected_domain(retriever, query, expected):
    hits = retriever.search("questions", query, k=3)
    assert hits, f"aucun fragment récupéré pour {query!r}"
    assert hits[0]["domain"] == expected, [hit["domain"] for hit in hits]


def test_hits_carry_the_fields_the_ui_needs(retriever):
    hit = retriever.search("questions", "Kubernetes deployment rolling update", k=1)[0]
    assert set(hit) == {"id", "domain", "title", "type", "difficulty", "score", "text"}
    assert 0.0 <= hit["score"] <= 1.0001
    assert "/" in hit["id"] and hit["title"]


def test_sources_drop_the_text_kept_for_the_prompt(retriever):
    hits = retriever.search("questions", "Kubernetes deployment rolling update", k=2)
    sources = retriever.sources(hits)
    assert all("text" not in source for source in sources)
    assert {field for field in sources[0]} == {"id", "domain", "title", "type", "difficulty", "score"}


def test_evaluate_step_prefers_the_rubrics(retriever):
    """
    Même requête, deux étapes du pipeline : l'étape qui note doit faire remonter la grille
    plus haut que l'étape qui génère des questions. On compare des positions plutôt que
    d'exiger un top-1 différent : c'est la propriété réelle du reclassement par `kind`,
    et elle ne dépend pas de quel fragment arrive deuxième.
    """
    query = "answer quality relevance structure technical accuracy score"

    def rubric_positions(kind):
        ids = [hit["id"] for hit in retriever.search(kind, query, k=6)]
        assert ids, f"aucun fragment récupéré pour {query!r}"
        return ids, [index for index, identifier in enumerate(ids) if identifier.startswith("rubrics/")]

    asked_ids, asked_positions = rubric_positions("questions")
    scored_ids, scored_positions = rubric_positions("evaluate")

    assert scored_ids[0].startswith("rubrics/")
    assert asked_positions and scored_positions
    assert min(scored_positions) <= min(asked_positions)
    assert DOMAIN_PRIORITY["evaluate"]["rubrics"] > DOMAIN_PRIORITY["questions"]["rubrics"]


def test_improve_step_prefers_the_star_method(retriever):
    hits = retriever.search("improve", "rewrite the answer situation task action result", k=3)
    assert hits[0]["domain"] == "star-method"


def test_min_score_filters_weak_matches(rag_store):
    store, _ = rag_store
    strict = AdamRetriever(store=store, embedder=HashingEmbedder(), min_score=0.99)
    assert strict.search("questions", "zzz qqq xxx", k=3) == []


# ----------------------------------------------------------------------
# Requêtes françaises contre une base anglaise
# ----------------------------------------------------------------------

def test_expansion_adds_english_and_keeps_french():
    expanded = expand_query("parle-moi d'un échec")
    assert "échec" in expanded.lower()
    assert "failure" in expanded


def test_accent_folding_does_not_split_the_vocabulary():
    """« compétence » doit être reconnu malgré l'accent aigu. """
    assert "skill" in expand_query("Quelles sont tes compétences")
    assert "remote work" in expand_query("Politique de télétravail")
    assert "conflict" in expand_query("une situation de conflit")


def test_an_unknown_word_is_left_untouched():
    assert expand_query("zythologue krocodel") == "zythologue krocodel"


def test_the_embedder_receives_the_expanded_query(retriever):
    """
    Sans l'expansion, une requête française n'a aucun mot commun avec la base anglaise et
    ne remonte rien : c'est exactement le défaut que ce test verrouille.
    """
    recorder = HashingEmbedder()
    retriever.embedder = recorder
    hits = retriever.search("questions", "raconte-moi un échec pendant une deadline", k=3)
    assert hits, "un échec = failure : la base comportementale doit être atteignable en français"
    assert recorder.calls, "le retriever n'a rien plongé"
    assert "failure" in recorder.calls[-1]


@pytest.mark.parametrize("french,expected", [
    ("raconte-moi une situation de conflit avec un collègue", "hr-behavioral"),
    ("quelle est ta plus grande faiblesse", "hr-behavioral"),
    ("comment structures-tu une api pour un premier projet", "web-dev"),
    ("votre politique de travail à distance et de documentation", "hr-behavioral"),
    ("compétences en déploiement et en conteneur", "devops"),
])
def test_french_questions_reach_the_expected_domain(retriever, french, expected):
    """Les questions affichées au candidat sont en français : la récupération doit suivre."""
    hits = retriever.search("questions", french, k=3)
    assert hits, french
    assert hits[0]["domain"] == expected, [(hit["domain"], hit["id"]) for hit in hits]


def test_gibberish_never_injects_a_reference(retriever):
    assert retriever.search("questions", "qqq www zzz blorp", k=3) == []


def test_top_k_is_respected(retriever):
    assert len(retriever.search("questions", "Python API", k=2)) <= 2
    assert len(retriever.search("questions", "Python API", k=6)) <= 6


def test_context_is_formatted_and_bounded(retriever):
    hits = retriever.search("questions", "Docker image layer security", k=5)
    context = retriever.context(hits, limit=600)
    assert context.startswith("### ")
    assert "(devops / " in context
    assert len(context) <= 600
    # Une seule référence tient si le budget ne permet pas la deuxième : on ne coupe pas un
    # fragment en plein milieu pour caser le suivant.
    assert context.count("### ") <= len(hits)


def test_retrieve_returns_the_pair_the_service_consumes(retriever):
    """Le contrat du service 2b : retrieve(kind, query, limit) -> (contexte, sources)."""
    context, sources = retriever.retrieve("evaluate", "rubric relevance clarity", limit=800)
    assert context.startswith("### ") and len(context) <= 800
    assert sources and all("text" not in source for source in sources)
    assert [source["id"] for source in sources] == [hit["id"] for hit in
                                                    retriever.search("evaluate", "rubric relevance clarity")]


def test_availability_messages_are_actionable(rag_store, tmp_path):
    """
    Les trois états possibles doivent se distinguer à l'écran : prêt, pas encore de retriever,
    index pas encore ingéré. Le dernier cas nomme la commande à lancer.
    """
    store, _ = rag_store
    available, reason = AdamRetriever(store=store, embedder=HashingEmbedder()).available()
    assert available and "fragments" in reason

    available, reason = AdamRetriever(store=None, embedder=HashingEmbedder()).available()
    assert not available and "non chargé" in reason

    not_ingested = AdamRetriever(store=AdamVectorStore(tmp_path / "none.faiss", tmp_path / "none.json"),
                                 embedder=HashingEmbedder())
    available, reason = not_ingested.available()
    assert not available and "ingest" in reason


def test_a_failing_embedder_degrades_to_no_rag(retriever):
    class Broken(HashingEmbedder):
        def embed_one(self, text):
            raise AdamEmbeddingError("modèle non téléchargeable")

    retriever.embedder = Broken()
    assert retriever.search("questions", "Kubernetes", k=3) == []


def test_a_store_without_vectors_returns_nothing(rag_store):
    store, _ = rag_store

    class WrongDimension(HashingEmbedder):
        dim = 7

        def embed_one(self, text):
            import numpy as np
            return np.zeros(7, dtype="float32")

    quiet = AdamRetriever(store=store, embedder=WrongDimension(), min_score=0.0)
    assert quiet.search("questions", "Kubernetes", k=3) == []


def test_build_returns_none_when_nothing_is_ingested(tmp_path):
    assert AdamRetriever.build(tmp_path / "none.faiss", tmp_path / "none.json") is None


def test_build_wires_the_persisted_index(rag_store):
    store, _ = rag_store
    wired = AdamRetriever.build(store.index_path, store.meta_path, embedder=HashingEmbedder())
    assert wired is not None and wired.available()[0]
    assert wired.model_name == "test-hashing-embedder"


# ----------------------------------------------------------------------
# Ingestion : idempotence et résumé
# ----------------------------------------------------------------------

def test_ingestion_is_idempotent(tmp_path, chunks):
    knowledge = tmp_path / "knowledge"
    shutil.copytree(KNOWLEDGE, knowledge)
    store = AdamVectorStore(tmp_path / "k.faiss", tmp_path / "k.json")
    embedder = HashingEmbedder()

    first = ingest_module.ingest(knowledge_dir=knowledge, embedder=embedder, store=store)
    assert first["chunks"] == len(chunks)
    assert first["unchanged"] is False and first["diff"]["first"] is True
    assert len(embedder.calls) == len(chunks)

    # Deuxième exécution sur les mêmes fichiers : même contenu, donc diff vide — c'est la
    # preuve que l'ingestion ne peut pas empiler des doublons.
    second = ingest_module.ingest(knowledge_dir=knowledge, embedder=HashingEmbedder(), store=store)
    assert second["unchanged"] is True, second["diff"]
    assert second["diff"] == {"added": [], "removed": [], "changed": [], "first": False}
    assert second["chunks"] == first["chunks"]
    assert set(second["domains"]) == DOMAINS

    reloaded = AdamVectorStore(second["index_path"], second["meta_path"])
    assert reloaded.load() is True and reloaded.size == len(chunks)


def test_ingestion_reports_added_and_removed(tmp_path):
    knowledge = tmp_path / "knowledge"
    shutil.copytree(KNOWLEDGE, knowledge)
    store = AdamVectorStore(tmp_path / "k.faiss", tmp_path / "k.json")
    ingest_module.ingest(knowledge_dir=knowledge, embedder=HashingEmbedder(), store=store)

    target = knowledge / "web-dev.md"
    original = target.read_text(encoding="utf-8")
    target.write_text(original + "\n## Un fragment ajoute\n\nTexte neuf assez long pour etre index.\n",
                      encoding="utf-8")
    diff = ingest_module.ingest(knowledge_dir=knowledge, embedder=HashingEmbedder(), store=store)["diff"]
    assert diff["added"] == ["web-dev/un-fragment-ajoute"]
    assert diff["removed"] == [] and diff["changed"] == []

    target.write_text(original, encoding="utf-8")
    reverted = ingest_module.ingest(knowledge_dir=knowledge, embedder=HashingEmbedder(), store=store)["diff"]
    assert reverted["removed"] and not reverted["added"]


def test_ingest_dry_run_writes_nothing(tmp_path):
    store = AdamVectorStore(tmp_path / "k.faiss", tmp_path / "k.json")
    summary = ingest_module.ingest(knowledge_dir=KNOWLEDGE, embedder=HashingEmbedder(),
                                   store=store, dry_run=True)
    assert summary["dry_run"] is True and summary["chunks"] >= 60
    assert not store.index_path.exists() and not store.meta_path.exists()


def test_ingest_cli_prints_chunks_per_domain(capsys):
    assert ingest_module.main(["--dry-run"]) == 0
    printed = capsys.readouterr().out
    for domain in sorted(DOMAINS):
        assert domain in printed
    assert "Fragments analysés" in printed


def test_ingest_cli_json_output_is_machine_readable(capsys):
    assert ingest_module.main(["--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True and set(payload["domains"]) == DOMAINS


# ----------------------------------------------------------------------
# CLI de recherche (démo de soutenance)
# ----------------------------------------------------------------------

def test_search_cli_prints_top_k_with_scores(rag_store, capsys, monkeypatch):
    store, _ = rag_store
    monkeypatch.setattr(AdamRetriever, "build",
                        classmethod(lambda cls, *a, **kw: cls(store=store, embedder=HashingEmbedder(),
                                                              min_score=0.0)))
    query = "DevOps engineer Kubernetes Docker CI/CD Terraform deployment"
    assert search_module.main([query, "--top-k", "2", "--text", "40"]) == 0
    printed = capsys.readouterr().out
    assert "Requête" in printed and "devops" in printed
    assert "id=devops/" in printed
    assert re.search(r"\d\.\s+0\.\d{3}\s+\[", printed), printed


def test_search_cli_explains_a_missing_index(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(AdamRetriever, "build", classmethod(lambda cls, *a, **kw: None))
    assert search_module.main(["n'importe quoi"]) == 1
    assert "ingest" in capsys.readouterr().err


def test_search_cli_reports_a_query_with_no_hit(rag_store, capsys, monkeypatch):
    store, _ = rag_store
    monkeypatch.setattr(AdamRetriever, "build",
                        classmethod(lambda cls, *a, **kw: cls(store=store, embedder=HashingEmbedder(),
                                                              min_score=0.95)))
    assert search_module.main(["zzzz", "--text", "0"]) == 0
    printed = capsys.readouterr().out
    assert "aucun fragment" in printed
    assert "0/1 requêtes ont trouvé" in printed


# ----------------------------------------------------------------------
# Plongeur réel : hors CI, suppose le modèle en cache HuggingFace
# ----------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("ADAM_RAG_TESTS") != "1",
                    reason="plongeur réel : ADAM_RAG_TESTS=1 (télécharge/use le cache MiniLM)")
def test_real_embedder_routes_queries_on_the_full_index(tmp_path, chunks):
    """
    Smoke test du chemin réel (transformers + faiss, garde coupée comme en production) sur la
    base entière : un proxy haché ne prouve pas que MiniLM atteigne le bon domaine, et indexer
    huit fragments n'en contient aucun sur le sujet demandé.
    """
    import numpy as np

    embedder = AdamEmbedder()
    vectors = embedder.embed([chunk.embedding_text for chunk in chunks])
    assert vectors.shape == (len(chunks), 384)
    # L2 normalisé : la norme de chaque ligne vaut 1, condition du cosinus par produit scalaire.
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)

    store = AdamVectorStore(tmp_path / "real.faiss", tmp_path / "real.json")
    store.build(chunks, vectors, model_name=embedder.model_name)
    live = AdamRetriever(store=store, embedder=embedder)  # min_score et garde : défauts production

    assert live.search("questions", "Docker container image layer", k=3)[0]["domain"] == "devops"
    conflict = live.search("questions", "raconte-moi une situation de conflit avec un collègue", k=3)
    assert conflict[0]["domain"] == "hr-behavioral", "le glossaire FR doit porter sur le modèle réel"

