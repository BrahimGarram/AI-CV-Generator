/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

import { Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GenerationItem } from '../models';
import { AdamInterviewApi } from './interview-adam.api';
import { InterviewStatus, QuestionsOut } from './models';
import { SENIORITY_OPTIONS, TYPE_OPTIONS } from './labels';

const MIN_Q = 3;
const MAX_Q = 15;

/**
 * Formulaire de lancement : poste visé, niveau, type de questions, nombre et langue.
 * Optionnel : appuyer l'entretien sur un CV déjà généré par le Module 1 (via son historique).
 */
@Component({
  selector: 'app-adam-interview-setup',
  imports: [FormsModule],
  templateUrl: './adam-interview-setup.html',
  styleUrl: './adam-interview-setup.scss',
})
export class AdamInterviewSetup implements OnInit {
  private readonly api = inject(AdamInterviewApi);

  readonly status = input<InterviewStatus | null>(null);
  readonly started = output<QuestionsOut>();
  readonly cancel = output<void>();

  readonly seniorities = SENIORITY_OPTIONS;
  readonly types = TYPE_OPTIONS;
  readonly languages = [
    { value: 'fr', label: 'Français' },
    { value: 'en', label: 'Anglais' },
  ];

  readonly jobTitle = signal('');
  readonly jobDescription = signal('');
  readonly company = signal('');
  readonly seniority = signal('junior');
  readonly questionType = signal('mixed');
  readonly language = signal('fr');
  readonly nQuestions = signal(6);
  readonly useCv = signal(false);
  readonly cvId = signal<string | null>(null);

  readonly cvList = signal<GenerationItem[]>([]);
  readonly cvLoading = signal(true);
  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);

  readonly minQ = MIN_Q;
  readonly maxQ = MAX_Q;

  readonly canSubmit = computed(() => {
    const title = this.jobTitle().trim();
    const enoughTitle = title.length >= 2;
    const cvOk = !this.useCv() || !!this.cvId();
    return enoughTitle && cvOk && !this.submitting();
  });

  ngOnInit(): void {
    this.api.cvHistory().subscribe({
      next: (list) => {
        this.cvList.set(list);
        this.cvLoading.set(false);
      },
      error: () => this.cvLoading.set(false),
    });
  }

  setQuestionCount(value: unknown): void {
    const n = Math.round(Number(value));
    this.nQuestions.set(Number.isFinite(n) ? Math.min(MAX_Q, Math.max(MIN_Q, n)) : MIN_Q);
  }

  toggleCv(value: boolean): void {
    this.useCv.set(value);
    if (!value) this.cvId.set(null);
  }

  submit(): void {
    if (!this.canSubmit()) return;
    this.error.set(null);
    this.submitting.set(true);
    this.api
      .questions({
        job_title: this.jobTitle().trim(),
        job_description: this.jobDescription().trim() || null,
        company: this.company().trim() || null,
        seniority: this.seniority(),
        question_type: this.questionType(),
        n_questions: this.nQuestions(),
        language: this.language(),
        use_cv: this.useCv(),
        cv_generation_id: this.useCv() ? this.cvId() : null,
      })
      .subscribe({
        next: (out) => {
          this.submitting.set(false);
          this.started.emit(out);
        },
        error: (err: Error) => {
          this.submitting.set(false);
          this.error.set(err.message);
        },
      });
  }
}
