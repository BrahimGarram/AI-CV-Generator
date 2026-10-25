"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Petit CLI de démonstration pour la soutenance : il montre ce que le RAG récupère vraiment.

    python -m interview_adam.rag.search "DevOps engineer kubernetes"
    python -m interview_adam.rag.search "React developer" "Data scientist" --top-k 3
    python -m interview_adam.rag.search "tell me about a failure" --kind evaluate --text 200

Le score affiché est la similarité cosinus brute entre le vecteur de la requête et le
fragment — pas le score après reclassement par domaine, qui n'est qu'un ordre de tri.
"""

import argparse
import sys
from pathlib import Path

from interview_adam import config_adam as cfg
from interview_adam.rag.retriever import AdamRetriever


def format_hit(rank, hit, text_chars):
    line = (f"  {rank}. {hit['score']:.3f}  [{hit['domain']} / {hit['type']} / {hit['difficulty']}]  "
            f"{hit['title']}\n      id={hit['id']}")
    if text_chars:
        excerpt = " ".join((hit.get("text") or "").split())[:text_chars]
        line += f"\n      {excerpt}{'…' if len(' '.join((hit.get('text') or '').split())) > text_chars else ''}"
    return line


def run_query(retriever, query, kind, top_k, text_chars):
    print(f"\nRequête   : {query!r}")
    print(f"Étape     : {kind}   (priorité de domaines du pipeline)")
    hits = retriever.search(kind, query, k=top_k)
    if not hits:
        print("  aucun fragment au-dessus du seuil "
              f"(ADAM_RAG_MIN_SCORE={retriever.min_score}) — le prompt partira sans <references>.")
        return hits
    print(f"  top {len(hits)} :")
    for rank, hit in enumerate(hits, start=1):
        print(format_hit(rank, hit, text_chars))
    return hits


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m interview_adam.rag.search",
        description="Interroge l'index vectoriel du simulateur d'entretien (aucun appel à Mistral).")
    parser.add_argument("query", nargs="+", help="texte à plonger, plusieurs requêtes acceptées")
    parser.add_argument("--kind", choices=("questions", "evaluate", "improve"), default="questions",
                        help="étape du pipeline simulée, change la priorité des domaines")
    parser.add_argument("--top-k", type=int, default=cfg.RAG_TOP_K, help="nombre de fragments affichés")
    parser.add_argument("--text", type=int, default=240,
                        help="extraits de fragment à afficher (0 = titres seuls)")
    arguments = parser.parse_args(argv)

    retriever = AdamRetriever.build()
    if retriever is None:
        print("Index RAG absent ou illisible.\n"
              "Construis-le d'abord :  python -m interview_adam.rag.ingest", file=sys.stderr)
        return 1

    available, reason = retriever.available()
    print(f"Index     : {reason}")
    if not available:
        print("Index non chargé : relance l'ingestion.", file=sys.stderr)
        return 1

    results = [run_query(retriever, query, arguments.kind, arguments.top_k, arguments.text)
               for query in arguments.query]
    print(f"\n{sum(1 for hits in results if hits)}/{len(results)} requêtes ont trouvé au moins un fragment.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
