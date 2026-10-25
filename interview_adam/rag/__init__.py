"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Sous-package RAG du simulateur d'entretien.

Ce module n'importe **ni torch ni faiss à l'import** : seul `ingest` et le premier appel
`embed()` les chargent, pour qu'un `import interview_adam.rag` dans l'API reste gratuit.
Les entrées utilisables :

    python -m interview_adam.rag.ingest             (re)construit l'index depuis knowledge/
    python -m interview_adam.rag.ingest --dry-run   parse la base, ne plonge rien
    python -m interview_adam.rag.search "DevOps engineer" --kind questions
"""
