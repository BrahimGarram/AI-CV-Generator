"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Configuration du simulateur d'entretien (variables d'environnement propres au module).

Le module ne lit ni n'écrit jamais `LLM_PROVIDER` : la sélection Gemini/Ollama du Module 1
reste inchangée. Mistral est servi par Ollama sur sa propre URL, configurable indépendamment.

Les variables (voir .env.example) :
    MISTRAL_BASE_URL, MISTRAL_MODEL, MISTRAL_API_KEY
    ADAM_TIMEOUT_READ (alias de l'ancien ADAM_MISTRAL_TIMEOUT_READ),
    ADAM_MISTRAL_TIMEOUT_CONNECT, ADAM_MISTRAL_RETRIES,
    ADAM_MISTRAL_BACKOFF_BASE, ADAM_MISTRAL_KEEP_ALIVE, ADAM_MISTRAL_NUM_GPU,
    ADAM_MISTRAL_NUM_CTX, ADAM_MAX_CONCURRENT_LLM_CALLS, ADAM_MAX_NEW_TOKENS,
    ADAM_QUESTIONS_BASE_TOKENS, ADAM_QUESTIONS_TOKENS_PER_QUESTION,
    ADAM_EVALUATE_MAX_TOKENS, ADAM_IMPROVE_MAX_TOKENS,
    ADAM_MAX_CV_DIGEST_CHARS, ADAM_MAX_RAG_CONTEXT_CHARS, ADAM_MAX_RAG_CHUNK_CHARS, ADAM_RAG_TOP_K,
    ADAM_REDACT_ORGS, ADAM_DB_PATH
"""

import os
from pathlib import Path

from config import BASE_DIR, DATA_DIR, DB_PATH

# ----------------------------------------------------------------------
# Lecture d'environnement défensive : une valeur mal formatée ne doit jamais
# empêcher l'application de démarrer (cours sur machine étudiante).
# ----------------------------------------------------------------------


def _env(key, default):
    value = os.environ.get(key)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_int(key, default):
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key, default):
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key, default=False):
    return _env(key, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


def _env_first(keys, default):
    """Première variable non vide dans `keys` ; sinon `default`. Permet un alias récent devant un nom hérité."""
    for key in keys:
        value = os.environ.get(key)
        if value is not None and value.strip():
            return value.strip()
    return default


def _env_float_first(keys, default):
    try:
        return float(_env_first(keys, str(default)))
    except ValueError:
        return default


# ----------------------------------------------------------------------
# Fournisseur Mistral (Ollama)
# ----------------------------------------------------------------------

MISTRAL_BASE_URL = _env("MISTRAL_BASE_URL", "http://localhost:11434").rstrip("/")
MISTRAL_MODEL = _env("MISTRAL_MODEL", "mistral:7b-instruct-v0.2-q4_K_M")
# Optionnel : Ollama local n'en a pas besoin. Utilisé seulement si un proxy distant
# exige un en-tête Authorization: Bearer.
MISTRAL_API_KEY = _env("MISTRAL_API_KEY", "")

# Les URL d'API sont construites par AdamMistralClient à partir de MISTRAL_BASE_URL
# (/api/generate pour les prompts, /api/tags pour le contrôle de disponibilité).

# (connexion, lecture). Le read timeout d'`requests` est un délai MAXIMUM ENTRE DEUX OCTETS
# lus sur le socket, pas une durée totale : avec `stream=false` Ollama n'écrit la réponse
# qu'une fois la génération finie, donc un read timeout = plafond de génération. En CPU une
# génération froide (chargement du modèle) dépasse facilement 180 s : on relève le plafond à
# 600 pour que l'appel aboutisse au lieu de repartir en retry. Nom récent `ADAM_TIMEOUT_READ`,
# l'ancien `ADAM_MISTRAL_TIMEOUT_READ` reste accepté.
TIMEOUT_CONNECT = _env_float("ADAM_MISTRAL_TIMEOUT_CONNECT", 10.0)
TIMEOUT_READ = _env_float_first(["ADAM_TIMEOUT_READ", "ADAM_MISTRAL_TIMEOUT_READ"], 600.0)

RETRIES = _env_int("ADAM_MISTRAL_RETRIES", 2)          # tentatives supplémentaires après l'échec initial
BACKOFF_BASE = _env_float("ADAM_MISTRAL_BACKOFF_BASE", 3.0)  # secondes, multipliées par la tentative

# Durée de rétention du modèle en VRAM après un appel. Courte par défaut :
# le Module 1 charge Qwen3-0.6B + LoRA sur le même GPU (4 Go sur les portables
# d'équipe) et son déchargement automatique ne concerne que son propre modèle.
KEEP_ALIVE = _env("ADAM_MISTRAL_KEEP_ALIVE", "5m")

# -1 = Ollama décide (défaut, adapté aux machines avec assez de VRAM).
# 0  = CPU uniquement : aucune contention GPU avec le générateur LaTeX.
# Sur une carte 4 Go partagée avec le Module 1, 0 est le réglage recommandé (voir .env.example) :
# les couches que tiennent dans 4 Go ne suffisent pas à accélérer une génération utile sans
# évincer Qwen ; le CPU est plus lent mais ne fait jamais planer l'entretien par OOM.
NUM_GPU = _env_int("ADAM_MISTRAL_NUM_GPU", -1)
NUM_CTX = _env_int("ADAM_MISTRAL_NUM_CTX", 8192)
# Plafond global de tokens de sortie ; les budgets par étape ci-dessous le réduisent encore.
MAX_NEW_TOKENS = _env_int("ADAM_MAX_NEW_TOKENS", 1400)

# Budgets num_predict par étape (item de la passe de performance) : un 7 B en CPU produit
# ~4-9 tokens/s, donc chaque token superflu est de la seconde d'attente en démonstration.
# Questions : proportionnel au nombre demandé (une question + expected_points ~ 150 tokens),
# plafonné par MAX_NEW_TOKENS. Évaluation et amélioration : sorties courtes et bornées.
QUESTIONS_BASE_TOKENS = _env_int("ADAM_QUESTIONS_BASE_TOKENS", 120)
QUESTIONS_TOKENS_PER_QUESTION = _env_int("ADAM_QUESTIONS_TOKENS_PER_QUESTION", 170)
EVALUATE_MAX_TOKENS = _env_int("ADAM_EVALUATE_MAX_TOKENS", 420)
IMPROVE_MAX_TOKENS = _env_int("ADAM_IMPROVE_MAX_TOKENS", 520)

# Un seul appel à la fois par défaut : un 7 B sur un portable partage la carte
# avec le modèle de génération de CV du Module 1.
MAX_CONCURRENT_LLM_CALLS = _env_int("ADAM_MAX_CONCURRENT_LLM_CALLS", 1)
SEMAPHORE_TIMEOUT = _env_float("ADAM_SEMAPHORE_TIMEOUT", TIMEOUT_READ + 60)

# ----------------------------------------------------------------------
# Confidentialité
# ----------------------------------------------------------------------

# Noms d'entreprises et d'écoles : conservés par défaut (ils servent à contextualiser
# les questions). À true, les valeurs sont remplacées par un libellé neutre.
REDACT_ORGS = _env_bool("ADAM_REDACT_ORGS", False)

# ----------------------------------------------------------------------
# bornes d'entrée (anti-injection et coût mémoire/contenu)
# ----------------------------------------------------------------------

MAX_JOB_TITLE_CHARS = 200
MAX_JOB_DESCRIPTION_CHARS = _env_int("ADAM_MAX_JOB_DESCRIPTION_CHARS", 2400)
MAX_COMPANY_CHARS = 200
MAX_QUESTIONS = 15
MIN_QUESTIONS = 3
MAX_ANSWER_CHARS = 4000
MAX_QUESTION_CHARS = 600
# Digest du CV et contexte RAG bornés bas : ce sont les deux plus gros contributeurs à la
# taille du prompt, et au-delà de ces volumes le modèle perd le fil tout en préfillant plus
# lentement. Le digest tient l'essentiel (profil, dernières expériences, compétences) ; les
# fiches RAG ne sont que des références, deux fragments courts suffisent.
MAX_CV_DIGEST_CHARS = _env_int("ADAM_MAX_CV_DIGEST_CHARS", 1200)
MAX_RAG_CONTEXT_CHARS = _env_int("ADAM_MAX_RAG_CONTEXT_CHARS", 900)

# ----------------------------------------------------------------------
# Base de données : même fichier SQLite que la plateforme, connexion séparée.
# ADAM_DB_PATH permet de pointer un fichier jetable pendant les tests.
# ----------------------------------------------------------------------

DB_FILE = Path(_env("ADAM_DB_PATH", str(DB_PATH)))

MODULE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = MODULE_DIR / "knowledge"

# Artefact régénérable (non versionné, data/ est ignoré par git) :
# l'index vectoriel est reconstruit par `python -m interview_adam.rag.ingest`.
RAG_DIR = DATA_DIR / "interview_adam"
RAG_INDEX_PATH = RAG_DIR / "knowledge.faiss"
RAG_META_PATH = RAG_DIR / "knowledge_meta.json"
EMBEDDING_MODEL = _env("ADAM_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Nombre de fragments injectés dans un prompt, et le seuil en dessous duquel on préfère
# n'en injecter aucun. Le seuil est calé sur les scores réels de all-MiniLM-L6-v2 sur cette
# base : un bon domaine marque 0,28-0,60, un hors-sujet reste sous 0,15. En dessous de 0,20
# on injecterait du bruit ; au-dessus de 0,30 on perdrait des récupérations correctes.
RAG_TOP_K = _env_int("ADAM_RAG_TOP_K", 2)
# Chaque fragment injecté est lui-même borné : une fiche entière fait ~1,5 k caractères, on
# n'en garde que l'amorce (suffisante comme référence de barème) pour tenir le budget prompt.
MAX_RAG_CHUNK_CHARS = _env_int("ADAM_MAX_RAG_CHUNK_CHARS", 340)
RAG_MIN_SCORE = _env_float("ADAM_RAG_MIN_SCORE", 0.20)
# On sur-échantillonne avant de reclasser par domaine : le filtre de domaine serait sinon
# un tri après coup qui ferait disparaître les bons résultats d'un domaine non prioritaire.
RAG_CANDIDATES = _env_int("ADAM_RAG_CANDIDATES", 9)
# Filtre optionnel : n'injecter un fragment que s'il partage au moins un mot réel avec la
# requête. Pensé pour un plongeur lexical (ou un proxy de test) dont le bruit de hachage
# renvoie des hors-sujets non nuls. Par défaut désactivé avec all-MiniLM-L6-v2 : un plongeur
# dense rapproche utilement des synonymes sans mot commun, et imposer le recouvrement lexical
# jetterait ces bons résultats. Mesuré sur la base réelle : seule une requête absurde
# (« qqq www zzz ») passe le seuil de 0,20 sans recouvrement ; elle n'arrive pas dans un
# entretien. Activer ADAM_RAG_REQUIRE_OVERLAP=1 si on préfère la garantie à la nuance.
RAG_REQUIRE_OVERLAP = _env_bool("ADAM_RAG_REQUIRE_OVERLAP", False)

DEFAULT_LANGUAGE = "fr"
LANGUAGES = ("fr", "en")
QUESTION_TYPES = ("technical", "hr", "mixed")

__all__ = [
    "BASE_DIR", "DATA_DIR", "MODULE_DIR", "KNOWLEDGE_DIR", "RAG_DIR",
    "RAG_INDEX_PATH", "RAG_META_PATH", "EMBEDDING_MODEL",
    "RAG_TOP_K", "MAX_RAG_CHUNK_CHARS", "RAG_MIN_SCORE", "RAG_CANDIDATES", "RAG_REQUIRE_OVERLAP",
    "MISTRAL_BASE_URL", "MISTRAL_MODEL", "MISTRAL_API_KEY",
    "TIMEOUT_CONNECT", "TIMEOUT_READ", "RETRIES", "BACKOFF_BASE", "KEEP_ALIVE",
    "NUM_GPU", "NUM_CTX", "MAX_NEW_TOKENS", "MAX_CONCURRENT_LLM_CALLS", "SEMAPHORE_TIMEOUT",
    "QUESTIONS_BASE_TOKENS", "QUESTIONS_TOKENS_PER_QUESTION", "EVALUATE_MAX_TOKENS", "IMPROVE_MAX_TOKENS",
    "REDACT_ORGS", "DB_FILE",
    "MAX_JOB_TITLE_CHARS", "MAX_JOB_DESCRIPTION_CHARS", "MAX_COMPANY_CHARS", "MAX_QUESTIONS",
    "MIN_QUESTIONS", "MAX_ANSWER_CHARS", "MAX_QUESTION_CHARS", "MAX_CV_DIGEST_CHARS",
    "MAX_RAG_CONTEXT_CHARS",
    "DEFAULT_LANGUAGE", "LANGUAGES", "QUESTION_TYPES",
]
