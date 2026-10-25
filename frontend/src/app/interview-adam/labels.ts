/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

/** Libellés français des codes échangés avec le backend (aucune logique métier ici). */

const SENIORITY: Record<string, string> = { junior: 'Junior', inter: 'Confirmé', senior: 'Senior', lead: 'Lead' };
const TYPE: Record<string, string> = { technical: 'Technique', hr: 'Comportemental', mixed: 'Mixte' };
const CATEGORY: Record<string, string> = { technical: 'Technique', hr: 'Comportemental', project: 'Projet' };
const LANGUAGE: Record<string, string> = { fr: 'Français', en: 'Anglais' };

export const SENIORITY_OPTIONS = Object.keys(SENIORITY).map((value) => ({ value, label: SENIORITY[value] }));
export const TYPE_OPTIONS = Object.keys(TYPE).map((value) => ({ value, label: TYPE[value] }));

export function seniorityLabel(code: string): string {
  return SENIORITY[code] ?? code;
}

export function typeLabel(code: string): string {
  return TYPE[code] ?? code;
}

export function categoryLabel(code: string): string {
  return CATEGORY[code] ?? code;
}

export function languageLabel(code: string): string {
  return LANGUAGE[code] ?? code;
}

/** Classe CSS selon la note 0-10 : vert au-dessus de 7, ambre entre 5 et 7, rouge en dessous. */
export function scoreTone(score: number | null | undefined): 'good' | 'mid' | 'bad' | 'none' {
  if (score === null || score === undefined) return 'none';
  if (score >= 7) return 'good';
  if (score >= 5) return 'mid';
  return 'bad';
}

/** Une note n'a de sens affichée qu'avec un chiffre ; on arrondit au demi pour tenir sur une ligne. */
export function formatScore(score: number | null | undefined): string {
  return score === null || score === undefined ? '—' : `${Math.round(score * 2) / 2}/10`;
}
