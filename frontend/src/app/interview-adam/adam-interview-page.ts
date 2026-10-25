/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AdamInterviewApi } from './interview-adam.api';
import { InterviewStatus, QuestionsOut } from './models';
import { AdamInterviewHistory } from './adam-interview-history';
import { AdamInterviewRun } from './adam-interview-run';
import { AdamInterviewSetup } from './adam-interview-setup';

type Mode = 'setup' | 'run' | 'history';

/**
 * Page /interview — Module 3 « AI Job Interview Simulator ».
 * Orchestre préparation, déroulé et historique ; libère la VRAM du modèle en quittant la page
 * pour rendre immédiatement la carte graphique au générateur de CV (Module 1).
 */
@Component({
  selector: 'app-adam-interview-page',
  imports: [RouterLink, AdamInterviewSetup, AdamInterviewRun, AdamInterviewHistory],
  templateUrl: './adam-interview-page.html',
  styleUrl: './adam-interview-page.scss',
})
export class AdamInterviewPage implements OnInit, OnDestroy {
  private readonly api = inject(AdamInterviewApi);
  private unloadFired = false;

  readonly mode = signal<Mode>('setup');
  readonly status = signal<InterviewStatus | null>(null);
  readonly result = signal<QuestionsOut | null>(null);

  ngOnInit(): void {
    this.api.status().subscribe({
      next: (s) => this.status.set(s),
      error: () => this.status.set(null),
    });
    // Fermeture / rechargement d'onglet : seul un fetch keepalive survit au déchargement.
    window.addEventListener('pagehide', this.onUnload);
  }

  ngOnDestroy(): void {
    window.removeEventListener('pagehide', this.onUnload);
    // Navigation interne (ex. retour à l'éditeur via routerLink) : la page vit encore, HttpClient marche.
    // Échec toléré : keep_alive d'Ollama finit de toute façon par décharger le modèle.
    this.api.release().subscribe({ next: () => {}, error: () => {} });
  }

  /** Libère la VRAM au déchargement, une seule fois, via fetch keepalive (voir AdamInterviewApi). */
  private readonly onUnload = (): void => {
    if (this.unloadFired) return;
    this.unloadFired = true;
    this.api.releaseOnUnload();
  };

  startRun(out: QuestionsOut): void {
    this.result.set(out);
    this.mode.set('run');
  }

  newInterview(): void {
    this.result.set(null);
    this.mode.set('setup');
  }

  leaveRun(): void {
    this.result.set(null);
    this.mode.set('history');
  }

  goHistory(): void {
    this.mode.set('history');
  }

  goSetup(): void {
    this.result.set(null);
    this.mode.set('setup');
  }
}
