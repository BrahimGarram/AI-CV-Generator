"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Ingestion de la base de connaissances : markdown -> fragments -> plongeon CPU -> index
FAISS persisté sous `data/interview_adam/`.

    python -m interview_adam.rag.ingest
    python -m interview_adam.rag.ingest --dry-run     # parse seulement, aucun téléchargement

Idempotence : l'opération est un rebuild complet déterministe (mêmes fichiers, même ordre,
mêmes identifiants), donc la relancer ne crée jamais de doublon. Elle compare tout de même
son résultat avec l'index déjà présent et affiche ajouté / retiré / modifié / inchangé, ce
qui est la preuve visible de cette idempotence à la soutenance — « relance, il est écrit
inchangé ».
"""

import argparse
import json
import sys
from pathlib import Path

from interview_adam import config_adam as cfg
from interview_adam.rag.chunking import describe, load_chunks
from interview_adam.rag.store import AdamRagUnavailable, AdamVectorStore


def _previous_meta(store):
    """Métadonnées de l'index déjà sur disque, ou None. La lecture ne doit jamais lever ici."""
    if not store.meta_path.exists():
        return None
    try:
        return json.loads(store.meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def compare(previous, chunks):
    """
    Diff entre l'index existant et ce qui vient d'être parsé, par identifiant de fragment.
    Un titre renommé apparaît comme retiré + ajouté, c'est le comportement voulu : le
    texte a changé, son vecteur aussi.
    """
    if previous is None:
        return {"added": [c.id for c in chunks], "removed": [], "changed": [], "first": True}

    before = {record["id"]: record["text"] for record in previous.get("records", [])}
    after = {chunk.id: chunk.text for chunk in chunks}
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(i for i in set(after) & set(before) if after[i] != before[i]),
        "first": False,
    }


def ingest(knowledge_dir=None, embedder=None, store=None, dry_run=False):
    """
    Plonge tous les fragments et écrit l'index. Retourne le résumé machine (affiché par
    `main`). `dry_run` s'arrête après le découpage : utile pour valider le markdown sans
    télécharger le modèle d'embeddings ni toucher au GPU/disque.
    """
    chunks = load_chunks(knowledge_dir or cfg.KNOWLEDGE_DIR)
    if not chunks:
        raise AdamRagUnavailable(f"aucun fragment trouvé dans {knowledge_dir or cfg.KNOWLEDGE_DIR} "
                                 "— un fragment est une section « ## Titre » avec un corps.")

    summary = {
        "knowledge_dir": str(knowledge_dir or cfg.KNOWLEDGE_DIR),
        "chunks": len(chunks),
        "domains": describe(chunks),
        "dry_run": dry_run,
    }
    if dry_run:
        return summary

    target = store if store is not None else AdamVectorStore()
    diff = compare(_previous_meta(target), chunks)
    summary["diff"] = diff

    if embedder is None:
        from interview_adam.rag.embeddings import AdamEmbedder      # différé : torch
        embedder = AdamEmbedder()

    vectors = embedder.embed([chunk.embedding_text for chunk in chunks])
    meta = target.build(chunks, vectors, model_name=embedder.model_name)
    summary.update({"index_path": str(target.index_path), "meta_path": str(target.meta_path),
                    "model": meta["model"], "dim": meta["dim"], "built_at": meta["built_at"],
                    "unchanged": not (diff["added"] or diff["removed"] or diff["changed"])})
    return summary


def _print_summary(summary):
    print(f"Base de connaissances : {summary['knowledge_dir']}")
    print(f"Fragments analysés    : {summary['chunks']}")
    print()
    print(f"{'domaine':<16}{'frags':>6}   détail par type")
    print("-" * 62)
    for domain, row in sorted(summary["domains"].items()):
        types = ", ".join(f"{t}={n}" for t, n in sorted(row["types"].items()))
        print(f"{domain:<16}{row['total']:>6}   {types}")
    print("-" * 62)

    if summary["dry_run"]:
        print("--dry-run : aucun embedding calculé, aucun fichier écrit.")
        return

    diff = summary["diff"]
    if diff["first"]:
        print("Premier index : aucun index existant comparé.")
    else:
        print(f"Diff avec l'index existant : ajouté={len(diff['added'])}, "
              f"retiré={len(diff['removed'])}, modifié={len(diff['changed'])}")
        for label, ids in (("ajouté", diff["added"]), ("retiré", diff["removed"]),
                           ("modifié", diff["changed"])):
            for identifier in ids[:10]:
                print(f"   {label:8s} {identifier}")
    print(f"{'Inchangé : oui — réindexation idempotente.' if summary['unchanged'] else 'Index reconstruit.'}")
    print(f"Index   : {summary['index_path']}")
    print(f"Méta    : {summary['meta_path']}")
    print(f"Modèle  : {summary['model']} ({summary['dim']} dimensions), {summary['built_at']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m interview_adam.rag.ingest",
        description="(Re)construit l'index vectoriel du simulateur d'entretien (CPU uniquement).")
    parser.add_argument("--dry-run", action="store_true",
                        help="découpe et affiche la base sans calculer ni écrire d'index")
    parser.add_argument("--knowledge-dir", default=None, help="répertoire des .md (défaut : interview_adam/knowledge)")
    parser.add_argument("--json", action="store_true", help="rend le résumé en JSON pour un script")
    arguments = parser.parse_args(argv)

    try:
        summary = ingest(knowledge_dir=arguments.knowledge_dir, dry_run=arguments.dry_run)
    except AdamRagUnavailable as error:
        print(f"Echec de l'ingestion : {error}", file=sys.stderr)
        return 1

    if arguments.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
