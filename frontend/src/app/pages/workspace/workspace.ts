import { DatePipe } from '@angular/common';
import { Component, ElementRef, OnDestroy, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../auth/auth.service';
import { CvApiService } from '../../cv-api.service';
import { CvPanel } from '../../cv-panel/cv-panel';
import { ChatFormatPipe, SafeResourcePipe } from '../../format';
import { ChatMessage, CvData, GeneratedCv, GenerationItem } from '../../models';

const SUGGESTIONS = [
  {
    title: 'Me présenter',
    text: 'Je suis étudiant en cycle ingénieur informatique à ESPRIT de 2022 à 2027. Je maîtrise Java, Spring Boot et Angular.',
  },
  {
    title: 'Ajouter un stage',
    text: "J'ai fait un stage chez Elyadata au Lac 2 en août 2025 pendant 2 mois : agents IA avec LangGraph et LangChain. Rends-le plus professionnel.",
  },
  {
    title: 'Demander conseil',
    text: "Qu'est-ce qui rend un CV d'étudiant en informatique vraiment convaincant ?",
  },
];

@Component({
  selector: 'app-workspace',
  imports: [FormsModule, RouterLink, DatePipe, CvPanel, ChatFormatPipe, SafeResourcePipe],
  templateUrl: './workspace.html',
  styleUrl: './workspace.scss',
})
export class Workspace implements OnInit, OnDestroy {
  private readonly api = inject(CvApiService);
  readonly auth = inject(AuthService);

  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');
  private readonly composer = viewChild<ElementRef<HTMLTextAreaElement>>('composer');

  readonly suggestions = SUGGESTIONS;

  // conversation
  readonly sessionId = signal<string | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly cv = signal<CvData | null>(null);
  readonly draft = signal('');
  readonly sending = signal(false);
  readonly waitingLong = signal(false);

  // CV affiché dans le panneau (généré maintenant ou ouvert depuis l'historique)
  readonly generated = signal<GeneratedCv | null>(null);
  readonly generating = signal(false);

  // historique
  readonly history = signal<GenerationItem[]>([]);
  readonly historyLoading = signal(true);
  readonly selectedId = signal<string | null>(null);
  readonly confirmDelete = signal<string | null>(null);

  // interface
  readonly online = signal<boolean | null>(null);
  readonly llmModel = signal<string | null>(null);
  readonly panelOpen = signal(false);
  readonly sidebarOpen = signal(false);
  readonly userMenu = signal(false);

  readonly started = computed(() => this.messages().some((m) => m.role === 'user'));
  readonly canSend = computed(() => !!this.draft().trim() && !this.sending() && !!this.sessionId());
  readonly canGenerate = computed(() => {
    const info = this.cv()?.personal_info;
    return !!(info?.first_name || info?.last_name) && !!this.sessionId();
  });

  private lastMessage = '';
  private longTimer?: ReturnType<typeof setTimeout>;
  private objectUrls: string[] = [];

  ngOnInit(): void {
    this.api.health().subscribe({
      next: (h) => {
        this.online.set(true);
        this.llmModel.set(h.llm_model);
      },
      error: () => this.online.set(false),
    });
    this.auth.refresh();
    this.loadHistory();
    this.newConversation();
  }

  ngOnDestroy(): void {
    clearTimeout(this.longTimer);
    this.objectUrls.forEach((u) => URL.revokeObjectURL(u));
  }

  // ------------------------------------------------------------------
  // Conversation
  // ------------------------------------------------------------------

  newConversation(): void {
    this.messages.set([]);
    this.cv.set(null);
    this.generated.set(null);
    this.selectedId.set(null);
    this.sessionId.set(null);
    this.sidebarOpen.set(false);
    this.api.createSession().subscribe({
      next: (res) => {
        this.online.set(true);
        this.sessionId.set(res.session_id);
        this.push('assistant', res.reply);
      },
      error: (err: Error) => this.push('error', err.message),
    });
  }

  useSuggestion(text: string): void {
    this.draft.set(text);
    this.composer()?.nativeElement.focus();
    queueMicrotask(() => this.autoResize());
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      this.send();
    }
  }

  send(text?: string): void {
    const message = (text ?? this.draft()).trim();
    const sessionId = this.sessionId();
    if (!message || !sessionId || this.sending()) return;

    this.lastMessage = message;
    if (!text) this.draft.set('');
    queueMicrotask(() => this.autoResize());
    this.push('user', message);
    this.startWaiting();

    this.api.sendMessage(sessionId, message).subscribe({
      next: (res) => {
        this.stopWaiting();
        this.cv.set(res.cv);
        this.push('assistant', res.reply, undefined, res.model, res.seconds);
        if (res.generated && res.tex_url) {
          this.showResult(res.tex_url, res.pdf_url, res.pdf_error, res.generation);
        }
      },
      error: (err: Error) => {
        this.stopWaiting();
        this.push('error', err.message);
      },
    });
  }

  retry(): void {
    const list = [...this.messages()];
    if (list.at(-1)?.role === 'error') list.pop();
    if (list.at(-1)?.role === 'user') list.pop();
    this.messages.set(list);
    this.send(this.lastMessage);
  }

  generateNow(): void {
    const sessionId = this.sessionId();
    if (!sessionId || this.generating()) return;
    this.generating.set(true);
    this.api.generate(sessionId).subscribe({
      next: (res) => {
        this.generating.set(false);
        this.showResult(res.tex_url, res.pdf_url, res.pdf_error, res.generation);
      },
      error: (err: Error) => {
        this.generating.set(false);
        this.push('error', err.message);
      },
    });
  }

  autoResize(): void {
    const el = this.composer()?.nativeElement;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  // ------------------------------------------------------------------
  // Historique
  // ------------------------------------------------------------------

  loadHistory(): void {
    this.historyLoading.set(true);
    this.api.history().subscribe({
      next: (items) => {
        this.history.set(items);
        this.historyLoading.set(false);
      },
      error: () => this.historyLoading.set(false),
    });
  }

  /** Ouvre un CV de l'historique dans le panneau d'aperçu. */
  openGeneration(item: GenerationItem): void {
    this.selectedId.set(item.id);
    this.sidebarOpen.set(false);
    if (!item.has_pdf) {
      this.generated.set({
        pdfObjectUrl: null,
        fileName: this.fileNameFor(item.title),
        texUrl: `/history/${item.id}/tex`,
        pdfError: "Ce CV n'a pas de PDF.",
        generationId: item.id,
      });
      this.panelOpen.set(true);
      return;
    }
    this.generating.set(true);
    this.api.getFile(`/history/${item.id}/pdf`).subscribe({
      next: (blob) => {
        this.generating.set(false);
        this.generated.set({
          pdfObjectUrl: this.objectUrl(blob),
          fileName: this.fileNameFor(item.title),
          texUrl: `/history/${item.id}/tex`,
          pdfError: null,
          generationId: item.id,
        });
        this.panelOpen.set(true);
      },
      error: (err: Error) => {
        this.generating.set(false);
        this.push('error', err.message);
      },
    });
  }

  askDelete(id: string, event: Event): void {
    event.stopPropagation();
    this.confirmDelete.set(this.confirmDelete() === id ? null : id);
  }

  deleteGeneration(id: string, event: Event): void {
    event.stopPropagation();
    this.api.deleteGeneration(id).subscribe({
      next: () => {
        this.history.update((list) => list.filter((g) => g.id !== id));
        this.confirmDelete.set(null);
        if (this.generated()?.generationId === id) this.generated.set(null);
        if (this.selectedId() === id) this.selectedId.set(null);
        this.auth.refresh();
      },
      error: (err: Error) => this.push('error', err.message),
    });
  }

  // ------------------------------------------------------------------
  // Fichiers
  // ------------------------------------------------------------------

  download(url: string, fileName: string): void {
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
  }

  openPdf(url: string): void {
    window.open(url, '_blank');
  }

  /** Le .tex est protégé par le jeton : on le récupère puis on le télécharge. */
  downloadTex(texUrl: string, fileName: string): void {
    this.api.getFile(texUrl).subscribe({
      next: (blob) => this.download(this.objectUrl(blob), fileName.replace(/\.pdf$/, '.tex')),
      error: (err: Error) => this.push('error', err.message),
    });
  }

  logout(): void {
    this.auth.logout();
  }

  // ------------------------------------------------------------------

  private showResult(
    texUrl: string,
    pdfUrl: string | null,
    pdfError: string | null,
    generation: GenerationItem | null,
  ): void {
    if (generation) {
      this.history.update((list) => [generation, ...list.filter((g) => g.id !== generation.id)]);
      this.selectedId.set(generation.id);
      this.auth.refresh();
    }
    const fileName = this.fileNameFor(generation?.title ?? 'CV');
    const base = { fileName, texUrl, generationId: generation?.id };
    if (!pdfUrl) {
      const result: GeneratedCv = { ...base, pdfObjectUrl: null, pdfError };
      this.generated.set(result);
      this.push('cv', '', result);
      return;
    }
    this.generating.set(true);
    this.api.getFile(pdfUrl).subscribe({
      next: (blob) => {
        this.generating.set(false);
        const result: GeneratedCv = { ...base, pdfObjectUrl: this.objectUrl(blob), pdfError: null };
        this.generated.set(result);
        this.push('cv', '', result);
      },
      error: (err: Error) => {
        this.generating.set(false);
        this.push('error', err.message);
      },
    });
  }

  private objectUrl(blob: Blob): string {
    const typed = blob.type ? blob : new Blob([blob], { type: 'application/pdf' });
    const url = URL.createObjectURL(typed);
    this.objectUrls.push(url);
    return url;
  }

  private fileNameFor(title: string): string {
    const slug = title
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/\W+/g, '_')
      .replace(/^_|_$/g, '');
    return `${slug || 'CV'}.pdf`;
  }

  private startWaiting(): void {
    this.sending.set(true);
    this.waitingLong.set(false);
    this.longTimer = setTimeout(() => this.waitingLong.set(true), 8000);
  }

  private stopWaiting(): void {
    clearTimeout(this.longTimer);
    this.sending.set(false);
    this.waitingLong.set(false);
  }

  private push(
    role: ChatMessage['role'],
    content: string,
    cv?: GeneratedCv,
    model?: string | null,
    seconds?: number | null,
  ): void {
    this.messages.update((list) => [...list, { role, content, time: new Date(), cv, model, seconds }]);
    setTimeout(() => {
      const el = this.scroller()?.nativeElement;
      el?.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    });
  }
}
