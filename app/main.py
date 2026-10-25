"""
Assistant de création de CV en ligne de commande.

    python -m app.main            (depuis le dossier ia)
    python -m app.main --debug    (affiche le CV collecté et les corrections des garde-fous)

1. Le LLM de conversation (Gemini 2.5 Flash, ou Ollama) discute et collecte les données.
2. Le modèle Qwen3-0.6B fine-tuné génère le CV au format LaTeX (.tex).
"""

import json
import sys
from pathlib import Path

# Permet aussi : python app/main.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import WELCOME, CVAgent  # noqa: E402
from config import LLM_PROVIDER  # noqa: E402
from llm import LLMError, unload_ollama  # noqa: E402

DEBUG = "--debug" in sys.argv


def generate(agent):
    # Le générateur est importé ici : torch ne se charge qu'au moment voulu.
    from generator import generate_cv_file

    if LLM_PROVIDER == "ollama":
        unload_ollama()  # libère la VRAM pour le générateur
    tex_path, pdf_path, report = generate_cv_file(agent.data)

    print(f"\nCV LaTeX enregistré : {tex_path}")
    if pdf_path:
        print(f"PDF compilé : {pdf_path}")
    else:
        print("Pour obtenir le PDF : compile le .tex avec pdflatex (MiKTeX / TeX Live) ou Overleaf.")
    if report["source"] == "fallback":
        print("Remarque : la sortie du modèle était invalide, le rendu de référence a été utilisé.")
        if DEBUG:
            print("[DEBUG] Problèmes :", report["problems"])


def main():
    agent = CVAgent()

    print("=== Assistant de création de CV ===")
    print("Tape 'quitter' pour arrêter.\n")
    print("Assistant :", WELCOME)

    while True:
        try:
            message = input("\nToi : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAssistant : À bientôt !")
            break

        if not message:
            continue
        if message.lower() in {"quitter", "quit", "exit"}:
            print("Assistant : À bientôt !")
            break

        try:
            result = agent.handle(message)
        except LLMError as error:
            print("\n[Erreur]", error)
            agent.history.pop()  # le message sera renvoyé
            continue

        print("\nAssistant :", result["reply"])
        if DEBUG:
            print("[DEBUG] action :", result["action"], "| corrigé par les garde-fous :", result["removed"])
            print("[DEBUG] CV :", json.dumps(agent.data, ensure_ascii=False))

        if result["action"] == "cancel":
            break
        if result["action"] == "generate":
            try:
                generate(agent)
            except Exception as error:
                print("\nErreur pendant la génération du CV :", error)
            break


if __name__ == "__main__":
    main()
