"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Prompt de réparation : deuxième tentative quand la sortie du modèle n'est pas un JSON
conforme (Pydantic a rejeté, ou le parse a échoué).

Mode `raw=true` sans mémoire de contexte : la consigne de réparation est donc collée à la
suite du prompt d'origine, avec la sortie fautive en référence. Une seule tentative de
réparation, puis repli déterministe côté service.
"""

from interview_adam.prompts import base_adam as base
from interview_adam.security import clip

REPAIR_HEADER = """CONSIGNE DE FORMAT (rappel, obligatoire)
Ta réponse précédente n'était pas un objet JSON conforme au schéma demandé.
Renvoie MAINTENANT uniquement le JSON corrigé :
- même contenu informationnel que ta réponse précédente, mais mise en forme corrigée ;
- aucun texte avant ou après, aucun bloc Markdown, aucune clé manquante, aucun commentaire ;
- guillemets doubles pour les clés et les chaînes, virgules correctes, tableaux entre crochets."""


def build(original_prompt, invalid_output, error_message, schema):
    """
    `original_prompt` est le prompt complet déjà envoyé (au format `[INST]…[/INST]`).
    On ne renvoie pas `[/INST]` deux fois : on ferme le bloc d'origine, puis on rouvre
    un bloc `[INST]` de correction, ce qui correspond à la conversation attendue par Mistral.
    """
    head = original_prompt.rstrip()
    if head.endswith("[/INST]"):
        head = head[:-len("[/INST]")].rstrip()
        opened = True
    else:
        opened = False

    instruction = "\n\n".join(x for x in (
        REPAIR_HEADER,
        f"Motif de rejet : {clip(str(error_message or 'JSON invalide'), 400)}",
        base.schema_contract(schema),
        "Réponse fautive à corriger :\n" + base.block(
            "sortie_precedente", clip(str(invalid_output or ""), 1600)),
    ) if x)

    if opened:
        return f"{head} [/INST]\n\n{instruction}\n\nJSON corrigé :"
    return f"{head}\n\n{instruction}\n\nJSON corrigé :"
