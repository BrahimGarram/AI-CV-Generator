import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Mise en forme légère des réponses de l'assistant (texte sûr : tout est échappé d'abord).
 * **gras**, *italique*, listes "- " / "• " / "1. ", citations « ... » sur leur propre ligne, retours à la ligne.
 */
@Pipe({ name: 'chatFormat' })
export class ChatFormatPipe implements PipeTransform {
  transform(text: string): string {
    const lines = escapeHtml(text).split('\n');
    const out: string[] = [];
    let list: 'ul' | 'ol' | null = null;

    const closeList = () => {
      if (list) {
        out.push(`</${list}>`);
        list = null;
      }
    };

    for (const raw of lines) {
      const line = raw.trim();
      const bullet = line.match(/^[-•*]\s+(.*)$/);
      const numbered = line.match(/^\d+[.)]\s+(.*)$/);
      if (bullet || numbered) {
        const type = bullet ? 'ul' : 'ol';
        if (list !== type) {
          closeList();
          out.push(`<${type}>`);
          list = type;
        }
        out.push(`<li>${inline((bullet || numbered)![1])}</li>`);
        continue;
      }
      closeList();
      if (!line) {
        out.push('<div class="gap"></div>');
      } else if (/^«.*»$/.test(line)) {
        out.push(`<blockquote>${inline(line.slice(1, -1).trim())}</blockquote>`);
      } else {
        out.push(`<p>${inline(line)}</p>`);
      }
    }
    closeList();
    return out.join('');
  }
}

function inline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, '$1<em>$2</em>');
}

/** Autorise l'affichage d'un PDF local (URL blob créée par l'application) dans une iframe. */
@Pipe({ name: 'safeResource' })
export class SafeResourcePipe implements PipeTransform {
  private readonly sanitizer = inject(DomSanitizer);

  transform(url: string): SafeResourceUrl {
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  }
}
