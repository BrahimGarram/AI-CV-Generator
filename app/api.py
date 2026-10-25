"""
API FastAPI de la plateforme CV Studio.

Lancer (depuis le dossier ia) :
    python -m uvicorn app.api:app --port 8000

Documentation interactive : http://localhost:8000/docs

Comptes :
    POST /auth/register   {name, email, password} -> {token, user}
    POST /auth/login      {email, password}       -> {token, user}
    GET  /auth/me                                 -> utilisateur connecté
Conversation (connexion requise : en-tête Authorization: Bearer <token>) :
    POST /sessions                   -> nouvelle conversation
    POST /sessions/{id}/messages     -> message ; si l'utilisateur demande de générer, le CV
                                        est créé et ajouté à son historique
    POST /sessions/{id}/generate     -> force la génération
Historique :
    GET    /history                  -> CV générés par l'utilisateur
    GET    /history/{id}/pdf | /tex  -> fichiers d'un CV
    DELETE /history/{id}
"""

import shutil
import sys
import threading
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import db  # noqa: E402
from agent import CVAgent  # noqa: E402
from auth import create_token, current_user, hash_password, validate_registration, verify_password  # noqa: E402
from config import GEMINI_FALLBACK_MODELS, GEMINI_MODEL, LLM_PROVIDER, OLLAMA_MODEL, USER_FILES_DIR  # noqa: E402
from latex_compiler import engine_status  # noqa: E402
from llm import LLMError, unload_ollama  # noqa: E402

app = FastAPI(
    title="CV Studio API",
    description="Conversation avec un LLM pour collecter les données, puis génération du CV "
                "(LaTeX par le modèle Qwen3-0.6B fine-tuné, puis PDF).",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,  # autorise le front-end Angular à appeler l'API
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conversations en cours, en mémoire (l'historique des CV, lui, est en base).
SESSIONS = {}
# Une seule génération à la fois : le modèle fine-tuné utilise le GPU.
GPU_LOCK = threading.Lock()


class Session:
    def __init__(self, user):
        self.user_id = user["id"]
        self.agent = CVAgent()
        # Accueil personnalisé avec le prénom de l'utilisateur connecté.
        first_name = user["name"].split()[0]
        self.agent.history[0]["content"] = self.agent.history[0]["content"].replace(
            "Bonjour !", f"Bonjour {first_name} !", 1)
        self.lock = threading.Lock()   # messages d'une même session traités dans l'ordre


# ----------------------------------------------------------------------
# Schémas
# ----------------------------------------------------------------------

class RegisterIn(BaseModel):
    name: str = Field(..., examples=["Mohamed Brahim Garram"])
    email: str = Field(..., examples=["brahim@gmail.com"])
    password: str = Field(..., examples=["motdepasse123"])


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: str
    cv_count: int = 0


class AuthOut(BaseModel):
    token: str
    user: UserOut


class MessageIn(BaseModel):
    message: str = Field(..., min_length=1, examples=["Je suis étudiant ingénieur à ESPRIT."])


class SessionOut(BaseModel):
    session_id: str
    reply: str


class GenerationOut(BaseModel):
    id: str
    title: str
    created_at: str
    has_pdf: bool
    source: str | None = None


class MessageOut(BaseModel):
    reply: str
    action: str = Field(..., description="continue | generate | cancel")
    cv: dict = Field(..., description="Données du CV collectées jusqu'ici")
    corrections: list[str] = Field(..., description="Éléments retirés par les garde-fous (inventions)")
    model: str | None = Field(None, description="Modèle LLM qui a répondu")
    seconds: float | None = None
    generated: bool = False
    generation: GenerationOut | None = None
    tex_url: str | None = None
    pdf_url: str | None = None
    pdf_error: str | None = None
    generation_source: str | None = None


class GenerateOut(BaseModel):
    generation: GenerationOut
    tex_url: str
    pdf_url: str | None
    pdf_error: str | None
    generation_source: str
    problems: list[str]


# ----------------------------------------------------------------------
# Outils
# ----------------------------------------------------------------------

def _user_out(user):
    return UserOut(**user, cv_count=db.count_generations(user["id"]))


def _get_session(session_id, user):
    session = SESSIONS.get(session_id)
    if session is None or session.user_id != user["id"]:
        raise HTTPException(404, "Conversation introuvable. Lance une nouvelle conversation.")
    return session


def _cv_title(data):
    info = data.get("personal_info") or {}
    name = " ".join(x for x in [info.get("first_name"), info.get("last_name")] if x)
    title = info.get("title")
    return " — ".join(x for x in [f"CV {name}".strip() if name else "Mon CV", title] if x)


def _generate(session, user):
    """Génère le CV (modèle fine-tuné + PDF) et l'enregistre dans l'historique de l'utilisateur."""
    from generator import generate_cv_file  # import tardif : torch n'est chargé qu'au besoin

    generation_id = uuid.uuid4().hex
    out_dir = USER_FILES_DIR / user["id"] / generation_id
    data = session.agent.data
    with GPU_LOCK:
        if LLM_PROVIDER == "ollama":
            unload_ollama()
        tex_path, pdf_path, report = generate_cv_file(data, out_dir=out_dir)

    db.add_generation(generation_id, user["id"], _cv_title(data), tex_path, pdf_path, report["source"], data)
    generation = next(g for g in db.list_generations(user["id"]) if g["id"] == generation_id)
    return GenerateOut(
        generation=GenerationOut(**generation),
        tex_url=f"/history/{generation_id}/tex",
        pdf_url=f"/history/{generation_id}/pdf" if pdf_path else None,
        pdf_error=report.get("pdf_error"),
        generation_source=report["source"],
        problems=report["problems"],
    )


# ----------------------------------------------------------------------
# Santé
# ----------------------------------------------------------------------

@app.get("/health", tags=["système"])
def health():
    return {
        "status": "ok",
        "llm_provider": LLM_PROVIDER,
        "llm_model": GEMINI_MODEL if LLM_PROVIDER == "gemini" else OLLAMA_MODEL,
        "fallback_models": GEMINI_FALLBACK_MODELS,
        "sessions": len(SESSIONS),
        "latex": engine_status(),
    }


# ----------------------------------------------------------------------
# Comptes
# ----------------------------------------------------------------------

@app.post("/auth/register", response_model=AuthOut, status_code=201, tags=["comptes"])
def register(body: RegisterIn):
    validate_registration(body.name, body.email, body.password)
    if db.get_user_by_email(body.email.strip()):
        raise HTTPException(409, "Un compte existe déjà avec cette adresse e-mail.")
    user = db.create_user(body.name.strip(), body.email.strip(), hash_password(body.password))
    return AuthOut(token=create_token(user), user=_user_out(user))


@app.post("/auth/login", response_model=AuthOut, tags=["comptes"])
def login(body: LoginIn):
    user = db.get_user_by_email(body.email.strip())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou mot de passe incorrect.")
    user = db.get_user(user["id"])  # sans le hash du mot de passe
    return AuthOut(token=create_token(user), user=_user_out(user))


@app.get("/auth/me", response_model=UserOut, tags=["comptes"])
def me(user=Depends(current_user)):
    return _user_out(user)


# ----------------------------------------------------------------------
# Conversation
# ----------------------------------------------------------------------

@app.post("/sessions", response_model=SessionOut, status_code=201, tags=["conversation"])
def create_session(user=Depends(current_user)):
    """Démarre une nouvelle conversation."""
    session_id = uuid.uuid4().hex
    session = Session(user)
    SESSIONS[session_id] = session
    return SessionOut(session_id=session_id, reply=session.agent.history[0]["content"])


@app.post("/sessions/{session_id}/messages", response_model=MessageOut, tags=["conversation"])
def send_message(session_id: str, body: MessageIn, user=Depends(current_user)):
    """Envoie un message à l'assistant. Génère le CV si l'utilisateur le demande."""
    session = _get_session(session_id, user)
    with session.lock:
        try:
            result = session.agent.handle(body.message.strip())
        except LLMError as error:
            session.agent.history.pop()  # le message pourra être renvoyé
            raise HTTPException(503, str(error)) from error

        out = MessageOut(
            reply=result["reply"],
            action=result["action"],
            cv=session.agent.data,
            corrections=result["removed"],
            model=result.get("model"),
            seconds=result.get("seconds"),
        )
        if result["action"] == "generate":
            try:
                generated = _generate(session, user)
            except Exception as error:
                raise HTTPException(500, f"Erreur pendant la génération du CV : {error}") from error
            out.generated = True
            out.generation = generated.generation
            out.tex_url = generated.tex_url
            out.pdf_url = generated.pdf_url
            out.pdf_error = generated.pdf_error
            out.generation_source = generated.generation_source
        return out


@app.post("/sessions/{session_id}/generate", response_model=GenerateOut, tags=["conversation"])
def generate_now(session_id: str, user=Depends(current_user)):
    """Force la génération du CV avec les données actuelles."""
    session = _get_session(session_id, user)
    with session.lock:
        try:
            return _generate(session, user)
        except Exception as error:
            raise HTTPException(500, f"Erreur pendant la génération du CV : {error}") from error


@app.get("/sessions/{session_id}", tags=["conversation"])
def get_session(session_id: str, user=Depends(current_user)):
    session = _get_session(session_id, user)
    return {"history": session.agent.history, "cv": session.agent.data}


@app.delete("/sessions/{session_id}", status_code=204, tags=["conversation"])
def delete_session(session_id: str, user=Depends(current_user)):
    _get_session(session_id, user)
    SESSIONS.pop(session_id, None)


# ----------------------------------------------------------------------
# Historique des CV
# ----------------------------------------------------------------------

@app.get("/history", response_model=list[GenerationOut], tags=["historique"])
def history(user=Depends(current_user)):
    return db.list_generations(user["id"])


def _owned(generation_id, user):
    generation = db.get_generation(generation_id, user["id"])
    if generation is None:
        raise HTTPException(404, "CV introuvable.")
    return generation


@app.get("/history/{generation_id}", tags=["historique"])
def history_item(generation_id: str, user=Depends(current_user)):
    generation = _owned(generation_id, user)
    return {k: generation[k] for k in ("id", "title", "created_at", "source", "cv")} | {
        "has_pdf": bool(generation["pdf_path"])}


@app.get("/history/{generation_id}/pdf", tags=["historique"])
def history_pdf(generation_id: str, user=Depends(current_user)):
    generation = _owned(generation_id, user)
    if not generation["pdf_path"] or not Path(generation["pdf_path"]).exists():
        raise HTTPException(404, "Pas de PDF pour ce CV.")
    path = Path(generation["pdf_path"])
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type="inline")


@app.get("/history/{generation_id}/tex", tags=["historique"])
def history_tex(generation_id: str, user=Depends(current_user)):
    generation = _owned(generation_id, user)
    path = Path(generation["tex_path"])
    if not path.exists():
        raise HTTPException(404, "Fichier .tex introuvable.")
    return FileResponse(path, media_type="application/x-tex", filename=path.name)


@app.delete("/history/{generation_id}", status_code=204, tags=["historique"])
def history_delete(generation_id: str, user=Depends(current_user)):
    generation = _owned(generation_id, user)
    db.delete_generation(generation_id, user["id"])
    shutil.rmtree(Path(generation["tex_path"]).parent, ignore_errors=True)
