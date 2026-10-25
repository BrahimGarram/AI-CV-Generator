import { Component, computed, effect, input, output, signal } from '@angular/core';

import { SafeResourcePipe } from '../format';
import { CvData, GeneratedCv } from '../models';

type Tab = 'data' | 'pdf';

@Component({
  selector: 'app-cv-panel',
  imports: [SafeResourcePipe],
  templateUrl: './cv-panel.html',
  styleUrl: './cv-panel.scss',
})
export class CvPanel {
  readonly cv = input<CvData | null>(null);
  readonly result = input<GeneratedCv | null>(null);
  readonly generating = input(false);
  readonly canGenerate = input(false);

  readonly generate = output<void>();
  readonly download = output<{ url: string; fileName: string }>();
  readonly openPdf = output<string>();

  readonly tab = signal<Tab>('data');

  readonly pdfUrl = computed(() => this.result()?.pdfObjectUrl ?? null);

  constructor() {
    // Dès qu'un PDF est généré, on affiche l'onglet d'aperçu ; nouvelle conversation -> données.
    effect(() => this.tab.set(this.pdfUrl() ? 'pdf' : 'data'));
  }

  readonly fullName = computed(() => {
    const info = this.cv()?.personal_info;
    return [info?.first_name, info?.last_name].filter(Boolean).join(' ');
  });

  readonly contacts = computed(() => {
    const info = this.cv()?.personal_info;
    if (!info) return [];
    return [info.email, info.phone, info.location, info.linkedin, info.github].filter(Boolean) as string[];
  });

  /** Progression indicative : sections principales remplies. */
  readonly sections = computed(() => {
    const cv = this.cv();
    const has = (v: unknown) => (Array.isArray(v) ? v.length > 0 : !!v);
    return [
      { label: 'Identité', done: has(this.fullName()) },
      { label: 'Contact', done: has(cv?.personal_info.email) },
      { label: 'Formation', done: has(cv?.education) },
      { label: 'Expériences', done: has(cv?.experiences) },
      { label: 'Projets', done: has(cv?.projects) },
      { label: 'Compétences', done: has(cv?.skills) },
      { label: 'Langues', done: has(cv?.languages) },
      { label: 'Profil', done: has(cv?.profile) },
    ];
  });

  readonly progress = computed(() => {
    const items = this.sections();
    return Math.round((items.filter((s) => s.done).length / items.length) * 100);
  });

  readonly isEmpty = computed(() => this.progress() === 0);

  dates(start: string | null, end: string | null): string {
    if (start && end) return `${start} – ${end}`;
    return end || (start ? `Depuis ${start}` : '');
  }

  showPdf(): void {
    if (this.pdfUrl()) this.tab.set('pdf');
  }

  downloadPdf(): void {
    const result = this.result();
    if (result?.pdfObjectUrl) this.download.emit({ url: result.pdfObjectUrl, fileName: result.fileName });
  }
}
