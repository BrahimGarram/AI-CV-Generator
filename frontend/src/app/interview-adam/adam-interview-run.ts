/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

import { Component, computed, inject, input, OnDestroy, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';

import { AdamInterviewApi } from './interview-adam.api';
import {
  EvaluationOut,
  InterviewContext,
  InterviewQuestion,
  ImprovementOut,
  SessionDetail,
} from './models';
import { categoryLabel, formatScore, scoreTone, seniorityLabel, typeLabel } from './labels';

type StepState = 'idle' | 'queued' | 'running' | 'done' | 'error';

interface EvalCell {
  state: StepState;
  result: EvaluationOut | null;
  error: string;
}
interface ImproveCell {
  state: StepState;
  result: ImprovementOut | null;
  error: string;
}

const idleEval: EvalCell = { state: 'idle', result: null, error: '' };
const idleImprove: ImproveCell = { state: 'idle', result: null, error: '' };

/** Seuil côté UI : en dessous, une « réponse » n'est plus une réponse et l'analyse coûte un appel LLM. */
const MIN_ANSWER_CHARS = 10;

/** Job de la file : la réponse est figée à la demande, sinon l'attente analyserait un texte modifié. */
type Job = { kind: 'eval'; index: number; answer: string } | { kind: 'improve'; index: number };

/**
 * Déroulé de l'entretien : une carte par question.
 * L'analyse d'une réponse part en arrière-plan — le candidat passe à la question suivante
 * sans attendre — et « Proposer une meilleure réponse » n'est déclenché que sur demande.
 */
@Component({
  selector: 'app-adam-interview-run',
  imports: [FormsModule],
  templateUrl: './adam-interview-run.html',
  styleUrl: './adam-interview-run.scss',
})
export class AdamInterviewRun implements OnDestroy {
  private readonly api = inject(AdamInterviewApi);

  readonly questions = input<InterviewQuestion[]>([]);
  readonly context = input<InterviewContext | null>(null);
  readonly sessionId = input('');
  readonly ragUsed = input(false);

  readonly dismissed = output<void>();
  readonly saved = output<void>();

  // Libellés/formatage exposés au modèle.
  readonly scoreTone = scoreTone;
  readonly formatScore = formatScore;
  readonly categoryLabel = categoryLabel;

  readonly answers = signal<Record<number, string>>({});
  readonly evals = signal<Record<number, EvalCell>>({});
  readonly improves = signal<Record<number, ImproveCell>>({});
  readonly globalError = signal<string | null>(null);

  readonly synthesis = signal<SessionDetail | null>(null);
  readonly synthesisLoading = signal(false);

  private readonly queue: Job[] = [];
  private running: Job | null = null;
  private destroyed = false;

  readonly total = computed(() => this.questions().length);
  readonly doneCount = computed(() => this.questions().filter((q) => this.evals()[q.index]?.state === 'done').length);
  readonly allDone = computed(() => this.total() > 0 && this.doneCount() === this.total());
  readonly progress = computed(() => (this.total() ? Math.round((this.doneCount() / this.total()) * 100) : 0));

  answerText(index: number): string {
    return this.answers()[index] ?? '';
  }

  evalCell(index: number): EvalCell {
    return this.evals()[index] ?? idleEval;
  }

  improveCell(index: number): ImproveCell {
    return this.improves()[index] ?? idleImprove;
  }

  seniorityLabel(code: string): string {
    return seniorityLabel(code);
  }

  typeLabel(code: string): string {
    return typeLabel(code);
  }

  setAnswer(index: number, value: string): void {
    this.answers.update((map) => ({ ...map, [index]: value }));
  }

  /** État en cours d'occupation pour la file ('queued' | 'running'), sinon null. */
  private busy(state: StepState): 'queued' | 'running' | null {
    return state === 'queued' || state === 'running' ? state : null;
  }

  canEvaluate(index: number): boolean {
    return this.answerText(index).trim().length >= MIN_ANSWER_CHARS && this.busy(this.evalCell(index).state) === null;
  }

  /** Un bouton grisé sans explication ne se devine pas : on dit ce qui manque. */
  shortAnswerHint(index: number): string | null {
    const chars = this.answerText(index).trim().length;
    if (chars === 0 || chars >= MIN_ANSWER_CHARS || this.busy(this.evalCell(index).state)) return null;
    return `Encore ${MIN_ANSWER_CHARS - chars} caractère(s) : une réponse doit faire au moins ${MIN_ANSWER_CHARS} caractères.`;
  }

  /**
   * Lance l'analyse sans bloquer l'interface : la requête part dans la file unique et
   * la carte passe immédiatement en « en attente ». Le candidat continue ses réponses.
   */
  evaluate(index: number): void {
    if (!this.canEvaluate(index)) return;
    this.evals.update((map) => ({ ...map, [index]: { ...idleEval, state: 'queued' } }));
    this.globalError.set(null);
    this.queue.push({ kind: 'eval', index, answer: this.answerText(index) });
    this.drain();
  }

  canImprove(index: number): boolean {
    const hasAnswer = this.answerText(index).trim().length > 0;
    return hasAnswer && this.busy(this.improveCell(index).state) === null;
  }

  /** Réponse améliorée demandée à la main (jamais automatique) : même file, donc « en attente » si occupé. */
  improve(index: number): void {
    if (!this.canImprove(index)) return;
    this.improves.update((map) => ({ ...map, [index]: { ...idleImprove, state: 'queued' } }));
    this.queue.push({ kind: 'improve', index });
    this.drain();
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.queue.length = 0;
  }

  // ------------------------------------------------------------------
  // File d'attente : une seule requête modèle à la fois
  // ------------------------------------------------------------------

  /**
   * Le serveur ne tient qu'un seul appel LLM à la fois (MAX_CONCURRENT_LLM_CALLS) :
   * sans file côté UI, les demandes simultanées partiraient toutes et resteraient
   * bloquées serveur, ce qui affiche « en cours » sans jamais dire « en attente ».
   *
   * `finalize` est obligatoire et non `complete` : un flux qui part en erreur ne se
   * termine PAS par `complete`. Sans lui, la file resterait occupée après le premier
   * échec et toutes les demandes suivantes attendraient pour toujours.
   */
  private drain(): void {
    if (this.destroyed || this.running || !this.queue.length) return;
    const job = this.queue.shift()!;
    this.running = job;

    if (job.kind === 'eval') {
      this.evals.update((map) => ({ ...map, [job.index]: { ...idleEval, state: 'running' } }));
      this.api
        .evaluate({ session_id: this.sessionId(), index: job.index, answer: job.answer })
        .pipe(finalize(this.onJobDone))
        .subscribe({
          next: (result) =>
            this.evals.update((map) => ({ ...map, [job.index]: { state: 'done', result, error: '' } })),
          error: (err: Error) =>
            this.evals.update((map) => ({
              ...map,
              [job.index]: { state: 'error', result: null, error: err.message },
            })),
        });
    } else {
      this.improves.update((map) => ({ ...map, [job.index]: { ...idleImprove, state: 'running' } }));
      this.api
        .improve({ session_id: this.sessionId(), index: job.index })
        .pipe(finalize(this.onJobDone))
        .subscribe({
          next: (result) =>
            this.improves.update((map) => ({ ...map, [job.index]: { state: 'done', result, error: '' } })),
          error: (err: Error) =>
            this.improves.update((map) => ({
              ...map,
              [job.index]: { state: 'error', result: null, error: err.message },
            })),
        });
    }
  }

  private readonly onJobDone = (): void => {
    this.running = null;
    this.drain();
  };

  loadSynthesis(): void {
    if (this.synthesis()) return;
    this.synthesisLoading.set(true);
    this.api.sessionDetail(this.sessionId()).subscribe({
      next: (detail) => {
        this.synthesis.set(detail);
        this.synthesisLoading.set(false);
        this.saved.emit();
      },
      error: (err: Error) => {
        this.globalError.set(err.message);
        this.synthesisLoading.set(false);
      },
    });
  }
}
