"""
Évalue le modèle fine-tuné sur le jeu de validation.

    python evaluate.py            # 20 exemples
    python evaluate.py --n 60

Mesures :
- valide     : la sortie passe validate_body (LaTeX sûr, rien d'inventé) ;
- identique  : la sortie est exactement la réponse attendue ;
- similarité : ressemblance moyenne avec la réponse attendue (0 à 1).
"""

import argparse
import json
import re
from difflib import SequenceMatcher

from config import CV_OUTPUT_DIR, VAL_FILE
from generator import generate_from_messages
from latex import validate_body, wrap_document


def identity_from_prompt(prompt_text):
    """Minimum nécessaire à validate_body, reconstruit depuis le texte d'entrée."""
    info = {}
    for key, label in [("first_name", "prenom"), ("last_name", "nom"), ("email", "email")]:
        match = re.search(rf"^{label}: (.*)$", prompt_text, re.MULTILINE)
        info[key] = match.group(1) if match else None
    return {"personal_info": info, "source": prompt_text}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()

    records = [json.loads(l) for l in VAL_FILE.open(encoding="utf-8") if l.strip()][: args.n]
    valid = exact = 0
    similarities = []
    CV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, record in enumerate(records, start=1):
        prompt, expected = record["messages"][:2], record["messages"][2]["content"]
        output = generate_from_messages(prompt)

        problems = validate_body(output, identity_from_prompt(prompt[1]["content"]))
        same = output.strip() == expected.strip()
        sim = SequenceMatcher(None, output, expected).ratio()

        valid += not problems
        exact += same
        similarities.append(sim)
        print(f"[{i:02d}] valide={not problems!s:5} identique={same!s:5} "
              f"similarité={sim:.3f} {problems[:2] if problems else ''}")

        if i <= 3:
            (CV_OUTPUT_DIR / f"eval_{i:02d}.tex").write_text(wrap_document(output), encoding="utf-8")

    n = len(records)
    print("\n" + "=" * 40)
    print(f"Valides    : {valid}/{n} ({100 * valid / n:.0f} %)")
    print(f"Identiques : {exact}/{n} ({100 * exact / n:.0f} %)")
    print(f"Similarité : {sum(similarities) / n:.3f}")
    print(f"Exemples écrits dans {CV_OUTPUT_DIR} (eval_01.tex ...)")


if __name__ == "__main__":
    main()
