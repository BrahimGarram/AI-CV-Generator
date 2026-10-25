/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

/**
 * Contrats de l'API /interview, miroir des schémas Pydantic de `interview_adam/schemas_adam.py`.
 * Les noms restent en snake_case côté TS : c'est ce que renvoie FastAPI, sans convertisseur partagé.
 */

/** Fragment de base documentaire réellement injecté dans le prompt (preuve RAG à l'écran). */
export interface AdamRagSource {
  id: string;
  domain: string;
  title: string;
  type: string;
  difficulty: string;
  score: number;
}

/** Sous-notes 0-10 d'une évaluation ; une valeur peut être absente si le modèle ne l'a pas produite. */
export interface AdamCriteria {
  relevance: number | null;
  clarity: number | null;
  structure: number | null;
  technical_accuracy: number | null;
}

/** Trame STAR d'une réponse améliorée (comportemental). */
export interface AdamStar {
  situation: string;
  task: string;
  action: string;
  result: string;
}

export interface InterviewContext {
  job_title: string;
  company: string | null;
  seniority: string;
  question_type: string;
  language: string;
  cv_used: boolean;
}

export interface InterviewQuestion {
  index: number;
  question: string;
  category: string;
  focus: string;
  expected_points: string[];
}

/** POST /interview/questions */
export interface QuestionsOut {
  session_id: string;
  context: InterviewContext;
  questions: InterviewQuestion[];
  model: string | null;
  seconds: number | null;
  degraded: boolean;
  rag_used: boolean;
  rag_sources: AdamRagSource[];
}

/** POST /interview/evaluate */
export interface EvaluationOut {
  session_id: string;
  index: number;
  question: string;
  answer: string;
  score: number | null;
  criteria: AdamCriteria;
  strengths: string[];
  weaknesses: string[];
  verdict: string;
  model: string | null;
  seconds: number | null;
  degraded: boolean;
  rag_used: boolean;
  rag_sources: AdamRagSource[];
}

/** POST /interview/improve */
export interface ImprovementOut {
  session_id: string;
  index: number;
  improved_answer: string;
  star: AdamStar | null;
  tips: string[];
  model: string | null;
  seconds: number | null;
  degraded: boolean;
  rag_used: boolean;
  rag_sources: AdamRagSource[];
}

/** GET /interview/status — bandeau d'interface avant de lancer un entretien. */
export interface InterviewStatus {
  llm_available: boolean;
  llm_reason: string;
  model: string;
  rag_available: boolean;
  rag_reason: string;
  rag_chunks: number;
  rag_model: string | null;
  languages: string[];
  question_types: string[];
}

/** Ligne d'historique (GET /interview/sessions). */
export interface SessionSummary {
  id: string;
  job_title: string;
  company: string | null;
  seniority: string;
  question_type: string;
  language: string;
  status: string;
  n_questions: number;
  answered: number;
  average_score: number | null;
  best_index: number | null;
  weakest_index: number | null;
  created_at: string;
  finished_at: string | null;
  saved_summary: Record<string, unknown> | null;
}

/** Une question-réponse telle que rendue par le détail de session. */
export interface SessionAnswer {
  idx: number;
  question: string;
  category: string;
  focus: string | null;
  expected_points: string[];
  answer: string | null;
  score: number | null;
  criteria: AdamCriteria | null;
  strengths: string[];
  weaknesses: string[];
  verdict: string | null;
  improvement: { improved_answer: string; star: AdamStar | null; tips: string[] } | null;
}

/** GET /interview/sessions/{id} */
export interface SessionDetail extends SessionSummary {
  cv_used: boolean;
  model: string | null;
  answers: SessionAnswer[];
  advice: string[];
}

/** Corps de POST /interview/questions (voir QuestionsIn côté serveur). */
export interface QuestionsRequest {
  job_title: string;
  job_description: string | null;
  company: string | null;
  seniority: string;
  question_type: string;
  n_questions: number;
  language: string;
  use_cv: boolean;
  cv_generation_id: string | null;
}

/** Corps de POST /interview/evaluate (voir EvaluateIn côté serveur). */
export interface EvaluateRequest {
  session_id: string;
  index: number;
  answer: string;
}

/** Corps de POST /interview/improve (voir ImproveIn côté serveur). */
export interface ImproveRequest {
  session_id: string;
  index: number;
}
