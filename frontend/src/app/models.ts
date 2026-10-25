export interface PersonalInfo {
  first_name: string | null;
  last_name: string | null;
  title: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  linkedin: string | null;
  github: string | null;
}

export interface Education {
  degree: string | null;
  field: string | null;
  institution: string | null;
  location: string | null;
  start: string | null;
  end: string | null;
}

export interface Experience {
  role: string | null;
  company: string | null;
  location: string | null;
  start: string | null;
  end: string | null;
  description: string | null;
}

export interface Project {
  name: string | null;
  description: string | null;
  technologies: string[];
}

export interface CvData {
  personal_info: PersonalInfo;
  profile: string | null;
  education: Education[];
  experiences: Experience[];
  projects: Project[];
  skills: { category: string; items: string[] }[];
  languages: { name: string; level: string | null }[];
  certifications: { name: string | null; issuer: string | null; year: string | null }[];
  interests: string[];
}

export interface SessionResponse {
  session_id: string;
  reply: string;
}

/** CV enregistré dans l'historique de l'utilisateur. */
export interface GenerationItem {
  id: string;
  title: string;
  created_at: string;
  has_pdf: boolean;
  source: string | null;
}

export interface MessageResponse {
  reply: string;
  action: 'continue' | 'generate' | 'cancel';
  cv: CvData;
  corrections: string[];
  model: string | null;
  seconds: number | null;
  generated: boolean;
  generation: GenerationItem | null;
  tex_url: string | null;
  pdf_url: string | null;
  pdf_error: string | null;
  generation_source: 'model' | 'fallback' | null;
}

export interface GenerateResponse {
  generation: GenerationItem;
  tex_url: string;
  pdf_url: string | null;
  pdf_error: string | null;
  generation_source: 'model' | 'fallback';
  problems: string[];
}

/** CV généré, prêt à être affiché et téléchargé. */
export interface GeneratedCv {
  pdfObjectUrl: string | null; // URL locale (blob) du PDF
  fileName: string; // nom du PDF
  texUrl: string; // route API du .tex (source)
  generationId?: string; // identifiant dans l'historique
  pdfError: string | null; // raison si le PDF n'a pas pu être créé
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'error' | 'cv';
  content: string;
  time: Date;
  cv?: GeneratedCv;
  model?: string | null; // modèle LLM qui a produit la réponse
  seconds?: number | null;
}
