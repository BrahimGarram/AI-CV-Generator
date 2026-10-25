import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';

import { API_URL } from './config';
import { GenerateResponse, GenerationItem, MessageResponse, SessionResponse } from './models';

/** Appels au backend FastAPI (le jeton est ajouté par l'intercepteur). */
@Injectable({ providedIn: 'root' })
export class CvApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<{ status: string; llm_provider: string; llm_model: string }> {
    return this.http.get<{ status: string; llm_provider: string; llm_model: string }>(`${API_URL}/health`);
  }

  // ---------------- Conversation ----------------

  createSession(): Observable<SessionResponse> {
    return this.http.post<SessionResponse>(`${API_URL}/sessions`, {}).pipe(catchError(toMessage));
  }

  sendMessage(sessionId: string, message: string): Observable<MessageResponse> {
    return this.http
      .post<MessageResponse>(`${API_URL}/sessions/${sessionId}/messages`, { message })
      .pipe(catchError(toMessage));
  }

  generate(sessionId: string): Observable<GenerateResponse> {
    return this.http
      .post<GenerateResponse>(`${API_URL}/sessions/${sessionId}/generate`, {})
      .pipe(catchError(toMessage));
  }

  // ---------------- Historique ----------------

  history(): Observable<GenerationItem[]> {
    return this.http.get<GenerationItem[]>(`${API_URL}/history`).pipe(catchError(toMessage));
  }

  deleteGeneration(id: string): Observable<void> {
    return this.http.delete<void>(`${API_URL}/history/${id}`).pipe(catchError(toMessage));
  }

  /** Récupère un fichier protégé (PDF, .tex) : `path` est une route relative renvoyée par l'API. */
  getFile(path: string): Observable<Blob> {
    return this.http.get(`${API_URL}${path}`, { responseType: 'blob' }).pipe(catchError(toMessage));
  }
}

/** Transforme une erreur HTTP en message lisible pour l'utilisateur. */
function toMessage(error: HttpErrorResponse) {
  // Messages destinés au client : aucun détail technique (modèles, serveur, LaTeX).
  let message: string;
  if (error.status === 0) {
    message = 'Le service est momentanément indisponible. Réessaie dans quelques instants.';
  } else if (error.status === 404 && /sessions/.test(error.url ?? '')) {
    message = 'Cette conversation a expiré. Lance un nouveau CV pour continuer.';
  } else if (error.status === 503) {
    message = "L'assistant est très sollicité en ce moment. Réessaie dans une minute.";
  } else if (error.status >= 500) {
    message = 'Une erreur est survenue. Réessaie dans un instant.';
  } else if (error.status === 404) {
    message = 'Élément introuvable.';
  } else {
    message = (error.error && typeof error.error.detail === 'string' && error.error.detail) || 'Une erreur est survenue.';
  }
  return throwError(() => new Error(message));
}
