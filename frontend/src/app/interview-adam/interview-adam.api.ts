/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';

import { API_URL } from '../config';
import { AuthService } from '../auth/auth.service';
import { CvApiService } from '../cv-api.service';
import { GenerationItem } from '../models';
import {
  EvaluateRequest,
  EvaluationOut,
  ImproveRequest,
  ImprovementOut,
  InterviewStatus,
  QuestionsOut,
  QuestionsRequest,
  SessionDetail,
  SessionSummary,
} from './models';

const BASE = `${API_URL}/interview`;

/**
 * Appels du simulateur d'entretien (le jeton est ajouté par l'intercepteur du Module 1).
 * Le CV selector réutilise `CvApiService.history()` : aucune route Module 1 n'est dupliquée.
 */
@Injectable({ providedIn: 'root' })
export class AdamInterviewApi {
  private readonly http = inject(HttpClient);
  private readonly cv = inject(CvApiService);
  private readonly auth = inject(AuthService);

  status(): Observable<InterviewStatus> {
    return this.http.get<InterviewStatus>(`${BASE}/status`).pipe(catchError(toMessage));
  }

  /** Liste des CV déjà générés (Module 1) pour personnaliser l'entretien. */
  cvHistory(): Observable<GenerationItem[]> {
    return this.cv.history();
  }

  questions(body: QuestionsRequest): Observable<QuestionsOut> {
    return this.http.post<QuestionsOut>(`${BASE}/questions`, body).pipe(catchError(toMessage));
  }

  evaluate(body: EvaluateRequest): Observable<EvaluationOut> {
    return this.http.post<EvaluationOut>(`${BASE}/evaluate`, body).pipe(catchError(toMessage));
  }

  improve(body: ImproveRequest): Observable<ImprovementOut> {
    return this.http.post<ImprovementOut>(`${BASE}/improve`, body).pipe(catchError(toMessage));
  }

  sessions(): Observable<SessionSummary[]> {
    return this.http.get<SessionSummary[]>(`${BASE}/sessions`).pipe(catchError(toMessage));
  }

  sessionDetail(id: string): Observable<SessionDetail> {
    return this.http.get<SessionDetail>(`${BASE}/sessions/${id}`).pipe(catchError(toMessage));
  }

  deleteSession(id: string): Observable<{ deleted: boolean; session_id: string }> {
    return this.http.delete<{ deleted: boolean; session_id: string }>(`${BASE}/sessions/${id}`).pipe(catchError(toMessage));
  }

  /** Rend la VRAM occupée par Mistral quand on quitte la page (fin de démonstration soignée). */
  release(): Observable<{ released: boolean; model: string }> {
    return this.http.post<{ released: boolean; model: string }>(`${BASE}/release`, {});
  }

  /**
   * Version pour la fermeture / le rechargement de l'onglet. `HttpClient` (XHR) est annulé
   * par le navigateur dès que la page se décharge : `fetch` avec `keepalive: true` survit à
   * l'événement `pagehide` et laisse la requête partir. L'intercepteur Angular ne s'applique
   * pas à un `fetch` natif, donc le jeton Bearer est posé à la main ici.
   */
  releaseOnUnload(): void {
    const token = this.auth.token();
    if (!token) return;
    // body vide : la route /release ne lit pas le corps, seul l'en-tête d'auth compte.
    fetch(`${BASE}/release`, {
      method: 'POST',
      keepalive: true,
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {
      /* non bloquant : keep_alive d'Ollama finit par décharger le modèle de toute façon */
    });
  }
}

/**
 * Messages destinés au candidat.
 * Les 503/504 et les 400 du service sont écrits en français côté serveur et portent une
 * action (redémarrer Ollama, rallonger le délai) : les remplacer par « le modèle met trop de
 * temps à répondre » ferait perdre l'information. Les 401/404 eux viennent de FastAPI et de
 * l'`HTTPBearer` en anglais — là on garde notre formulation.
 */
function toMessage(error: HttpErrorResponse) {
  const detail = serverDetail(error);
  if (error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 404 && detail) {
    return throwError(() => new Error(detail));
  }
  let message: string;
  if (error.status === 0) {
    message = "Le simulateur est momentanément indisponible. Vérifie que le backend tourne, puis réessaie.";
  } else if (error.status === 401) {
    message = 'Session expirée. Reconnecte-toi pour lancer un entretien.';
  } else if (error.status === 404) {
    message = 'Entretien introuvable. Lance une nouvelle session.';
  } else if (error.status === 503 || error.status === 504) {
    message = detail || "Le modèle d'IA met trop de temps à répondre. Réessaie dans un instant.";
  } else if (error.status >= 500) {
    message = "Une erreur est survenue pendant l'entretien. Réessaie dans un instant.";
  } else {
    message = detail || 'Une erreur est survenue.';
  }
  return throwError(() => new Error(message));
}

function serverDetail(error: HttpErrorResponse): string {
  const detail = error.error?.detail;
  return typeof detail === 'string' && detail.trim() ? detail.trim() : '';
}
