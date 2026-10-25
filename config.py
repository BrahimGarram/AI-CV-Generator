import os
from pathlib import Path

# Dossier racine du projet
BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path):
    """Charge les variables d'un fichier .env (KEY=valeur) sans dépendance externe."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# ---- LLM de conversation / extraction ----
# "gemini" (API, recommandé) ou "ollama" (local, hors ligne)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Essayés dans l'ordre si le modèle principal est surchargé, sans quota ou ne répond pas
# (le quota gratuit est compté par modèle : plusieurs modèles = plus de messages par jour).
GEMINI_FALLBACK_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite,gemini-2.5-flash").split(",") if m.strip()]
GEMINI_THINKING_BUDGET = int(os.environ.get("GEMINI_THINKING_BUDGET", "0"))  # 0 = plus rapide

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE}/api/chat"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")

# ---- Modèle générateur LaTeX (fine-tuné) ----
BASE_MODEL = "Qwen/Qwen3-0.6B"
OUTPUT_DIR = BASE_DIR / "output"
ADAPTER_PATH = OUTPUT_DIR / "cv-latex-lora"

# ---- Dataset ----
DATASET_DIR = BASE_DIR / "dataset"
TRAIN_FILE = DATASET_DIR / "cv_latex_train.jsonl"
VAL_FILE = DATASET_DIR / "cv_latex_val.jsonl"

# ---- Conversion LaTeX -> PDF ----
# Sans moteur LaTeX local, le PDF est compilé par l'API en ligne texlive.net.
LATEX_ONLINE = os.environ.get("LATEX_ONLINE", "true").lower() == "true"
LATEX_ONLINE_URL = os.environ.get("LATEX_ONLINE_URL", "https://texlive.net/cgi-bin/latexcgi")

# ---- CV générés ----
CV_OUTPUT_DIR = OUTPUT_DIR / "cv"

# ---- Plateforme : utilisateurs et historique ----
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cv_platform.db"
USER_FILES_DIR = DATA_DIR / "users"   # un dossier par utilisateur pour ses CV
JWT_HOURS = int(os.environ.get("JWT_HOURS", str(24 * 7)))


def _jwt_secret():
    """Clé de signature des jetons : .env (JWT_SECRET) ou générée une fois dans data/."""
    if os.environ.get("JWT_SECRET"):
        return os.environ["JWT_SECRET"]
    import secrets

    path = DATA_DIR / "jwt_secret.key"
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


JWT_SECRET = _jwt_secret()
