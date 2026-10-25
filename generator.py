"""
Génération du CV en LaTeX avec le modèle fine-tuné (Qwen3-0.6B + LoRA).
"""

import re
import unicodedata
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import ADAPTER_PATH, BASE_MODEL, CV_OUTPUT_DIR
from cv_schema import clean_cv
from latex import escape_cv, render_body, repair_body, validate_body, wrap_document
from latex_compiler import LatexCompileError, compile_pdf, engine_status
from prompts import build_messages

MAX_NEW_TOKENS = 1100

_tokenizer = None
_model = None


def load_generator():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model

    if not (ADAPTER_PATH / "adapter_config.json").is_file():
        raise FileNotFoundError(
            f"Adaptateur introuvable dans {ADAPTER_PATH}. Lance d'abord : python train.py"
        )

    use_cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if use_cuda and torch.cuda.is_bf16_supported() else (
        torch.float16 if use_cuda else torch.float32
    )

    print(f"Chargement du générateur ({BASE_MODEL} + LoRA)...")
    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        dtype=dtype,
        device_map={"": 0} if use_cuda else None,
    )
    # Fusion de l'adaptateur : génération plus rapide.
    _model = PeftModel.from_pretrained(base, str(ADAPTER_PATH)).merge_and_unload()
    _model.eval()
    return _tokenizer, _model


def generate_body(escaped_data):
    """Appelle le modèle fine-tuné et retourne le corps LaTeX brut."""
    return generate_from_messages(build_messages(escaped_data))


def generate_from_messages(messages):
    tokenizer, model = load_generator()

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            eos_token_id=tokenizer.convert_tokens_to_ids("<|im_end|>"),
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )

    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    # Sécurité si le modèle produit quand même un bloc de réflexion.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


def build_cv_tex(data):
    """
    Retourne (document_tex, rapport).
    rapport = {"source": "model" | "fallback", "problems": [...]}
    """
    data = clean_cv(data)
    escaped = escape_cv(data)

    problems = []
    try:
        body = repair_body(generate_body(escaped), escaped)
        problems = validate_body(body, escaped)
    except Exception as error:  # GPU absent, mémoire insuffisante, ...
        body, problems = "", [f"Erreur du modèle : {error}"]

    source = "model"
    if problems:
        # Rendu de référence : toujours valide, sans reformulation.
        body = render_body(escaped)
        source = "fallback"

    return wrap_document(body), {"source": source, "problems": problems}


def _file_stem(data):
    info = data.get("personal_info") or {}
    name = "_".join(x for x in [info.get("first_name"), info.get("last_name")] if x) or "cv"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "cv_" + re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower()


def generate_cv_file(data, out_dir=None):
    """
    Génère le .tex puis le PDF.
    out_dir : dossier de sortie (par défaut output/cv ; l'API utilise un dossier par utilisateur).
    Retourne (tex_path, pdf_path | None, rapport). rapport["pdf_error"] explique un PDF manquant.
    """
    document, report = build_cv_tex(data)
    out_dir = Path(out_dir) if out_dir else CV_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / f"{_file_stem(data)}.tex"
    tex_path.write_text(document, encoding="utf-8")
    tex_path.with_suffix(".pdf").unlink(missing_ok=True)  # pas d'ancien PDF d'une génération précédente

    report["pdf_error"] = None
    try:
        pdf_path = compile_pdf(tex_path)
    except LatexCompileError as error:
        pdf_path = None
        report["pdf_error"] = str(error)
        # Le LaTeX du modèle ne compile pas : on réessaie avec le rendu de référence.
        if report["source"] == "model" and engine_status()["available"]:
            tex_path.write_text(wrap_document(render_body(escape_cv(clean_cv(data)))), encoding="utf-8")
            try:
                pdf_path = compile_pdf(tex_path)
                report.update(source="fallback", pdf_error=None)
                report["problems"].append(f"Compilation du LaTeX du modèle impossible : {error}")
            except LatexCompileError as second:
                report["pdf_error"] = str(second)
    return tex_path, pdf_path, report
