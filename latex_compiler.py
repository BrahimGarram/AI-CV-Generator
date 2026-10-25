"""
Conversion du CV LaTeX (.tex) en PDF.

Ordre de priorité :
1. Moteur local, s'il est installé (les données restent sur la machine) :
   Tectonic (tools/tectonic/ ou PATH), puis pdflatex (MiKTeX / TeX Live).
2. API en ligne texlive.net (TeX Live officiel, gratuit, sans clé) : le document
   y est envoyé pour être compilé. Désactivable avec LATEX_ONLINE=false dans .env.
"""

import os
import shutil
import subprocess
from pathlib import Path

import requests

from config import BASE_DIR, LATEX_ONLINE, LATEX_ONLINE_URL

TOOLS_DIR = BASE_DIR / "tools"


class LatexCompileError(RuntimeError):
    pass


def _candidates():
    tectonic_local = TOOLS_DIR / "tectonic" / ("tectonic.exe" if os.name == "nt" else "tectonic")
    miktex_user = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64" / "pdflatex.exe"
    miktex_global = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "MiKTeX" / "miktex" / "bin" / "x64" / "pdflatex.exe"
    return [
        ("tectonic", str(tectonic_local) if tectonic_local.exists() else shutil.which("tectonic")),
        ("pdflatex", shutil.which("pdflatex")),
        ("pdflatex", str(miktex_user) if miktex_user.exists() else None),
        ("pdflatex", str(miktex_global) if miktex_global.exists() else None),
    ]


def find_engine():
    """Retourne (nom, chemin) du premier moteur LaTeX disponible, ou None."""
    for name, path in _candidates():
        if path:
            return name, path
    return None


def engine_status():
    engine = find_engine()
    if engine:
        return {"available": True, "engine": engine[0]}
    return {"available": LATEX_ONLINE, "engine": "texlive.net (en ligne)" if LATEX_ONLINE else None}


def compile_pdf(tex_path):
    """Compile tex_path en PDF (même dossier). Retourne le chemin du PDF ou lève LatexCompileError."""
    tex_path = Path(tex_path)
    engine = find_engine()
    if engine is None:
        if LATEX_ONLINE:
            return _compile_online(tex_path)
        raise LatexCompileError(
            "Aucun moteur LaTeX disponible : installe MiKTeX ou active LATEX_ONLINE=true dans .env."
        )
    return _compile_local(tex_path, *engine)


def _compile_online(tex_path):
    """Compilation par l'API texlive.net : envoie le .tex, reçoit le PDF."""
    try:
        response = requests.post(
            LATEX_ONLINE_URL,
            files=[
                ("filecontents[]", (None, tex_path.read_text(encoding="utf-8"))),
                ("filename[]", (None, "document.tex")),
                ("engine", (None, "pdflatex")),
                ("return", (None, "pdf")),
            ],
            timeout=(10, 120),
        )
    except requests.RequestException as error:
        raise LatexCompileError(f"Service de compilation en ligne injoignable : {error}") from error

    if response.status_code != 200 or not response.content.startswith(b"%PDF"):
        # En cas d'erreur, texlive.net renvoie le journal de compilation.
        log = response.text.splitlines()
        errors = [l for l in log if l.startswith("!")][:3] or log[-5:]
        raise LatexCompileError("Erreur de compilation LaTeX (en ligne) : " + " | ".join(errors))

    pdf = tex_path.with_suffix(".pdf")
    pdf.write_bytes(response.content)
    return pdf


def _compile_local(tex_path, name, path):
    workdir = tex_path.parent

    if name == "tectonic":
        commands = [[path, "-X", "compile", tex_path.name, "--outdir", str(workdir)]]
    else:
        args = [path, "-interaction=nonstopmode", "-halt-on-error"]
        if "miktex" in path.lower():
            args.append("-enable-installer")  # installe automatiquement les packages manquants
        commands = [args + [tex_path.name]] * 2  # 2 passes pour la mise en page

    for command in commands:
        try:
            result = subprocess.run(command, cwd=workdir, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=180)
        except subprocess.TimeoutExpired as error:
            raise LatexCompileError("La compilation LaTeX a pris trop de temps.") from error
        if result.returncode != 0:
            log = (result.stdout + result.stderr).strip().splitlines()
            errors = [l for l in log if l.startswith("!") or "error" in l.lower()][:5] or log[-8:]
            raise LatexCompileError("Erreur de compilation LaTeX : " + " | ".join(errors))

    pdf = tex_path.with_suffix(".pdf")
    if not pdf.exists():
        raise LatexCompileError("La compilation n'a pas produit de PDF.")

    # Nettoyage des fichiers auxiliaires de pdflatex.
    for ext in (".aux", ".log", ".out"):
        tex_path.with_suffix(ext).unlink(missing_ok=True)
    return pdf
