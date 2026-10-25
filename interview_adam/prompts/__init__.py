"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Prompts du simulateur d'entretien (Mistral, format `[INST]`).

Trois prompts métier + un prompt de réparation :
    adam_questions.build(...)  -> génération des questions adaptées au poste
    adam_evaluate.build(...)   -> score 0-10, critères, forces, faiblesses, verdict
    adam_improve.build(...)    -> réponse améliorée (STAR pour le comportemental)
    repair.build(...)          -> seconde tentative après sortie JSON non conforme
"""

from interview_adam.prompts import adam_evaluate, adam_improve, adam_questions, base_adam, repair

__all__ = ["base_adam", "adam_questions", "adam_evaluate", "adam_improve", "repair"]
