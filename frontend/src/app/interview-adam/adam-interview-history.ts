/* Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027 */

import { Component, OnInit, inject, output, signal } from '@angular/core';
import { DatePipe } from '@angular/common';

import { AdamInterviewApi } from './interview-adam.api';
import { SessionDetail, SessionSummary } from './models';
import { formatScore, scoreTone } from './labels';

/** Historique des entretiens : liste, réouverture en lecture seule et suppression. */
@Component({
  selector: 'app-adam-interview-history',
  imports: [DatePipe],
  templateUrl: './adam-interview-history.html',
  styleUrl: './adam-interview-history.scss',
})
export class AdamInterviewHistory implements OnInit {
  private readonly api = inject(AdamInterviewApi);

  readonly newInterview = output<void>();

  readonly sessions = signal<SessionSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly confirmId = signal<string | null>(null);

  readonly detail = signal<SessionDetail | null>(null);
  readonly detailLoading = signal(false);

  readonly scoreTone = scoreTone;
  readonly formatScore = formatScore;

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.sessions().subscribe({
      next: (list) => {
        this.sessions.set(list);
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }

  open(id: string): void {
    this.detailLoading.set(true);
    this.api.sessionDetail(id).subscribe({
      next: (d) => {
        this.detail.set(d);
        this.detailLoading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.detailLoading.set(false);
      },
    });
  }

  closeDetail(): void {
    this.detail.set(null);
  }

  askDelete(id: string): void {
    this.confirmId.set(id);
  }

  remove(id: string): void {
    this.api.deleteSession(id).subscribe({
      next: () => {
        this.confirmId.set(null);
        if (this.detail()?.id === id) this.closeDetail();
        this.load();
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }
}
